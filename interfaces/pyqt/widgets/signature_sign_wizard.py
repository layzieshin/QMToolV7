from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.widgets.signature_actions import SignatureActions
from interfaces.pyqt.presenters.formatting import format_local, now_utc_aware
from interfaces.pyqt.widgets.signature_placement_dialog import SignaturePlacementDialog
from interfaces.pyqt.widgets.signature_request_form import SignatureRequestForm
from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput


class SignatureSignWizard(QDialog):
    """Guided sign flow: 1) Datei  2) Vorlage  3) Platzierung  4) Passwort + Signieren."""

    def __init__(
        self,
        *,
        signature_api,
        usermanagement_service,
        settings_service=None,
        audit_logger=None,
        manage_signature_callback=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dokument signieren")
        self.resize(360, 240)

        self._api = signature_api
        self._um = usermanagement_service
        self._settings_service = settings_service
        self._audit = audit_logger
        self._manage_signature_callback = manage_signature_callback
        self._actions = SignatureActions(signature_api)
        self._form = SignatureRequestForm()
        self._form.output_pdf.setReadOnly(False)

        self._result_payload: object | None = None
        self._current_placement: SignaturePlacementInput | None = None
        self._current_layout: LabelLayoutInput = self._resolved_runtime_layout(LabelLayoutInput())
        self._startup_signature_checked = False

        self._input_pdf = QLineEdit()
        self._output_pdf = QLineEdit()
        self._profile = QComboBox()
        self._profile_hint = QLabel("")
        self._profile_hint.setWordWrap(True)
        self._placement_status = QLabel("Platzierung noch nicht geprüft.")
        self._placement_status.setWordWrap(True)
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Passwort für die Freigabe eingeben")

        self._step_hint = QLabel("")
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_input_page())
        self._stack.addWidget(self._build_profile_page())
        self._stack.addWidget(self._build_placement_page())
        self._stack.addWidget(self._build_password_page())

        self._nav_back = QPushButton("Zurück")
        self._nav_next = QPushButton("Weiter")
        self._nav_sign = QPushButton("Signieren")
        self._nav_cancel = QPushButton("Abbrechen")
        self._nav_back.clicked.connect(self._on_back)
        self._nav_next.clicked.connect(self._on_next)
        self._nav_sign.clicked.connect(self._on_sign)
        self._nav_cancel.clicked.connect(self.reject)

        nav = QHBoxLayout()
        nav.addWidget(self._nav_back)
        nav.addWidget(self._nav_next)
        nav.addStretch(1)
        nav.addWidget(self._nav_sign)
        nav.addWidget(self._nav_cancel)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)
        root.addWidget(self._step_hint)
        root.addWidget(self._stack, stretch=1)
        root.addLayout(nav)

        self._input_pdf.textChanged.connect(self._on_input_pdf_changed)
        self._output_pdf.textChanged.connect(lambda _v: self._sync_form())
        self._profile.currentIndexChanged.connect(lambda _v: self._update_profile_hint())

        self._load_profiles()
        self._set_step(0)
        self.adjustSize()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._startup_signature_checked:
            self._startup_signature_checked = True
            self._ensure_signature_available_for_start()

    def result_payload(self) -> object | None:
        return self._result_payload

    def _build_input_page(self) -> QWidget:
        page = QWidget()
        pick_input = QPushButton("Datei auswählen…")
        pick_output = QPushButton("Zielpfad ändern…")
        pick_input.clicked.connect(self._pick_input)
        pick_output.clicked.connect(self._pick_output)

        row_in = QHBoxLayout()
        row_in.addWidget(self._input_pdf)
        row_in.addWidget(pick_input)

        row_out = QHBoxLayout()
        row_out.addWidget(self._output_pdf)
        row_out.addWidget(pick_output)

        form = QFormLayout(page)
        form.addRow("Eingabe-PDF", row_in)
        form.addRow("Ausgabe-PDF", row_out)
        hint = QLabel("Standard: gleicher Ordner wie Eingabe, Dateiname + '_signiert.pdf'.")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return page

    def _build_profile_page(self) -> QWidget:
        page = QWidget()
        load_btn = QPushButton("Vorlagen neu laden")
        load_btn.clicked.connect(self._load_profiles)

        btn_row = QHBoxLayout()
        btn_row.addWidget(load_btn)
        btn_row.addStretch(1)

        form = QFormLayout(page)
        form.addRow("Signatur-Vorlage", self._profile)
        form.addRow("", btn_row)
        form.addRow("", self._profile_hint)
        return page

    def _build_placement_page(self) -> QWidget:
        page = QWidget()
        btn_preview = QPushButton("Platzierungsvorschau öffnen")
        btn_preview.clicked.connect(self._open_placement_preview)

        form = QFormLayout(page)
        form.addRow("Platzierung", self._placement_status)
        form.addRow("", btn_preview)
        form.addRow("", QLabel("Die Detail-Anpassungen und das Speichern als Vorlage erfolgen in der Vorschau."))
        return page

    def _build_password_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        hint = QLabel("Letzter Schritt: Passwort eingeben und das Dokument signieren.")
        hint.setWordWrap(True)
        form.addRow("", hint)
        form.addRow("Signier-Passwort", self._password)
        return page

    def _set_step(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._nav_back.setEnabled(index > 0)
        self._nav_next.setVisible(index < self._stack.count() - 1)
        self._nav_sign.setVisible(index == self._stack.count() - 1)
        hints = {
            0: "Schritt 1 / 4 — Datei wählen und Zielpfad prüfen.",
            1: "Schritt 2 / 4 — Signatur-Vorlage auswählen.",
            2: "Schritt 3 / 4 — Platzierung groß prüfen und anpassen.",
            3: "Schritt 4 / 4 — Passwort eingeben und signieren.",
        }
        self._step_hint.setText(hints.get(index, ""))
        self.adjustSize()

    def _on_back(self) -> None:
        self._set_step(max(0, self._stack.currentIndex() - 1))

    def _on_next(self) -> None:
        if self._stack.currentIndex() == 0 and not self._input_pdf.text().strip():
            QMessageBox.warning(self, "Signieren", "Bitte zuerst eine Eingabe-PDF auswählen.")
            return
        if self._stack.currentIndex() == 1:
            self._update_profile_hint()
        next_index = min(self._stack.count() - 1, self._stack.currentIndex() + 1)
        self._set_step(next_index)
        if next_index == 2:
            self._open_placement_preview()

    def _on_sign(self) -> None:
        try:
            user = self._current_user()
            self._sync_form()
            self._apply_dry_run_from_settings()
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
            self._result_payload = self._actions.sign_from_form(
                self._form,
                user_id=user.user_id,
                username=user.username,
                display_name=self._display_name(user),
                placement_override=self._current_placement,
                layout_override=self._resolved_runtime_layout(self._current_layout),
            )
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signieren", str(exc))

    def _current_user(self):
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        return user

    def _display_name(self, user) -> str:
        first = (getattr(user, "first_name", None) or "").strip()
        last = (getattr(user, "last_name", None) or "").strip()
        if first and last:
            return f"{first}, {last}"
        if first:
            return first
        if last:
            return last
        return (getattr(user, "display_name", None) or user.username or user.user_id).strip()

    def _resolved_runtime_layout(self, layout: LabelLayoutInput) -> LabelLayoutInput:
        user = self._um.get_current_user()
        display_name = self._display_name(user) if user is not None else ""
        timestamp = format_local(now_utc_aware())
        return replace(
            layout,
            name_text=display_name if layout.show_name else None,
            date_text=timestamp if layout.show_date else None,
        )

    def _template_layout(self, layout: LabelLayoutInput) -> LabelLayoutInput:
        return replace(layout, name_text=None, date_text=None)

    def _apply_dry_run_from_settings(self) -> None:
        dry_run = False
        if self._settings_service is not None:
            try:
                cfg = self._settings_service.get_module_settings("signature")
                dry_run = bool(cfg.get("dry_run_enabled", False))
            except Exception:  # noqa: BLE001
                pass
        self._form.dry_run.setChecked(dry_run)

    def _sync_form(self) -> None:
        self._form.input_pdf.setText(self._input_pdf.text().strip())
        self._form.output_pdf.setText(self._output_pdf.text().strip())
        self._form.password.setText(self._password.text())

        template_id = self._profile.currentData()
        if isinstance(template_id, str):
            idx = self._form.profile.findData(template_id)
            self._form.profile.setCurrentIndex(idx if idx >= 0 else 0)

        if self._current_placement is not None:
            self._form.page_index.setText(str(self._current_placement.page_index))
            self._form.x.setText(str(self._current_placement.x))
            self._form.y.setText(str(self._current_placement.y))
            self._form.width.setText(str(self._current_placement.target_width))
            self._placement_status.setText("Platzierung geprüft und gespeichert.")

        if self._current_layout is not None:
            self._form.show_name.setChecked(self._current_layout.show_name)
            self._form.show_date.setChecked(self._current_layout.show_date)
            self._form.name_position.setCurrentText(self._current_layout.name_position)
            self._form.date_position.setCurrentText(self._current_layout.date_position)
            self._form.name_font_size.setText(str(self._current_layout.name_font_size))
            self._form.date_font_size.setText(str(self._current_layout.date_font_size))
            self._form.name_rel_x.setText("" if self._current_layout.name_rel_x is None else str(self._current_layout.name_rel_x))
            self._form.name_rel_y.setText("" if self._current_layout.name_rel_y is None else str(self._current_layout.name_rel_y))
            self._form.date_rel_x.setText("" if self._current_layout.date_rel_x is None else str(self._current_layout.date_rel_x))
            self._form.date_rel_y.setText("" if self._current_layout.date_rel_y is None else str(self._current_layout.date_rel_y))

    def _on_input_pdf_changed(self, _text: str) -> None:
        path = self._input_pdf.text().strip()
        if path and not self._output_pdf.text().strip():
            src = Path(path)
            self._output_pdf.setText(str(src.with_name(f"{src.stem or 'dokument'}_signiert.pdf")))
        self._sync_form()

    def _pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Eingabe-PDF auswählen", "", "PDF (*.pdf)")
        if path:
            self._input_pdf.setText(path)

    def _pick_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Ausgabe-PDF Zielpfad", self._output_pdf.text().strip(), "PDF (*.pdf)"
        )
        if path:
            self._output_pdf.setText(path)

    def _load_profiles(self) -> None:
        try:
            user = self._current_user()
        except RuntimeError:
            return
        rows = self._actions.list_templates_for_select(user.user_id)
        self._profile.clear()
        self._profile.addItem("Eigene Parameter", "")
        for template_id, name in rows:
            self._profile.addItem(name, template_id)
        self._form.set_profiles(rows)
        self._update_profile_hint()

    def _update_profile_hint(self) -> None:
        self._sync_form()
        user = self._um.get_current_user()
        if user is None:
            self._profile_hint.setText("Nicht angemeldet")
            return
        payload = self._actions.build_profile_preview_payload(self._form, user_id=user.user_id)
        if "template" in payload:
            template = payload["template"]
            placement = getattr(template, "placement", None)
            template_layout = getattr(template, "layout", None)
            if placement is None:
                self._profile_hint.setText("Profilvorschau nicht verfügbar")
                return
            if template_layout is None:
                self._profile_hint.setText("Profilvorschau nicht verfügbar")
                return
            self._profile_hint.setText(
                f"Profil: {payload.get('selected_profile', '-')} — gespeicherte Platzierung wird in Schritt 3 geladen."
            )
            self._current_placement = placement
            self._current_layout = self._resolved_runtime_layout(template_layout)
            self._sync_form()
        elif payload.get("modus") == "eigene_parameter":
            self._profile_hint.setText("Eigene Parameter aktiv — Platzierung wird in Schritt 3 festgelegt.")
            self._current_layout = self._resolved_runtime_layout(self._current_layout)
        else:
            self._profile_hint.setText(f"Profilvorschau nicht verfügbar: {payload}")

    def _get_sig_pixmap(self) -> QPixmap | None:
        try:
            user = self._current_user()
            tmp_dir = Path(tempfile.mkdtemp(prefix="qmtool-sig-"))
            exported = self._api.export_active_signature(user.user_id, tmp_dir / "sig.png")
            if exported.exists():
                px = QPixmap(str(exported))
                return px if not px.isNull() else None
        except Exception:  # noqa: BLE001
            pass
        return None

    def _open_placement_preview(self) -> None:
        try:
            self._sync_form()
            if not self._form.input_pdf.text().strip():
                QMessageBox.warning(self, "Platzierung", "Bitte zuerst eine Eingabe-PDF auswählen.")
                return
            request = self._form.build_request(signer_user="preview", reason="pyqt_preview")
            placement = self._current_placement or request.placement
            layout = self._resolved_runtime_layout(self._current_layout or request.layout)
            dialog = SignaturePlacementDialog(
                input_pdf=Path(self._form.input_pdf.text().strip()),
                placement=placement,
                layout=layout,
                signature_pixmap=self._get_sig_pixmap(),
                template_save_callback=self._save_as_template,
                template_list_provider=self._list_templates_for_dialog,
                template_load_callback=self._load_template_for_dialog,
                parent=self,
            )
            dialog.showFullScreen()
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            self._current_placement = dialog.placement()
            self._current_layout = dialog.layout_result()
            self._sync_form()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Platzierung", str(exc))

    def _save_as_template(
        self,
        name: str,
        placement: SignaturePlacementInput,
        layout: LabelLayoutInput,
    ) -> None:
        user = self._current_user()
        normalized = name.strip()
        if not normalized:
            raise RuntimeError("Bitte einen Vorlagennamen eingeben.")
        self._api.create_user_signature_template(
            owner_user_id=user.user_id,
            name=normalized,
            placement=placement,
            layout=self._template_layout(layout),
            signature_asset_id=self._api.get_active_signature_asset_id(user.user_id),
            scope="user",
        )
        self._load_profiles()

    def _list_templates_for_dialog(self) -> list[tuple[str, str]]:
        user = self._current_user()
        return self._actions.list_templates_for_select(user.user_id)

    def _load_template_for_dialog(self, template_id: str) -> tuple[SignaturePlacementInput, LabelLayoutInput]:
        user = self._current_user()
        template = self._actions.get_template_by_id(user.user_id, template_id)
        if template is None:
            raise RuntimeError(f"Signaturprofil '{template_id}' wurde nicht gefunden")
        return template.placement, self._resolved_runtime_layout(template.layout)

    def _ensure_signature_available_for_start(self) -> None:
        try:
            user = self._current_user()
        except RuntimeError:
            self.reject()
            return
        if self._api.get_active_signature_asset_id(user.user_id):
            return
        message = (
            "Es ist noch keine aktive Signatur hinterlegt.\n\n"
            "Soll jetzt zur Signaturverwaltung gewechselt werden, um eine Signatur zu importieren oder zu zeichnen?"
        )
        reply = QMessageBox.question(
            self,
            "Aktive Signatur fehlt",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes and callable(self._manage_signature_callback):
            self._manage_signature_callback()
            self._load_profiles()
            if self._api.get_active_signature_asset_id(user.user_id):
                return
        QMessageBox.information(
            self,
            "Signieren abgebrochen",
            "Ohne aktive Signatur kann der Signaturprozess nicht gestartet werden.",
        )
        self.reject()

    def _ensure_active_signature_available(self, user_id: str) -> None:
        selected = self._form.selected_profile()
        if selected:
            template = self._actions.get_template_by_id(user_id, selected)
            if template is not None and template.layout.show_signature and template.signature_asset_id:
                return
        active = self._api.get_active_signature_asset_id(user_id)
        if active:
            return
        raise RuntimeError("Keine aktive Signatur vorhanden. Bitte zuerst die Signaturverwaltung verwenden.")
