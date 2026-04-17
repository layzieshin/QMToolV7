"""
Signature and artifact operations for the Documents Workflow view.

Extracted from ``documents_workflow_view.py`` (Phase 3A) so the widget
itself contains no PDF/artifact/signature logic.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.presenters.artifact_paths import resolve_openable_artifact_paths
from modules.documents.contracts import ArtifactType
from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput


class DocumentsSignatureOps:
    _REASON_BY_TRANSITION: dict[str, str] = {
        "IN_PROGRESS->IN_REVIEW": "EDITING_COMPLETED",
        "IN_REVIEW->IN_APPROVAL": "REVIEW_ACCEPTED",
        "IN_APPROVAL->APPROVED": "FINAL_APPROVAL",
        "EXTEND_VALIDITY": "VALIDITY_EXTENSION",
    }

    """
    Stateless-ish helper that owns all signature / PDF / artifact path logic
    on behalf of the workflow widget.

    The widget passes its service ports at construction time so this class
    never imports or resolves them itself.
    """

    def __init__(
        self,
        *,
        signature_api: object | None,
        pool_api: object,
        um_service: object,
        audit_logger: object | None,
        app_home: Path,
        artifacts_root: Path,
    ) -> None:
        self._signature_api = signature_api
        self._pool = pool_api
        self._um = um_service
        self._audit_logger = audit_logger
        self._app_home = app_home
        self._artifacts_root = artifacts_root

    # ------------------------------------------------------------------
    # Audit helper
    # ------------------------------------------------------------------

    def audit(self, *, action: str, actor: str, target: str, result: str, reason: str = "") -> None:
        emit = getattr(self._audit_logger, "emit", None) if self._audit_logger is not None else None
        if callable(emit):
            emit(action=action, actor=actor, target=target, result=result, reason=reason)

    # ------------------------------------------------------------------
    # Signature building
    # ------------------------------------------------------------------

    def build_sign_request_or_none(
        self,
        state: object,
        transition: str,
        parent_widget: QWidget,
    ) -> SignRequest | None:
        profile = getattr(state, "workflow_profile", None)
        if profile is None or transition not in set(profile.signature_required_transitions):
            return None
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")

        input_path = self.find_pdf_for_signature(state, transition)
        if input_path is None:
            raise RuntimeError("Fuer den signaturpflichtigen Uebergang wurde keine PDF-Datei gefunden")

        signature_png = self.export_active_signature_png(str(user.user_id))
        signature_pixmap = QPixmap(str(signature_png))
        if signature_pixmap.isNull():
            raise RuntimeError("Aktive Signatur konnte nicht als Vorschau geladen werden")

        default_placement = SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=140.0)
        default_layout = self.resolved_runtime_layout(
            LabelLayoutInput(show_signature=True, show_name=True, show_date=True),
            user,
        )
        self.audit(
            action="documents.workflow.signature.placement.opened",
            actor=str(user.user_id),
            target=f"{state.document_id}:{state.version}",
            result="ok",
            reason=transition,
        )

        # Lazy import to avoid circular dependency at module level
        from interfaces.pyqt.widgets.signature_placement_dialog import SignaturePlacementDialog

        place_dialog = SignaturePlacementDialog(
            input_pdf=input_path,
            placement=default_placement,
            layout=default_layout,
            signature_pixmap=signature_pixmap,
            template_save_callback=self._save_signature_template_from_workflow,
            template_list_provider=self._list_signature_templates_for_dialog,
            template_load_callback=self._load_signature_template_for_dialog,
            parent=parent_widget,
        )
        place_dialog.showFullScreen()
        if place_dialog.exec() != QDialog.DialogCode.Accepted:
            self.audit(
                action="documents.workflow.signature.placement.cancelled",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="cancelled",
                reason=transition,
            )
            return None
        placement = place_dialog.placement()
        layout_result = place_dialog.layout_result()

        pwd_dialog = QDialog(parent_widget)
        pwd_dialog.setWindowTitle("Signatur fuer Uebergang erforderlich")
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        form = QFormLayout()
        form.addRow("Signatur-Passwort", password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(pwd_dialog.accept)
        buttons.rejected.connect(pwd_dialog.reject)
        layout = QVBoxLayout(pwd_dialog)
        layout.addWidget(
            QLabel(
                "Dieser Workflowschritt erfordert eine Signatur. Es wird automatisch eine visuelle Markierung mit Namens-/Datumslabel gesetzt."
            )
        )
        layout.addLayout(form)
        layout.addWidget(buttons)
        if pwd_dialog.exec() != QDialog.DialogCode.Accepted:
            self.audit(
                action="documents.workflow.signature.password.cancelled",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="cancelled",
                reason=transition,
            )
            return None

        safe_title = self.safe_document_title_token(getattr(state, "title", None))
        output_name = f"{state.document_id}_{safe_title}_signed.pdf"
        output_path = Path(tempfile.gettempdir()) / output_name
        reason = self._REASON_BY_TRANSITION.get(transition.strip().upper(), "WORKFLOW_TRANSITION")
        return SignRequest(
            input_pdf=input_path,
            output_pdf=output_path,
            signature_png=signature_png,
            placement=placement,
            layout=layout_result,
            overwrite_output=True,
            dry_run=False,
            sign_mode="visual",
            signer_user=str(user.user_id),
            password=password.text().strip() or None,
            reason=reason,
        )

    def build_extension_sign_request(
        self,
        state: object,
        parent_widget: QWidget,
    ) -> SignRequest | None:
        """Build a sign request specifically for the annual validity extension flow."""
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")

        input_path = self.find_pdf_for_signature(state, "EXTEND_VALIDITY")
        if input_path is None:
            raise RuntimeError("Keine PDF-Datei fuer Signatur gefunden. Bitte pruefen Sie die Artefakte.")

        signature_png = self.export_active_signature_png(str(user.user_id))
        signature_pixmap = QPixmap(str(signature_png))
        if signature_pixmap.isNull():
            raise RuntimeError("Aktive Signatur konnte nicht als Vorschau geladen werden")

        from interfaces.pyqt.widgets.signature_placement_dialog import SignaturePlacementDialog

        placement_dialog = SignaturePlacementDialog(
            input_pdf=input_path,
            placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=140.0),
            layout=self.resolved_runtime_layout(
                LabelLayoutInput(show_signature=True, show_name=True, show_date=True),
                user,
            ),
            signature_pixmap=signature_pixmap,
            template_list_provider=self._list_signature_templates_for_dialog,
            template_load_callback=self._load_signature_template_for_dialog,
            parent=parent_widget,
        )
        placement_dialog.showFullScreen()
        if placement_dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        placement = placement_dialog.placement()
        layout_result = placement_dialog.layout_result()

        pwd_dialog = QDialog(parent_widget)
        pwd_dialog.setWindowTitle("Signatur fuer Verlaengerung erforderlich")
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        form = QFormLayout()
        form.addRow("Signatur-Passwort", password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(pwd_dialog.accept)
        buttons.rejected.connect(pwd_dialog.reject)
        layout = QVBoxLayout(pwd_dialog)
        layout.addWidget(QLabel("Diese Gueltigkeitsverlaengerung erfordert eine Signatur."))
        layout.addLayout(form)
        layout.addWidget(buttons)

        if pwd_dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        safe_title = self.safe_document_title_token(getattr(state, "title", None))
        output_name = f"{state.document_id}_{safe_title}_extended.pdf"
        output_path = Path(tempfile.gettempdir()) / output_name

        return SignRequest(
            input_pdf=input_path,
            output_pdf=output_path,
            signature_png=signature_png,
            placement=placement,
            layout=layout_result,
            overwrite_output=True,
            dry_run=False,
            sign_mode="visual",
            signer_user=str(user.user_id),
            password=password.text().strip() or None,
            reason=self._REASON_BY_TRANSITION["EXTEND_VALIDITY"],
        )

    def require_signature_call(self, sign_request: SignRequest) -> None:
        sign = getattr(self._signature_api, "sign_with_fixed_position", None)
        if not callable(sign):
            raise RuntimeError("signature_api ist nicht verfuegbar oder unterstuetzt sign_with_fixed_position nicht")
        sign(sign_request)

    # ------------------------------------------------------------------
    # Signature templates
    # ------------------------------------------------------------------

    def _save_signature_template_from_workflow(
        self,
        name: str,
        placement: SignaturePlacementInput,
        layout: LabelLayoutInput,
    ) -> None:
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        create = getattr(self._signature_api, "create_user_signature_template", None)
        get_active = getattr(self._signature_api, "get_active_signature_asset_id", None)
        if not callable(create) or not callable(get_active):
            raise RuntimeError("Signatur-API unterstuetzt Vorlagen nicht")
        template_name = name.strip()
        if not template_name:
            raise RuntimeError("Bitte einen Vorlagennamen eingeben")
        signature_asset_id = get_active(user.user_id)
        if layout.show_signature and not signature_asset_id:
            raise RuntimeError("Keine aktive Signatur vorhanden. Bitte zuerst eine Signatur aktivieren.")
        create(
            owner_user_id=user.user_id,
            name=template_name,
            placement=placement,
            layout=replace(layout, name_text=None, date_text=None),
            signature_asset_id=signature_asset_id,
            scope="user",
        )

    def _list_signature_templates_for_dialog(self) -> list[tuple[str, str]]:
        user = self._um.get_current_user()
        if user is None:
            return []
        list_templates = getattr(self._signature_api, "list_user_signature_templates", None)
        if not callable(list_templates):
            return []
        rows: list[tuple[str, str]] = []
        for template in list_templates(user.user_id):
            rows.append((str(template.template_id), str(template.name)))
        return rows

    def _load_signature_template_for_dialog(self, template_id: str) -> tuple[SignaturePlacementInput, LabelLayoutInput]:
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        list_templates = getattr(self._signature_api, "list_user_signature_templates", None)
        if not callable(list_templates):
            raise RuntimeError("Signatur-API unterstuetzt Vorlagen nicht")
        for template in list_templates(user.user_id):
            if str(template.template_id) == str(template_id):
                return template.placement, self.resolved_runtime_layout(template.layout, user)
        raise RuntimeError(f"Signaturprofil '{template_id}' wurde nicht gefunden")

    # ------------------------------------------------------------------
    # Runtime layout / display name
    # ------------------------------------------------------------------

    @staticmethod
    def display_name(user: object) -> str:
        first = (getattr(user, "first_name", None) or "").strip()
        last = (getattr(user, "last_name", None) or "").strip()
        if first and last:
            return f"{first}, {last}"
        if first:
            return first
        if last:
            return last
        return (getattr(user, "display_name", None) or getattr(user, "username", None) or str(user.user_id)).strip()

    def resolved_runtime_layout(self, layout: LabelLayoutInput, user: object) -> LabelLayoutInput:
        name = self.display_name(user)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        seeded = replace(
            layout,
            name_text=name if layout.show_name else None,
            date_text=timestamp if layout.show_date else None,
        )
        resolver = getattr(self._signature_api, "resolve_runtime_layout", None)
        if callable(resolver):
            return resolver(seeded, signer_user=name)
        return seeded

    def export_active_signature_png(self, user_id: str) -> Path:
        get_active = getattr(self._signature_api, "get_active_signature_asset_id", None)
        export = getattr(self._signature_api, "export_active_signature", None)
        if not callable(get_active) or not callable(export):
            raise RuntimeError("Signatur-API unterstuetzt aktive Signaturvorschau nicht")
        active_asset_id = get_active(user_id)
        if not active_asset_id:
            raise RuntimeError("Keine aktive Signatur vorhanden. Bitte zuerst im Signaturmodul hinterlegen.")
        target = Path(tempfile.gettempdir()) / f"qmtool-signature-{uuid4().hex}.png"
        exported = export(user_id, target)
        if not exported.exists() or exported.stat().st_size == 0:
            raise RuntimeError("Aktive Signatur konnte nicht exportiert werden")
        return exported

    @staticmethod
    def safe_document_title_token(title: str | None) -> str:
        token = (title or "").strip().replace(" ", "_")
        token = (
            token.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("Ä", "Ae")
            .replace("Ö", "Oe")
            .replace("Ü", "Ue")
            .replace("ß", "ss")
        )
        safe = "".join(ch for ch in token if ch.isalnum() or ch in ("_", "-")).strip("_-")
        return safe or "Dokument"

    # ------------------------------------------------------------------
    # PDF search / DOCX conversion
    # ------------------------------------------------------------------

    def find_pdf_for_signature(self, state: object, transition: str | None = None) -> Path | None:
        artifacts = self._pool.list_artifacts(state.document_id, state.version)
        transition_key = (transition or "").strip().upper()
        if transition_key in {"IN_REVIEW->IN_APPROVAL", "IN_APPROVAL->APPROVED"}:
            priorities = [ArtifactType.SIGNED_PDF]
        elif transition_key == "EXTEND_VALIDITY":
            priorities = [ArtifactType.SIGNED_PDF, ArtifactType.RELEASED_PDF]
        else:
            priorities = [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF, ArtifactType.RELEASED_PDF]
        ordered_artifacts = sorted(artifacts, key=lambda a: 0 if getattr(a, "is_current", False) else 1)
        for artifact_type in priorities:
            for artifact in ordered_artifacts:
                if artifact.artifact_type != artifact_type:
                    continue
                for path in self.resolve_openable_artifact_paths(artifact):
                    if path.exists() and path.suffix.lower() == ".pdf":
                        return path

        if transition_key in {"IN_REVIEW->IN_APPROVAL", "IN_APPROVAL->APPROVED", "EXTEND_VALIDITY"}:
            return None

        conversion_errors: list[str] = []
        for artifact in ordered_artifacts:
            if artifact.artifact_type != ArtifactType.SOURCE_DOCX:
                continue
            for docx_path in self.resolve_openable_artifact_paths(artifact):
                if docx_path.exists() and docx_path.suffix.lower() == ".docx":
                    try:
                        converted = self.convert_docx_to_temp_pdf(docx_path)
                    except RuntimeError as exc:
                        conversion_errors.append(str(exc))
                        continue
                    if converted is not None:
                        return converted
        if conversion_errors:
            raise RuntimeError(conversion_errors[0])
        return None

    def convert_docx_to_temp_pdf(self, docx_path: Path) -> Path | None:
        if os.name != "nt":
            raise RuntimeError("DOCX-zu-PDF Fallback wird nur unter Windows unterstuetzt")
        safe_stem = self.safe_document_title_token(docx_path.stem)
        output_name = f"{safe_stem}_{uuid4().hex[:8]}.pdf"
        output_path = Path(tempfile.gettempdir()) / output_name
        try:
            import win32com.client  # type: ignore[import]

            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = False
            try:
                doc = word.Documents.Open(str(docx_path.resolve()))
                try:
                    if doc.Revisions.Count > 0:
                        doc.Revisions.AcceptAll()
                    doc.ExportAsFixedFormat(
                        str(output_path.resolve()),
                        17, False, 0, 0, 1, 1, 0, True, True, 0, True, True, False,
                    )
                finally:
                    doc.Close(False)
            finally:
                word.Quit()
        except ImportError:
            try:
                from docx2pdf import convert  # type: ignore[import]
                convert(str(docx_path), str(output_path))
            except ImportError:
                raise RuntimeError(
                    "Weder pywin32 noch docx2pdf verfuegbar. "
                    "Bitte installieren: pip install pywin32 (empfohlen) oder pip install docx2pdf"
                )
        except Exception as exc:
            raise RuntimeError(f"Fehler bei DOCX-zu-PDF Konvertierung: {exc}") from exc
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        raise RuntimeError(f"DOCX-zu-PDF Konvertierung fehlgeschlagen fuer {docx_path}")

    # ------------------------------------------------------------------
    # Artifact path resolution
    # ------------------------------------------------------------------

    def open_artifact(self, state: object, artifact_type: ArtifactType) -> bool:
        artifacts = self._pool.list_artifacts(state.document_id, state.version)
        for artifact in artifacts:
            if artifact.artifact_type != artifact_type:
                continue
            for path in self.resolve_openable_artifact_paths(artifact):
                if not path.exists():
                    continue
                if hasattr(os, "startfile"):
                    os.startfile(str(path))  # type: ignore[attr-defined]
                    return True
        return False

    def resolve_openable_artifact_paths(self, artifact: object) -> list[Path]:
        return resolve_openable_artifact_paths(
            artifact=artifact,
            app_home=self._app_home,
            artifacts_root=self._artifacts_root,
        )


