from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.widgets.signature_request_form import SignatureRequestForm
from interfaces.pyqt.widgets.signature_actions import SignatureActions
from interfaces.pyqt.widgets.signature_canvas_dialog import SignatureCanvasDialog
from interfaces.pyqt.widgets.signature_placement_dialog import SignaturePlacementDialog
from interfaces.pyqt.registry.contribution import QtModuleContribution
from qm_platform.runtime.container import RuntimeContainer


class SignatureWorkspace(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._api = container.get_port("signature_api")
        self._um = container.get_port("usermanagement_service")
        self._audit = container.get_port("audit_logger") if container.has_port("audit_logger") else None
        self._actions = SignatureActions(self._api)
        self._form = SignatureRequestForm()
        self._form.output_pdf.setReadOnly(False)
        self._template_preview = QPlainTextEdit()
        self._template_preview.setReadOnly(True)
        self._placement_status = QLabel("Platzierung: Standardwerte aktiv")
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        outer = QVBoxLayout(self)
        info = QLabel(
            "Ad-hoc-Signatur fuer externe Dokumente ausserhalb der Dokumentenlenkung. "
            "Globale Signaturkonfiguration und Vorlagenverwaltung liegen unter Einstellungen."
        )
        info.setWordWrap(True)
        outer.addWidget(info)
        outer.addWidget(self._form)
        auto_path_hint = QLabel(
            "Ausgabe-PDF wird automatisch im gleichen Ordner als *_signiert.pdf gesetzt und ist schreibgeschützt."
        )
        auto_path_hint.setWordWrap(True)
        outer.addWidget(auto_path_hint)
        outer.addWidget(QLabel("Profil-Vorschau"))
        outer.addWidget(self._template_preview, stretch=1)
        outer.addWidget(self._placement_status)

        buttons = QHBoxLayout()
        btn_in = QPushButton("Eingabe-PDF waehlen")
        btn_out = QPushButton("Ausgabe-PDF waehlen")
        btn_png = QPushButton("Signaturbild waehlen")
        btn_canvas = QPushButton("Signatur zeichnen")
        btn_profiles = QPushButton("Profile laden")
        btn_place = QPushButton("Platzierungsvorschau")
        btn_manage = QPushButton("Signatur verwalten")
        btn_sign = QPushButton("Dokument ad-hoc signieren")
        btn_in.clicked.connect(self._pick_input)
        btn_out.clicked.connect(self._pick_output)
        btn_png.clicked.connect(self._pick_png)
        btn_canvas.clicked.connect(self._open_canvas)
        btn_profiles.clicked.connect(self._load_profiles)
        btn_place.clicked.connect(self._open_placement_preview)
        btn_manage.clicked.connect(self._open_manage_flow)
        btn_sign.clicked.connect(self._sign_fixed)
        buttons.addWidget(btn_in)
        buttons.addWidget(btn_out)
        buttons.addWidget(btn_png)
        buttons.addWidget(btn_canvas)
        buttons.addWidget(btn_profiles)
        buttons.addWidget(btn_place)
        buttons.addWidget(btn_manage)
        buttons.addWidget(btn_sign)
        buttons.addStretch(1)
        outer.addLayout(buttons)
        outer.addWidget(self._out, stretch=1)

        self._form.input_pdf.textChanged.connect(lambda _text: self._auto_output_path())
        self._form.profile.currentTextChanged.connect(lambda _text: self._update_profile_preview())
        self._auto_output_path()
        self._load_profiles()

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}: {payload}\n")

    def _show_error(self, exc: Exception) -> None:
        QMessageBox.warning(self, "Signatur", str(exc))
        self._append("ERROR", {"message": str(exc)})

    def _current_user(self):
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        return user

    def _pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Eingabe-PDF", "", "PDF (*.pdf)")
        if path:
            self._form.input_pdf.setText(path)

    def _pick_png(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Signaturbild", "", "Images (*.png *.gif)")
        if path:
            self._form.signature_png.setText(path)

    def _pick_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Ausgabe-PDF", self._form.output_pdf.text().strip(), "PDF (*.pdf)")
        if path:
            self._form.output_pdf.setText(path)

    def _open_canvas(self) -> None:
        dialog = SignatureCanvasDialog(self)
        dialog.exec()
        user = self._um.get_current_user()
        if user is not None and dialog.signature_bytes() is not None:
            password = self._form.password.text().strip() or None
            asset = self._api.import_signature_asset_bytes_and_set_active(
                user.user_id,
                dialog.signature_bytes(),
                filename_hint="canvas.png",
                password=password,
            )
            self._append("AKTIVE_SIGNATUR_AKTUALISIERT", {"asset_id": asset.asset_id})
        saved = dialog.saved_path()
        if saved is not None:
            self._form.signature_png.setText(str(saved))
            self._append("SIGNATUR_CANVAS_GESPEICHERT", {"path": str(saved)})

    def _open_manage_flow(self) -> None:
        try:
            self._open_canvas()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _open_placement_preview(self) -> None:
        try:
            if not self._form.input_pdf.text().strip():
                raise RuntimeError("Bitte zuerst eine Eingabe-PDF auswählen.")
            placement = self._form.build_request(signer_user="preview", reason="pyqt_preview").placement
            dialog = SignaturePlacementDialog(
                input_pdf=Path(self._form.input_pdf.text().strip()),
                placement=placement,
                parent=self,
            )
            if dialog.exec() != dialog.DialogCode.Accepted:
                self._placement_status.setText("Platzierung: Dialog abgebrochen, Werte unveraendert")
                return
            updated = dialog.placement()
            self._form.page_index.setText(str(updated.page_index))
            self._form.x.setText(str(updated.x))
            self._form.y.setText(str(updated.y))
            self._form.width.setText(str(updated.target_width))
            self._placement_status.setText(
                f"Platzierung: Seite {updated.page_index}, x={updated.x}, y={updated.y}, Breite={updated.target_width}"
            )
            self._append("PLATZIERUNG_AKTUALISIERT", {"page": updated.page_index, "x": updated.x, "y": updated.y, "w": updated.target_width})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _sign_fixed(self) -> None:
        try:
            user = self._current_user()
            if not self._form.input_pdf.text().strip():
                raise RuntimeError("Bitte zuerst eine Eingabe-PDF auswählen.")
            self._ensure_active_signature_available(user.user_id)
            output = self._form.output_pdf.text().strip()
            if output and Path(output).exists():
                if self._audit is not None:
                    self._audit.emit(
                        action="signature.output.conflict.blocked",
                        actor=user.user_id,
                        target=output,
                        result="blocked",
                        reason="output file already exists",
                    )
                raise RuntimeError("Zieldatei existiert bereits. Bitte Eingabe anpassen oder Datei umbenennen.")
            payload = self._actions.sign_from_form(self._form, user_id=user.user_id, username=user.username)
            self._append("ADHOC_SIGNIERT", payload)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _auto_output_path(self) -> None:
        input_path = self._form.input_pdf.text().strip()
        if not input_path:
            self._form.output_pdf.clear()
            return
        if self._form.output_pdf.text().strip():
            return
        src = Path(input_path)
        stem = src.stem or "dokument"
        target = src.with_name(f"{stem}_signiert.pdf")
        self._form.output_pdf.setText(str(target))

    def _load_profiles(self) -> None:
        try:
            user = self._current_user()
            rows = self._actions.list_templates_for_select(user.user_id)
            self._form.set_profiles(rows)
            self._append("PROFILE_GELADEN", {"count": len(rows), "profiles": [name for _, name in rows]})
            self._update_profile_preview()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _ensure_active_signature_available(self, user_id: str) -> None:
        selected = self._form.selected_profile()
        if selected:
            template = self._actions.get_template_by_id(user_id, selected)
            if template is not None and template.layout.show_signature and template.signature_asset_id:
                return
        if self._form.signature_png.text().strip():
            return
        active = self._api.get_active_signature_asset_id(user_id)
        if active:
            return
        reply = QMessageBox.question(
            self,
            "Aktive Signatur fehlt",
            "Es ist keine aktive Signatur vorhanden. Jetzt zeichnen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._open_canvas()
        else:
            raise RuntimeError("Keine aktive Signatur vorhanden. Bitte zuerst Signatur verwalten.")

    def _update_profile_preview(self) -> None:
        try:
            user = self._current_user()
            payload = self._actions.build_profile_preview_payload(self._form, user_id=user.user_id)
            if "template" in payload:
                template = payload["template"]
                text = [
                    f"Profil: {payload.get('selected_profile', '-')}",
                    f"Seite: {template.placement.page_index}",
                    f"Position: x={template.placement.x}, y={template.placement.y}",
                    f"Breite: {template.placement.target_width}",
                    f"Name anzeigen: {'ja' if template.layout.show_name else 'nein'} ({template.layout.name_position})",
                    f"Datum anzeigen: {'ja' if template.layout.show_date else 'nein'} ({template.layout.date_position})",
                ]
                self._template_preview.setPlainText("\n".join(text))
                return
            if payload.get("modus") == "eigene_parameter":
                self._template_preview.setPlainText(
                    "Eigene Parameter aktiv.\n"
                    "Ausgabe-Pfad wird automatisch aus der Eingabe erzeugt (_signiert.pdf).\n"
                    f"Live-Preview: {self._form.preview.text()}"
                )
                return
            self._template_preview.setPlainText(f"Profilvorschau nicht verfügbar: {payload}")
        except Exception as exc:  # noqa: BLE001
            self._template_preview.setPlainText(f"Fehler bei der Profilvorschau: {exc}")


def _build(container: RuntimeContainer) -> QWidget:
    return SignatureWorkspace(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="signature.workspace",
            module_id="signature",
            title="Signatur",
            sort_order=30,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
