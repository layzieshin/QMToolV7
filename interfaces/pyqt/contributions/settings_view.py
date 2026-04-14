from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import as_json_text, normalize_role
from interfaces.pyqt.presenters.settings_presenter import SettingsProfilePresenter
from interfaces.pyqt.presenters.settings_policy_presenter import SettingsPolicyPresenter
from interfaces.pyqt.contributions.users_view import UsersAdminWidget
from interfaces.pyqt.widgets.access_guards import require_admin_or_qmb
from interfaces.pyqt.widgets.signature_canvas_dialog import SignatureCanvasDialog
from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput
from interfaces.pyqt.registry.contribution import QtModuleContribution
from qm_platform.runtime.container import RuntimeContainer


class _ProfileWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._um = container.get_port("usermanagement_service")
        self._presenter = SettingsProfilePresenter()
        self._session_user = None
        self._username = QLineEdit()
        self._username.setReadOnly(True)
        self._user_id = QLineEdit()
        self._user_id.setReadOnly(True)
        self._role = QLineEdit()
        self._role.setReadOnly(True)
        self._display_name = QLineEdit()
        self._email = QLineEdit()
        self._department = QLineEdit()
        self._department.setReadOnly(True)
        self._current_password = QLineEdit()
        self._current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_password = QLineEdit()
        self._new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_password = QLineEdit()
        self._confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        refresh = QPushButton("Neu laden")
        refresh.clicked.connect(self._reload)
        save = QPushButton("Alle Änderungen speichern")
        save.clicked.connect(self._save_all)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Profil / Mein Benutzer als Ein-Formular-Ansicht mit Sektionen Konto, Organisation und Sicherheit."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        konto = QFormLayout()
        konto.addRow("Benutzername", self._username)
        konto.addRow("User-ID", self._user_id)
        konto.addRow("Rolle", self._role)
        layout.addWidget(QLabel("Konto"))
        layout.addLayout(konto)

        org = QFormLayout()
        org.addRow("Anzeigename", self._display_name)
        org.addRow("E-Mail", self._email)
        org.addRow("Abteilung", self._department)
        layout.addWidget(QLabel("Organisation"))
        layout.addLayout(org)

        sec = QFormLayout()
        sec.addRow("Aktuelles Passwort", self._current_password)
        sec.addRow("Neues Passwort", self._new_password)
        sec.addRow("Neues Passwort (Bestätigung)", self._confirm_password)
        layout.addWidget(QLabel("Sicherheit"))
        layout.addLayout(sec)

        row = QHBoxLayout()
        row.addWidget(refresh)
        row.addWidget(save)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(QLabel("Ergebnis"))
        layout.addWidget(self._out, stretch=1)
        self._reload()

    def _reload(self) -> None:
        self._session_user = self._um.get_current_user()
        if self._session_user is None:
            self._out.setPlainText("Anmeldung erforderlich.")
            return
        self._username.setText(self._session_user.username)
        self._user_id.setText(self._session_user.user_id)
        self._role.setText(self._session_user.role)
        self._display_name.setText(self._session_user.display_name or self._session_user.username)
        self._email.setText(self._session_user.email or "")
        self._department.setText(self._session_user.department or "")
        self._out.setPlainText(self._presenter.describe_session(self._session_user))

    def _save_all(self) -> None:
        try:
            if self._session_user is None:
                raise RuntimeError("Anmeldung erforderlich")
            current_pw = self._current_password.text().strip()
            new_pw = self._new_password.text().strip()
            confirm_pw = self._confirm_password.text().strip()
            display_name = self._display_name.text().strip() or None
            email = self._email.text().strip() or None

            profile_changed = (
                (self._session_user.display_name or None) != display_name
                or (self._session_user.email or None) != email
            )
            pw_changed = bool(current_pw or new_pw or confirm_pw)

            if not profile_changed and not pw_changed:
                self._out.setPlainText("Keine Änderungen erkannt.")
                return

            if profile_changed:
                self._um.update_user_profile(
                    self._session_user.username,
                    display_name=display_name,
                    email=email,
                )

            if pw_changed:
                if not current_pw:
                    raise RuntimeError("Aktuelles Passwort erforderlich")
                if not new_pw:
                    raise RuntimeError("Neues Passwort erforderlich")
                if new_pw != confirm_pw:
                    raise RuntimeError("Neues Passwort und Bestätigung stimmen nicht überein")
                auth_fn = getattr(self._um, "authenticate", None)
                if not callable(auth_fn):
                    raise RuntimeError("Passwortvalidierung nicht verfügbar")
                auth = auth_fn(self._session_user.username, current_pw)
                if auth is None:
                    raise RuntimeError("Aktuelles Passwort ist nicht korrekt")
                self._um.change_password(self._session_user.username, new_pw)
            self._current_password.clear()
            self._new_password.clear()
            self._confirm_password.clear()
            self._reload()
            self._out.setPlainText(
                self._presenter.save_result(
                    username=self._session_user.username,
                    profile_changed=profile_changed,
                    password_changed=pw_changed,
                )
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Profil", str(exc))


class _WorkflowProfilesWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._svc = container.get_port("settings_service")
        self._um = container.get_port("usermanagement_service")
        self._file_path = QLabel("-")
        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText('{"profiles":[...]}')
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Workflow-Profile (nur Admin/QMB). Bearbeitung nur auf bestehender Profilstruktur; "
                "es wird keine neue Workflow-Engine eingefuehrt."
            )
        )
        layout.addWidget(QLabel("profiles_file"))
        layout.addWidget(self._file_path)

        tools = QHBoxLayout()
        btn_reload = QPushButton("Profile laden")
        btn_reload.clicked.connect(self._reload)
        btn_save = QPushButton("Profile speichern")
        btn_save.clicked.connect(self._save)
        tools.addWidget(btn_reload)
        tools.addWidget(btn_save)
        tools.addStretch(1)
        layout.addLayout(tools)
        layout.addWidget(self._editor, stretch=1)
        layout.addWidget(QLabel("Ergebnis"))
        layout.addWidget(self._out, stretch=1)
        self._reload()

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _profiles_file(self) -> Path:
        cfg = self._svc.get_module_settings("documents")
        value = str(cfg.get("profiles_file", "")).strip()
        if not value:
            raise RuntimeError("documents.profiles_file ist nicht konfiguriert")
        path = Path(value)
        if not path.is_absolute():
            app_home = self._container.get_port("app_home")
            path = Path(app_home) / value
        return path

    def _reload(self) -> None:
        try:
            path = self._profiles_file()
            self._file_path.setText(str(path))
            raw = path.read_text(encoding="utf-8")
            self._editor.setPlainText(raw)
            payload = json.loads(raw)
            self._out.setPlainText(as_json_text({"status": "geladen", "profiles": len(payload.get("profiles", []))}))
        except Exception as exc:  # noqa: BLE001
            self._out.setPlainText(as_json_text({"error": str(exc)}))

    def _save(self) -> None:
        try:
            self._require_privileged()
            path = self._profiles_file()
            parsed = json.loads(self._editor.toPlainText().strip() or "{}")
            if not isinstance(parsed, dict) or not isinstance(parsed.get("profiles"), list):
                raise RuntimeError("Profil-Datei muss ein JSON-Objekt mit 'profiles' Liste sein")
            path.write_text(json.dumps(parsed, indent=2, ensure_ascii=True), encoding="utf-8")
            self._out.setPlainText(as_json_text({"status": "gespeichert", "path": str(path)}))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Workflow-Profile", str(exc))
            self._out.setPlainText(as_json_text({"error": str(exc)}))


class _ModuleSettingsWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._svc = container.get_port("settings_service")
        self._registry = self._svc.registry
        self._policy = SettingsPolicyPresenter()

        self._module = QComboBox()
        for mid in sorted(self._registry.list_module_ids()):
            self._module.addItem(mid)

        self._editor = QPlainTextEdit()
        self._ack = QCheckBox("Governance-kritische Einstellungsänderungen bestätigen")
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._hint = QLabel("Bearbeitbares JSON fuer Modul-Einstellungen. Speichern nur fuer QMB/Admin.")
        self._hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._hint)
        layout.addWidget(self._module)

        tools = QHBoxLayout()
        btn_reload = QPushButton("Neu laden")
        btn_reload.clicked.connect(self._reload_selected)
        btn_save = QPushButton("JSON speichern")
        btn_save.clicked.connect(self._save_selected)
        tools.addWidget(btn_reload)
        tools.addWidget(btn_save)
        tools.addStretch(1)
        layout.addLayout(tools)

        layout.addWidget(self._ack)
        layout.addWidget(self._editor, stretch=1)
        layout.addWidget(QLabel("Ergebnis"))
        layout.addWidget(self._out, stretch=1)

        self._module.currentTextChanged.connect(self._reload)
        if self._module.count():
            self._reload(self._module.currentText())

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}\n{as_json_text(payload)}\n")

    def _require_privileged(self) -> None:
        um = self._container.get_port("usermanagement_service")
        require_admin_or_qmb(um)
        user = um.get_current_user()
        if not self._policy.is_privileged(getattr(user, "role", None) if user is not None else None):
            raise RuntimeError("Nur Admin/QMB darf speichern")

    def _reload_selected(self) -> None:
        self._reload(self._module.currentText())

    def _reload(self, module_id: str) -> None:
        if not module_id:
            return
        data = self._svc.get_module_settings(module_id)
        self._editor.setPlainText(json.dumps(data, indent=2, ensure_ascii=True))
        self._append("GELADEN", {"module_id": module_id, "settings": data})

    def _save_selected(self) -> None:
        module_id = self._module.currentText().strip()
        if not module_id:
            return
        try:
            self._require_privileged()
            payload = json.loads(self._editor.toPlainText().strip() or "{}")
            if not isinstance(payload, dict):
                raise RuntimeError("Einstellungs-Payload muss ein JSON-Objekt sein")
            self._svc.set_module_settings(
                module_id,
                payload,
                acknowledge_governance_change=self._ack.isChecked(),
            )
            persisted = self._svc.get_module_settings(module_id)
            self._editor.setPlainText(json.dumps(persisted, indent=2, ensure_ascii=True))
            self._append("GESPEICHERT", {"module_id": module_id, "settings": persisted})
            self._append("GOVERNANCE_ACK", {"status": self._policy.summarize_governance_ack(acknowledged=self._ack.isChecked())})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Einstellungen", str(exc))


class _SignatureSettingsWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._settings = container.get_port("settings_service")
        self._signature = container.get_port("signature_api")
        self._um = container.get_port("usermanagement_service")

        self._require_password = QCheckBox("Passwort für Signaturvorgänge erforderlich")
        self._default_mode = QComboBox()
        self._default_mode.addItems(["visual", "crypto", "both"])
        self._templates_db = QLineEdit()
        self._assets_root = QLineEdit()
        self._master_key = QLineEdit()

        self._profile_name = QLineEdit("standard")
        self._profile_select = QComboBox()
        self._page_index = QLineEdit("0")
        self._x = QLineEdit("100")
        self._y = QLineEdit("100")
        self._width = QLineEdit("120")
        self._show_name = QCheckBox("Name anzeigen")
        self._show_name.setChecked(True)
        self._show_date = QCheckBox("Datum anzeigen")
        self._show_date.setChecked(True)
        self._name_pos = QComboBox()
        self._name_pos.addItems(["above", "below", "off"])
        self._date_pos = QComboBox()
        self._date_pos.addItems(["above", "below", "off"])
        self._asset_id = QLineEdit()
        self._active_asset = QLineEdit()
        self._active_asset.setReadOnly(True)
        self._replace_password = QLineEdit()
        self._replace_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._global_profile_select = QComboBox()
        self._global_profile_name = QLineEdit("global-standard")

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Signatur-Einstellungen (global)"))
        global_form = QFormLayout()
        global_form.addRow("", self._require_password)
        global_form.addRow("Default-Modus", self._default_mode)
        global_form.addRow("templates_db_path", self._templates_db)
        global_form.addRow("assets_root", self._assets_root)
        global_form.addRow("master_key_path", self._master_key)
        layout.addLayout(global_form)
        global_btn = QHBoxLayout()
        btn_reload = QPushButton("Signatur-Settings laden")
        btn_reload.clicked.connect(self._load_settings)
        btn_save = QPushButton("Signatur-Settings speichern")
        btn_save.clicked.connect(self._save_settings)
        global_btn.addWidget(btn_reload)
        global_btn.addWidget(btn_save)
        global_btn.addStretch(1)
        layout.addLayout(global_btn)

        layout.addWidget(QLabel("Signaturprofile"))
        profile_form = QFormLayout()
        profile_form.addRow("Profil wählen", self._profile_select)
        profile_form.addRow("Neuer Profilname", self._profile_name)
        profile_form.addRow("Signatur Asset-ID (optional)", self._asset_id)
        profile_form.addRow("Aktive Asset-ID", self._active_asset)
        profile_form.addRow("Passwort (ersetzen/löschen)", self._replace_password)
        profile_form.addRow("Seite", self._page_index)
        profile_form.addRow("X", self._x)
        profile_form.addRow("Y", self._y)
        profile_form.addRow("Breite", self._width)
        profile_form.addRow("", self._show_name)
        profile_form.addRow("Name-Position", self._name_pos)
        profile_form.addRow("", self._show_date)
        profile_form.addRow("Datum-Position", self._date_pos)
        layout.addLayout(profile_form)
        profile_btn = QHBoxLayout()
        btn_profiles = QPushButton("Profile laden")
        btn_profiles.clicked.connect(self._load_profiles)
        btn_create = QPushButton("Profil anlegen")
        btn_create.clicked.connect(self._create_profile)
        btn_canvas = QPushButton("Signatur zeichnen")
        btn_canvas.clicked.connect(self._open_canvas)
        btn_dup = QPushButton("Profil duplizieren")
        btn_dup.clicked.connect(self._duplicate_profile)
        btn_set_active = QPushButton("Asset als aktiv setzen")
        btn_set_active.clicked.connect(self._set_active_signature_asset)
        btn_export_active = QPushButton("Aktive Signatur exportieren")
        btn_export_active.clicked.connect(self._export_active_signature)
        btn_clear_active = QPushButton("Aktive Signatur löschen")
        btn_clear_active.clicked.connect(self._clear_active_signature)
        profile_btn.addWidget(btn_profiles)
        profile_btn.addWidget(btn_create)
        profile_btn.addWidget(btn_canvas)
        profile_btn.addWidget(btn_dup)
        profile_btn.addWidget(btn_set_active)
        profile_btn.addWidget(btn_export_active)
        profile_btn.addWidget(btn_clear_active)
        profile_btn.addStretch(1)
        layout.addLayout(profile_btn)

        layout.addWidget(QLabel("Globale Templates (Admin)"))
        global_form = QFormLayout()
        global_form.addRow("Global wählen", self._global_profile_select)
        global_form.addRow("Neuer globaler Name", self._global_profile_name)
        layout.addLayout(global_form)
        global_btn = QHBoxLayout()
        btn_global_load = QPushButton("Globale laden")
        btn_global_load.clicked.connect(self._load_global_profiles)
        btn_global_create = QPushButton("Global anlegen")
        btn_global_create.clicked.connect(self._create_global_profile)
        btn_global_delete = QPushButton("Global löschen")
        btn_global_delete.clicked.connect(self._delete_global_profile)
        btn_global_copy = QPushButton("Global -> User kopieren")
        btn_global_copy.clicked.connect(self._copy_global_to_user)
        global_btn.addWidget(btn_global_load)
        global_btn.addWidget(btn_global_create)
        global_btn.addWidget(btn_global_delete)
        global_btn.addWidget(btn_global_copy)
        global_btn.addStretch(1)
        layout.addLayout(global_btn)

        layout.addWidget(QLabel("Preview"))
        layout.addWidget(self._preview, stretch=1)
        layout.addWidget(QLabel("Ergebnis"))
        layout.addWidget(self._out, stretch=1)

        self._profile_select.currentTextChanged.connect(lambda _text: self._apply_selected_profile())
        for widget in [self._page_index, self._x, self._y, self._width]:
            widget.textChanged.connect(lambda _text: self._render_preview())
        self._show_name.toggled.connect(lambda _v: self._render_preview())
        self._show_date.toggled.connect(lambda _v: self._render_preview())
        self._name_pos.currentTextChanged.connect(lambda _text: self._render_preview())
        self._date_pos.currentTextChanged.connect(lambda _text: self._render_preview())
        self._load_settings()
        self._load_profiles()
        self._load_global_profiles()
        self._refresh_active_signature()

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}\n{as_json_text(payload)}\n")

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _load_settings(self) -> None:
        cfg = self._settings.get_module_settings("signature")
        self._require_password.setChecked(bool(cfg.get("require_password", True)))
        mode = str(cfg.get("default_mode", "visual"))
        idx = self._default_mode.findText(mode)
        if idx >= 0:
            self._default_mode.setCurrentIndex(idx)
        self._templates_db.setText(str(cfg.get("templates_db_path", "")))
        self._assets_root.setText(str(cfg.get("assets_root", "")))
        self._master_key.setText(str(cfg.get("master_key_path", "")))
        self._append("SIGNATUR_SETTINGS_GELADEN", cfg)

    def _save_settings(self) -> None:
        try:
            self._require_privileged()
            payload = {
                "require_password": self._require_password.isChecked(),
                "default_mode": self._default_mode.currentText(),
                "templates_db_path": self._templates_db.text().strip(),
                "assets_root": self._assets_root.text().strip(),
                "master_key_path": self._master_key.text().strip(),
            }
            self._settings.set_module_settings("signature", payload, acknowledge_governance_change=True)
            self._append("SIGNATUR_SETTINGS_GESPEICHERT", payload)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signatur-Einstellungen", str(exc))

    def _load_profiles(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            profiles = self._signature.list_user_signature_templates(user.user_id)
            self._profile_select.clear()
            self._profile_select.addItem("Neues Profil", "")
            for profile in profiles:
                self._profile_select.addItem(profile.name, profile.template_id)
            self._append("SIGNATUR_PROFILE_GELADEN", {"count": len(profiles)})
            self._render_preview()
            self._refresh_active_signature()
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _build_placement(self) -> SignaturePlacementInput:
        return SignaturePlacementInput(
            page_index=int(self._page_index.text().strip() or "0"),
            x=float(self._x.text().strip() or "0"),
            y=float(self._y.text().strip() or "0"),
            target_width=float(self._width.text().strip() or "120"),
        )

    def _build_layout(self) -> LabelLayoutInput:
        return LabelLayoutInput(
            show_signature=True,
            show_name=self._show_name.isChecked(),
            show_date=self._show_date.isChecked(),
            name_position=self._name_pos.currentText(),  # type: ignore[arg-type]
            date_position=self._date_pos.currentText(),  # type: ignore[arg-type]
        )

    def _create_profile(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            created = self._signature.create_user_signature_template(
                owner_user_id=user.user_id,
                name=self._profile_name.text().strip(),
                placement=self._build_placement(),
                layout=self._build_layout(),
                signature_asset_id=self._asset_id.text().strip() or None,
                scope="user",
            )
            self._append("SIGNATUR_PROFIL_ANGELEGT", created)
            self._load_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signaturprofil", str(exc))

    def _duplicate_profile(self) -> None:
        current = self._profile_select.currentText().strip()
        if not current or current == "Neues Profil":
            self._append("HINWEIS", {"message": "Bitte zuerst ein Profil auswählen"})
            return
        self._profile_name.setText(f"{current}-kopie")
        self._create_profile()

    def _apply_selected_profile(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                return
            selected_name = self._profile_select.currentText().strip()
            if not selected_name or selected_name == "Neues Profil":
                self._render_preview()
                return
            profiles = self._signature.list_user_signature_templates(user.user_id)
            selected = next((p for p in profiles if p.name == selected_name), None)
            if selected is None:
                return
            self._profile_name.setText(selected.name)
            self._asset_id.setText(selected.signature_asset_id or "")
            self._page_index.setText(str(selected.placement.page_index))
            self._x.setText(str(selected.placement.x))
            self._y.setText(str(selected.placement.y))
            self._width.setText(str(selected.placement.target_width))
            self._show_name.setChecked(selected.layout.show_name)
            self._show_date.setChecked(selected.layout.show_date)
            self._name_pos.setCurrentText(selected.layout.name_position)
            self._date_pos.setCurrentText(selected.layout.date_position)
            self._render_preview()
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _render_preview(self) -> None:
        self._preview.setPlainText(
            "\n".join(
                [
                    f"Profil: {self._profile_name.text().strip() or 'Neu'}",
                    f"Seite: {self._page_index.text().strip()}",
                    f"Position: x={self._x.text().strip()}, y={self._y.text().strip()}",
                    f"Breite: {self._width.text().strip()}",
                    f"Name: {'an' if self._show_name.isChecked() else 'aus'} ({self._name_pos.currentText()})",
                    f"Datum: {'an' if self._show_date.isChecked() else 'aus'} ({self._date_pos.currentText()})",
                ]
            )
        )

    def _open_canvas(self) -> None:
        dialog = SignatureCanvasDialog(self)
        dialog.exec()
        user = self._um.get_current_user()
        if user is not None and dialog.signature_bytes() is not None:
            asset = self._signature.import_signature_asset_bytes(
                user.user_id,
                dialog.signature_bytes(),
                filename_hint="settings-canvas.png",
            )
            self._asset_id.setText(asset.asset_id)
            password = self._replace_password.text().strip() or None
            self._signature.set_active_signature_asset(user.user_id, asset.asset_id, password=password)
            self._refresh_active_signature()
            self._append("AKTIVE_SIGNATUR_AKTUALISIERT", {"asset_id": asset.asset_id})
        saved = dialog.saved_path()
        if saved is not None:
            self._asset_id.setText(str(saved))
            self._append("SIGNATUR_CANVAS_GESPEICHERT", {"asset_path": str(saved)})

    def _refresh_active_signature(self) -> None:
        user = self._um.get_current_user()
        if user is None:
            self._active_asset.clear()
            return
        asset_id = self._signature.get_active_signature_asset_id(user.user_id)
        self._active_asset.setText(asset_id or "-")

    def _set_active_signature_asset(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            asset_id = self._asset_id.text().strip()
            if not asset_id:
                raise RuntimeError("Asset-ID erforderlich")
            password = self._replace_password.text().strip() or None
            self._signature.set_active_signature_asset(user.user_id, asset_id, password=password)
            self._refresh_active_signature()
            self._append("AKTIVE_SIGNATUR_GESETZT", {"asset_id": asset_id})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signatur aktiv", str(exc))

    def _export_active_signature(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            path = Path(self._container.get_port("app_home")) / "storage" / "signature" / f"{user.user_id}_active_signature.png"
            exported = self._signature.export_active_signature(user.user_id, path)
            self._append("AKTIVE_SIGNATUR_EXPORTIERT", {"path": str(exported)})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signatur exportieren", str(exc))

    def _clear_active_signature(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            password = self._replace_password.text().strip() or None
            self._signature.clear_active_signature(user.user_id, password=password)
            self._refresh_active_signature()
            self._append("AKTIVE_SIGNATUR_GELOESCHT", {"user_id": user.user_id})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signatur löschen", str(exc))

    def _load_global_profiles(self) -> None:
        try:
            self._global_profile_select.clear()
            self._global_profile_select.addItem("Global wählen", "")
            for profile in self._signature.list_global_signature_templates():
                self._global_profile_select.addItem(profile.name, profile.template_id)
            self._append("GLOBAL_PROFILE_GELADEN", {"count": self._global_profile_select.count() - 1})
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _create_global_profile(self) -> None:
        try:
            self._require_privileged()
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            created = self._signature.create_user_signature_template(
                owner_user_id=user.user_id,
                name=self._global_profile_name.text().strip(),
                placement=self._build_placement(),
                layout=self._build_layout(),
                signature_asset_id=self._asset_id.text().strip() or None,
                scope="global",
            )
            self._append("GLOBAL_PROFIL_ANGELEGT", {"template_id": created.template_id, "name": created.name})
            self._load_global_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Globales Profil", str(exc))

    def _delete_global_profile(self) -> None:
        try:
            self._require_privileged()
            template_id = self._global_profile_select.currentData()
            if not template_id:
                raise RuntimeError("Bitte globales Profil wählen")
            self._signature.delete_signature_template(str(template_id))
            self._append("GLOBAL_PROFIL_GELOESCHT", {"template_id": template_id})
            self._load_global_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Globales Profil", str(exc))

    def _copy_global_to_user(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            template_id = self._global_profile_select.currentData()
            if not template_id:
                raise RuntimeError("Bitte globales Profil wählen")
            copied = self._signature.copy_global_template_to_user(str(template_id), user.user_id)
            self._append("GLOBAL_NACH_USER_KOPIERT", {"template_id": copied.template_id, "name": copied.name})
            self._load_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Globales Profil kopieren", str(exc))


class _LicenseManagementWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._license = container.get_port("license_service")
        self._um = container.get_port("usermanagement_service")
        self._license_path = QLineEdit()
        self._license_text = QPlainTextEdit()
        self._status_table = QTableWidget(0, 3)
        self._status_table.setHorizontalHeaderLabels(["Modul", "Status", "Hinweis"])
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Lizenzverwaltung (GUI-only): Lizenzdatei laden/speichern und Modulstatus sichtbar machen. "
            "Eine Runtime-Recovery bei fehlender Lizenz wird hier nicht durchgeführt."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        form.addRow("Lizenzdatei", self._license_path)
        layout.addLayout(form)
        actions = QHBoxLayout()
        btn_reload = QPushButton("Lizenz laden")
        btn_reload.clicked.connect(self._load_license)
        btn_save = QPushButton("Lizenz speichern")
        btn_save.clicked.connect(self._save_license)
        btn_status = QPushButton("Modulstatus aktualisieren")
        btn_status.clicked.connect(self._render_status)
        actions.addWidget(btn_reload)
        actions.addWidget(btn_save)
        actions.addWidget(btn_status)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addWidget(self._license_text, stretch=1)
        layout.addWidget(self._status_table, stretch=1)
        layout.addWidget(self._out, stretch=1)
        self._load_license()
        self._render_status()

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}\n{as_json_text(payload)}\n")

    def _license_file(self) -> Path:
        raw = self._license_path.text().strip()
        if raw:
            return Path(raw)
        return Path(self._license.license_file)

    def _load_license(self) -> None:
        try:
            path = Path(self._license.license_file)
            self._license_path.setText(str(path))
            self._license_text.setPlainText(path.read_text(encoding="utf-8"))
            self._append("LIZENZ_GELADEN", {"path": str(path)})
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _save_license(self) -> None:
        try:
            self._require_privileged()
            path = self._license_file()
            parsed = json.loads(self._license_text.toPlainText().strip() or "{}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(parsed, indent=2, ensure_ascii=True), encoding="utf-8")
            self._append("LIZENZ_GESPEICHERT", {"path": str(path)})
            self._render_status()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Lizenzverwaltung", str(exc))

    def _render_status(self) -> None:
        modules = [
            ("signature", "signature", []),
            ("documents", "documents", ["signature"]),
            ("training", None, []),
            ("registry", None, []),
            ("usermanagement", None, []),
        ]
        rows = []
        for module_id, tag, depends_on in modules:
            if tag is None:
                rows.append((module_id, "verfügbar", "keine Lizenzpflicht"))
                continue
            try:
                allowed = bool(self._license.is_module_allowed(tag))
            except Exception as exc:  # noqa: BLE001
                rows.append((module_id, "lizenz fehlt", f"prüfen fehlgeschlagen: {exc}"))
                continue
            if allowed:
                rows.append((module_id, "verfügbar", f"abhängig von: {', '.join(depends_on) if depends_on else '-'}"))
            else:
                rows.append((module_id, "lizenz fehlt", f"Tag '{tag}' nicht freigeschaltet"))
        for idx, (module_id, status, hint) in enumerate(rows):
            if status == "verfügbar":
                continue
            for dep_idx, (m2, s2, _h2) in enumerate(rows):
                if module_id in ("documents",) and m2 == "signature" and s2 != "verfügbar":
                    rows[idx] = (module_id, "abhängig blockiert", "Abhängigkeit 'signature' nicht verfügbar")
                    break
        self._status_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                self._status_table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        self._status_table.resizeColumnsToContents()
        self._append("MODULSTATUS", {"rows": rows})


class SettingsAdminWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._um = container.get_port("usermanagement_service")
        self._tabs = QTabWidget()
        self._sections: list[tuple[str, QWidget]] = []
        self._populate_sections()

        layout = QVBoxLayout(self)
        header = QLabel(
            "Einstellungen als zentraler Bereich mit horizontalen Reitern und rollenabhängigen Inhalten."
        )
        header.setWordWrap(True)
        layout.addWidget(header)
        layout.addWidget(self._tabs, stretch=1)

    def _populate_sections(self) -> None:
        user = self._um.get_current_user()
        role = normalize_role(user.role) if user is not None else ""

        self._add_section("Profil / Mein Benutzer", _ProfileWidget(self._container))
        self._add_section("Signatur", _SignatureSettingsWidget(self._container))
        if role in ("ADMIN", "QMB"):
            self._add_section("Benutzerverwaltung", UsersAdminWidget(self._container))
            self._add_section("Lizenzverwaltung", _LicenseManagementWidget(self._container))
            self._add_section("Workflow-Profile", _WorkflowProfilesWidget(self._container))
        if role == "ADMIN":
            self._add_section("Modul-Einstellungen", _ModuleSettingsWidget(self._container))
            self._add_section("Geplante Optionen", _PlannedOptionsWidget())

    def _add_section(self, title: str, widget: QWidget) -> None:
        self._sections.append((title, widget))
        self._tabs.addTab(widget, title)


class _PlannedOptionsWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Bereich", "Option", "Priorität", "Status", "Abhängigkeit vom API-Vertrag"]
        )
        rows = [
            ("Profil", "Anzeigename bearbeiten", "hoch", "in pruefung", "usermanagement_service: kein Feld"),
            ("Profil", "E-Mail bearbeiten", "hoch", "in pruefung", "usermanagement_service: kein Feld"),
            ("Profil", "Abteilung bearbeiten", "mittel", "geplant", "usermanagement_service: kein Feld"),
            ("Benutzerverwaltung", "Status aktiv/inaktiv", "mittel", "geplant", "user status API fehlt"),
            ("Benutzerverwaltung", "Abteilung pro Benutzer", "mittel", "geplant", "department field API fehlt"),
            ("Benutzerverwaltung", "Rolle bestehender Benutzer ändern", "hoch", "in pruefung", "update-role API fehlt"),
        ]
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(value))
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()

        out = QPlainTextEdit()
        out.setReadOnly(True)
        out.setPlainText(
            as_json_text(
                {
                    "hinweis": "Geplante Optionen sind bewusst readonly und inventarisieren moegliche Erweiterungen ohne neue Fachlogik.",
                    "prioritaet_erklaerung": {"hoch": "relevant fuer naechste Iteration", "mittel": "nachrangig"},
                }
            )
        )
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Geplante Optionen (readonly, priorisiert)"))
        layout.addWidget(table, stretch=1)
        layout.addWidget(out, stretch=1)


def _build(container: RuntimeContainer) -> QWidget:
    return SettingsAdminWidget(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="platform.settings_admin",
            module_id="settings",
            title="Einstellungen",
            sort_order=50,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
