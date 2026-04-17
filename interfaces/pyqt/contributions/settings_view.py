from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap

from interfaces.pyqt.contributions.common import as_json_text, normalize_role
from interfaces.pyqt.presenters.settings_presenter import SettingsProfilePresenter
from interfaces.pyqt.presenters.settings_policy_presenter import SettingsPolicyPresenter
from interfaces.pyqt.contributions.users_view import UsersAdminWidget
from interfaces.pyqt.widgets.access_guards import require_admin_or_qmb
from interfaces.pyqt.widgets.signature_canvas_dialog import SignatureCanvasDialog
from interfaces.pyqt.widgets.signature_placement_dialog import SignaturePlacementDialog, compute_label_local_position
from interfaces.pyqt.widgets.workflow_profile_wizard import WorkflowProfileWizardDialog
from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput
from modules.documents.contracts import DocumentType
from interfaces.pyqt.registry.contribution import QtModuleContribution
from qm_platform.runtime.container import RuntimeContainer
from modules.usermanagement.role_policies import is_effective_qmb


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
        self._first_name = QLineEdit()
        self._last_name = QLineEdit()
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
        konto.addRow("Loginname", self._username)
        konto.addRow("User-ID (stabil)", self._user_id)
        konto.addRow("Rolle", self._role)
        layout.addWidget(QLabel("Konto"))
        layout.addLayout(konto)

        org = QFormLayout()
        org.addRow("Vorname", self._first_name)
        org.addRow("Nachname", self._last_name)
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
        first = (getattr(self._session_user, "first_name", None) or "").strip()
        last = (getattr(self._session_user, "last_name", None) or "").strip()
        if not first and not last:
            legacy = (getattr(self._session_user, "display_name", None) or "").strip()
            if "," in legacy:
                first, last = [p.strip() for p in legacy.split(",", 1)]
            elif legacy:
                parts = legacy.split()
                first = parts[0]
                last = " ".join(parts[1:]) if len(parts) > 1 else ""
        self._first_name.setText(first)
        self._last_name.setText(last)
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
            first_name = self._first_name.text().strip() or None
            last_name = self._last_name.text().strip() or None
            email = self._email.text().strip() or None

            profile_changed = (
                (getattr(self._session_user, "first_name", None) or None) != first_name
                or (getattr(self._session_user, "last_name", None) or None) != last_name
                or (self._session_user.email or None) != email
            )
            pw_changed = bool(current_pw or new_pw or confirm_pw)

            if not profile_changed and not pw_changed:
                self._out.setPlainText("Keine Änderungen erkannt.")
                return

            if profile_changed:
                self._um.update_user_profile(
                    self._session_user.username,
                    first_name=first_name,
                    last_name=last_name,
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
        btn_wizard = QPushButton("Profil-Assistent")
        btn_wizard.clicked.connect(self._open_wizard)
        btn_save = QPushButton("Profile speichern")
        btn_save.clicked.connect(self._save)
        tools.addWidget(btn_reload)
        tools.addWidget(btn_wizard)
        tools.addWidget(btn_save)
        tools.addStretch(1)
        layout.addLayout(tools)
        layout.addWidget(self._editor, stretch=1)
        layout.addWidget(QLabel("Ergebnis"))
        layout.addWidget(self._out, stretch=1)
        self._reload()

    def _require_privileged(self) -> None:
        user = self._um.get_current_user()
        role = normalize_role(user.role) if user is not None else ""
        if role != "ADMIN":
            raise RuntimeError("Nur Admin darf Workflow-Profile bearbeiten")

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

    def _open_wizard(self) -> None:
        try:
            self._require_privileged()
            dialog = WorkflowProfileWizardDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            payload = dialog.payload()
            if not payload.profile_id:
                raise RuntimeError("Profil-ID ist erforderlich")
            current = json.loads(self._editor.toPlainText().strip() or "{}")
            profiles = list(current.get("profiles", []))
            profiles = [p for p in profiles if str(p.get("profile_id", "")) != payload.profile_id]
            profiles.append(payload.as_json_dict())
            current["profiles"] = profiles
            self._editor.setPlainText(json.dumps(current, indent=2, ensure_ascii=True))
            self._out.setPlainText(as_json_text({"status": "wizard_ok", "profile_id": payload.profile_id}))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Workflow-Profile", str(exc))


class _ModuleSettingsWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._svc = container.get_port("settings_service")
        self._registry = self._svc.registry
        self._policy = SettingsPolicyPresenter()

        self._module = QComboBox()
        for mid in sorted(str(m) for m in self._registry.list_module_ids()):
            self._module.addItem(mid)

        self._editor = QPlainTextEdit()
        self._ack = QCheckBox("Governance-kritische Einstellungsänderungen bestätigen")
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._hint = QLabel("Bearbeitbares JSON fuer Modul-Einstellungen. Speichern nur fuer QMB/Admin.")
        self._hint.setWordWrap(True)
        self._create_perm_box = QWidget()
        create_perm_layout = QVBoxLayout(self._create_perm_box)
        create_perm_layout.setContentsMargins(0, 0, 0, 0)
        create_perm_layout.addWidget(QLabel("Dokumentenlenkung: CanCreateNewDocuments (pro Nutzer)"))
        self._create_perm_table = QTableWidget(0, 3)
        self._create_perm_table.setHorizontalHeaderLabels(["User-ID", "Rolle", "CanCreateNewDocuments"])
        self._create_perm_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._create_perm_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._create_perm_table.horizontalHeader().setStretchLastSection(True)
        self._create_perm_table.itemClicked.connect(self._on_toggle_item_clicked)
        create_perm_layout.addWidget(self._create_perm_table)
        self._btn_apply_perm = QPushButton("Toggle-Auswahl ins JSON übernehmen")
        self._btn_apply_perm.clicked.connect(self._apply_create_permissions_to_editor)
        create_perm_layout.addWidget(self._btn_apply_perm)
        self._create_perm_box.setVisible(False)
        self._doc_type_rule_box = QWidget()
        doc_rule_layout = QVBoxLayout(self._doc_type_rule_box)
        doc_rule_layout.setContentsMargins(0, 0, 0, 0)
        doc_rule_layout.addWidget(QLabel("Dokumenttyp -> Workflowprofil Regeln"))
        self._doc_type_rule_table = QTableWidget(0, 3)
        self._doc_type_rule_table.setHorizontalHeaderLabels(["Dokumenttyp", "Default Workflowprofil", "Override possible"])
        self._doc_type_rule_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._doc_type_rule_table.horizontalHeader().setStretchLastSection(True)
        self._doc_type_rule_table.itemClicked.connect(self._on_toggle_item_clicked)
        doc_rule_layout.addWidget(self._doc_type_rule_table)
        self._btn_apply_doc_rules = QPushButton("Typ-Regeln ins JSON übernehmen")
        self._btn_apply_doc_rules.clicked.connect(self._apply_doc_type_rules_to_editor)
        doc_rule_layout.addWidget(self._btn_apply_doc_rules)
        self._doc_type_rule_box.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self._hint)
        layout.addWidget(self._module)
        layout.addWidget(self._create_perm_box)
        layout.addWidget(self._doc_type_rule_box)

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
        self._render_create_permissions(module_id, data)
        self._render_doc_type_profile_rules(module_id, data)
        self._append("GELADEN", {"module_id": module_id, "settings": data})

    def _save_selected(self) -> None:
        module_id = self._module.currentText().strip()
        if not module_id:
            return
        try:
            self._require_privileged()
            self._apply_create_permissions_to_editor()
            self._apply_doc_type_rules_to_editor()
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

    def _render_create_permissions(self, module_id: str, settings: dict[str, object]) -> None:
        is_documents = module_id == "documents"
        self._create_perm_box.setVisible(is_documents)
        if not is_documents:
            return
        try:
            users = self._container.get_port("usermanagement_service").list_users()
        except Exception:
            users = []
        mapping_raw = settings.get("can_create_new_documents", {})
        mapping = mapping_raw if isinstance(mapping_raw, dict) else {}
        self._create_perm_table.setRowCount(len(users))
        for row_idx, user in enumerate(users):
            user_id = str(getattr(user, "user_id", ""))
            role = str(getattr(user, "role", ""))
            allowed = bool(mapping.get(user_id, False))
            self._create_perm_table.setItem(row_idx, 0, QTableWidgetItem(user_id))
            self._create_perm_table.setItem(row_idx, 1, QTableWidgetItem(role))
            self._create_perm_table.setItem(row_idx, 2, self._make_toggle_cell(allowed))
        self._create_perm_table.resizeColumnsToContents()

    def _workflow_profile_ids(self) -> list[str]:
        try:
            docs_cfg = self._svc.get_module_settings("documents")
            raw = str(docs_cfg.get("profiles_file", "modules/documents/workflow_profiles.json")).strip()
            app_home = self._container.get_port("app_home")
            path = Path(raw)
            if not path.is_absolute():
                path = Path(app_home) / path
            if not path.exists():
                return ["long_release"]
            payload = json.loads(path.read_text(encoding="utf-8"))
            ids = [str(item.get("profile_id", "")).strip() for item in payload.get("profiles", [])]
            ids = [v for v in ids if v]
            return sorted(set(ids)) or ["long_release"]
        except Exception:
            return ["long_release"]

    def _render_doc_type_profile_rules(self, module_id: str, settings: dict[str, object]) -> None:
        is_documents = module_id == "documents"
        self._doc_type_rule_box.setVisible(is_documents)
        if not is_documents:
            return
        mapping_raw = settings.get("doc_type_profile_rules", {})
        mapping = mapping_raw if isinstance(mapping_raw, dict) else {}
        profile_ids = self._workflow_profile_ids()
        types = list(DocumentType)
        self._doc_type_rule_table.setRowCount(len(types))
        for row_idx, dt in enumerate(types):
            rule = mapping.get(dt.value, {})
            profile_id = str((rule.get("profile_id") if isinstance(rule, dict) else "") or "long_release")
            override = bool(rule.get("override_possible", False)) if isinstance(rule, dict) else False
            self._doc_type_rule_table.setItem(row_idx, 0, QTableWidgetItem(dt.value))
            combo = QComboBox()
            combo.addItems(profile_ids)
            if combo.findText(profile_id) < 0:
                combo.addItem(profile_id)
            combo.setCurrentIndex(combo.findText(profile_id))
            self._doc_type_rule_table.setCellWidget(row_idx, 1, combo)
            self._doc_type_rule_table.setItem(row_idx, 2, self._make_toggle_cell(override))
        self._doc_type_rule_table.resizeColumnsToContents()

    def _apply_create_permissions_to_editor(self) -> None:
        if self._module.currentText().strip() != "documents" or not self._create_perm_box.isVisible():
            return
        payload = json.loads(self._editor.toPlainText().strip() or "{}")
        if not isinstance(payload, dict):
            raise RuntimeError("Einstellungs-Payload muss ein JSON-Objekt sein")
        mapping: dict[str, bool] = {}
        for row_idx in range(self._create_perm_table.rowCount()):
            user_item = self._create_perm_table.item(row_idx, 0)
            check_item = self._create_perm_table.item(row_idx, 2)
            if user_item is None or check_item is None:
                continue
            user_id = user_item.text().strip()
            if not user_id:
                continue
            mapping[user_id] = self._toggle_cell_value(check_item)
        payload["can_create_new_documents"] = mapping
        self._editor.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))

    def _apply_doc_type_rules_to_editor(self) -> None:
        if self._module.currentText().strip() != "documents" or not self._doc_type_rule_box.isVisible():
            return
        payload = json.loads(self._editor.toPlainText().strip() or "{}")
        if not isinstance(payload, dict):
            raise RuntimeError("Einstellungs-Payload muss ein JSON-Objekt sein")
        rules: dict[str, dict[str, object]] = {}
        for row_idx in range(self._doc_type_rule_table.rowCount()):
            dt_item = self._doc_type_rule_table.item(row_idx, 0)
            ov_item = self._doc_type_rule_table.item(row_idx, 2)
            combo = self._doc_type_rule_table.cellWidget(row_idx, 1)
            if dt_item is None or ov_item is None or not isinstance(combo, QComboBox):
                continue
            rules[dt_item.text().strip()] = {
                "profile_id": combo.currentText().strip() or "long_release",
                "override_possible": self._toggle_cell_value(ov_item),
            }
        payload["doc_type_profile_rules"] = rules
        self._editor.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))

    def _make_toggle_cell(self, active: bool) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole, bool(active))
        if active:
            item.setText("✓")
            item.setForeground(QColor("#1B8E3E"))
        else:
            item.setText("⊘")
            item.setForeground(QColor("#C62828"))
        return item

    @staticmethod
    def _toggle_cell_value(item: QTableWidgetItem) -> bool:
        return bool(item.data(Qt.ItemDataRole.UserRole))

    def _flip_toggle_cell(self, item: QTableWidgetItem) -> None:
        active = not self._toggle_cell_value(item)
        item.setData(Qt.ItemDataRole.UserRole, active)
        if active:
            item.setText("✓")
            item.setForeground(QColor("#1B8E3E"))
        else:
            item.setText("⊘")
            item.setForeground(QColor("#C62828"))

    def _on_toggle_item_clicked(self, item: QTableWidgetItem) -> None:
        if item.column() != 2:
            return
        table = item.tableWidget()
        if table not in {self._create_perm_table, self._doc_type_rule_table}:
            return
        self._flip_toggle_cell(item)


class _TrainingSettingsWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._settings = container.get_port("settings_service")
        self._um = container.get_port("usermanagement_service")

        self._questions = QSpinBox()
        self._questions.setRange(1, 100)
        self._min_correct = QSpinBox()
        self._min_correct.setRange(1, 100)
        self._cooldown = QSpinBox()
        self._cooldown.setRange(0, 86400)
        self._shuffle = QPushButton()
        self._shuffle.setCheckable(True)
        self._reread = QPushButton()
        self._reread.setCheckable(True)
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setMaximumHeight(100)

        form = QFormLayout()
        form.addRow("Fragen pro Quiz", self._questions)
        form.addRow("Mindestens richtige Antworten", self._min_correct)
        form.addRow("Cooldown nach Fehlversuch (Sekunden)", self._cooldown)
        form.addRow("Antworten mischen", self._shuffle)
        form.addRow("Nach Fehlversuch erneutes Lesen erzwingen", self._reread)

        row = QHBoxLayout()
        btn_save = QPushButton("Speichern")
        btn_save.clicked.connect(self._save)
        btn_reload = QPushButton("Zuruecksetzen")
        btn_reload.clicked.connect(self._reload)
        row.addWidget(btn_save)
        row.addWidget(btn_reload)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(row)
        layout.addWidget(self._out)

        self._questions.valueChanged.connect(self._sync_min_bounds)
        self._shuffle.toggled.connect(lambda checked: self._apply_toggle_style(self._shuffle, checked))
        self._reread.toggled.connect(lambda checked: self._apply_toggle_style(self._reread, checked))
        self._reload()

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _sync_min_bounds(self) -> None:
        self._min_correct.setMaximum(self._questions.value())
        if self._min_correct.value() > self._questions.value():
            self._min_correct.setValue(self._questions.value())

    @staticmethod
    def _apply_toggle_style(button: QPushButton, active: bool) -> None:
        if active:
            button.setText("✓ aktiv")
            button.setStyleSheet("color: #1B8E3E;")
        else:
            button.setText("⊘ inaktiv")
            button.setStyleSheet("color: #C62828;")

    def _reload(self) -> None:
        cfg = self._settings.get_module_settings("training")
        questions = int(cfg.get("questions_per_quiz", 3) or 3)
        min_correct = int(cfg.get("min_correct_answers", questions) or questions)
        self._questions.setValue(max(1, questions))
        self._sync_min_bounds()
        self._min_correct.setValue(max(1, min(min_correct, self._questions.value())))
        self._cooldown.setValue(max(0, int(cfg.get("retry_cooldown_seconds", 0) or 0)))
        self._shuffle.setChecked(bool(cfg.get("shuffle_answers", True)))
        self._reread.setChecked(bool(cfg.get("force_reread_on_fail", False)))
        self._apply_toggle_style(self._shuffle, self._shuffle.isChecked())
        self._apply_toggle_style(self._reread, self._reread.isChecked())
        self._out.setPlainText("Schulungseinstellungen geladen.")

    def _save(self) -> None:
        try:
            self._require_privileged()
            payload = self._settings.get_module_settings("training")
            payload["questions_per_quiz"] = int(self._questions.value())
            payload["min_correct_answers"] = int(min(self._min_correct.value(), self._questions.value()))
            payload["retry_cooldown_seconds"] = int(self._cooldown.value())
            payload["shuffle_answers"] = bool(self._shuffle.isChecked())
            payload["force_reread_on_fail"] = bool(self._reread.isChecked())
            self._settings.set_module_settings("training", payload, acknowledge_governance_change=False)
            self._out.setPlainText("Schulungseinstellungen gespeichert.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Schulungseinstellungen", str(exc))


class _SignatureSettingsWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._settings = container.get_port("settings_service")
        self._signature = container.get_port("signature_api")
        self._um = container.get_port("usermanagement_service")
        current_user = self._um.get_current_user()
        self._is_admin = normalize_role(current_user.role) == "ADMIN" if current_user is not None else False
        self._profiles_cache: dict[str, object] = {}
        self._current_profile_placement = SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0)
        self._current_profile_layout = LabelLayoutInput()

        self._require_password = QCheckBox("Passwort für Signaturvorgänge erforderlich")
        self._default_mode = QComboBox()
        self._default_mode.addItems(["visual", "crypto", "both"])
        # Dry-Run setting (Admin only, persisted in settings DB)
        self._dry_run_off = QRadioButton("Scharf signieren (empfohlen — echte Signatur)")
        self._dry_run_on = QRadioButton("Testmodus aktiv (Dry-Run — keine echte Signatur erzeugt)")
        self._dry_run_off.setChecked(True)
        self._dry_run_group = QButtonGroup(self)
        self._dry_run_group.addButton(self._dry_run_off, 0)
        self._dry_run_group.addButton(self._dry_run_on, 1)
        self._templates_db = QLineEdit()
        self._assets_root = QLineEdit()
        self._master_key = QLineEdit()

        self._profile_name = QLineEdit("standard")
        self._profile_select = QComboBox()
        self._profiles_table = QTableWidget(0, 4)
        self._profiles_table.setHorizontalHeaderLabels(["Profil", "Seite", "Position", "Layout"])
        self._profiles_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._profiles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._profiles_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._profiles_table.setAlternatingRowColors(True)
        self._profiles_table.setSortingEnabled(True)
        self._profiles_table.horizontalHeader().setStretchLastSection(True)
        self._active_asset = QLineEdit()
        self._active_asset.setReadOnly(True)
        self._replace_password = QLineEdit()
        self._replace_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._global_profile_select = QComboBox()
        self._global_profile_name = QLineEdit("global-standard")

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview_canvas = QLabel()
        self._preview_canvas.setMinimumHeight(220)
        self._preview_sig_pixmap: QPixmap | None = None
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        layout = QVBoxLayout(self)
        self._global_settings_box = QWidget()
        global_box_layout = QVBoxLayout(self._global_settings_box)
        global_box_layout.setContentsMargins(0, 0, 0, 0)
        global_box_layout.addWidget(QLabel("Signatur-Einstellungen (global)"))
        global_form = QFormLayout()
        global_form.addRow("", self._require_password)
        global_form.addRow("Default-Modus", self._default_mode)
        global_form.addRow("Signiermodus", self._dry_run_off)
        global_form.addRow("", self._dry_run_on)
        global_form.addRow("templates_db_path", self._templates_db)
        global_form.addRow("assets_root", self._assets_root)
        global_form.addRow("master_key_path", self._master_key)
        global_box_layout.addLayout(global_form)
        global_btn = QHBoxLayout()
        btn_reload = QPushButton("Signatur-Settings laden")
        btn_reload.clicked.connect(self._load_settings)
        btn_save = QPushButton("Signatur-Settings speichern")
        btn_save.clicked.connect(self._save_settings)
        global_btn.addWidget(btn_reload)
        global_btn.addWidget(btn_save)
        global_btn.addStretch(1)
        global_box_layout.addLayout(global_btn)
        layout.addWidget(self._global_settings_box)

        layout.addWidget(QLabel("Signaturprofile"))
        profile_form = QFormLayout()
        profile_form.addRow("Profil wählen", self._profile_select)
        profile_form.addRow("Neuer Profilname", self._profile_name)
        profile_form.addRow("Aktive Asset-ID", self._active_asset)
        profile_form.addRow("Passwort (ersetzen/löschen)", self._replace_password)
        layout.addLayout(profile_form)
        layout.addWidget(self._profiles_table)
        profile_btn = QHBoxLayout()
        btn_create = QPushButton("Profil anlegen")
        btn_create.clicked.connect(self._create_profile_via_editor)
        btn_edit = QPushButton("Profil im Editor bearbeiten")
        btn_edit.clicked.connect(self._edit_profile_via_editor)
        btn_canvas = QPushButton("Signatur zeichnen")
        btn_canvas.clicked.connect(self._open_canvas)
        btn_import = QPushButton("Signatur importieren")
        btn_import.clicked.connect(self._import_and_set_active_signature)
        btn_delete = QPushButton("Profil löschen")
        btn_delete.clicked.connect(self._delete_profile)
        btn_clear_active = QPushButton("Aktive Signatur löschen")
        btn_clear_active.clicked.connect(self._clear_active_signature)
        profile_btn.addWidget(btn_create)
        profile_btn.addWidget(btn_edit)
        profile_btn.addWidget(btn_canvas)
        profile_btn.addWidget(btn_import)
        profile_btn.addWidget(btn_delete)
        profile_btn.addWidget(btn_clear_active)
        profile_btn.addStretch(1)
        layout.addLayout(profile_btn)

        self._global_templates_box = QWidget()
        global_tpl_layout = QVBoxLayout(self._global_templates_box)
        global_tpl_layout.setContentsMargins(0, 0, 0, 0)
        global_tpl_layout.addWidget(QLabel("Globale Templates (Admin)"))
        global_form = QFormLayout()
        global_form.addRow("Global wählen", self._global_profile_select)
        global_form.addRow("Neuer globaler Name", self._global_profile_name)
        global_tpl_layout.addLayout(global_form)
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
        global_tpl_layout.addLayout(global_btn)
        layout.addWidget(self._global_templates_box)

        layout.addWidget(QLabel("Preview"))
        layout.addWidget(self._preview_canvas)
        layout.addWidget(self._preview, stretch=1)
        self._debug_box = QWidget()
        debug_layout = QVBoxLayout(self._debug_box)
        debug_layout.setContentsMargins(0, 0, 0, 0)
        debug_layout.addWidget(QLabel("Ergebnis"))
        debug_layout.addWidget(self._out, stretch=1)
        layout.addWidget(self._debug_box)

        self._global_settings_box.setVisible(self._is_admin)
        self._global_templates_box.setVisible(self._is_admin)
        self._debug_box.setVisible(self._is_admin)

        self._profile_select.currentTextChanged.connect(lambda _text: self._apply_selected_profile())
        self._profiles_table.itemSelectionChanged.connect(self._on_profile_table_select)
        self._load_settings()
        self._load_profiles()
        if self._is_admin:
            self._load_global_profiles()
        self._refresh_active_signature()

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}\n{as_json_text(payload)}\n")

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _load_settings(self) -> None:
        if not self._is_admin:
            return
        cfg = self._settings.get_module_settings("signature")
        self._require_password.setChecked(bool(cfg.get("require_password", True)))
        mode = str(cfg.get("default_mode", "visual"))
        idx = self._default_mode.findText(mode)
        if idx >= 0:
            self._default_mode.setCurrentIndex(idx)
        self._templates_db.setText(str(cfg.get("templates_db_path", "")))
        self._assets_root.setText(str(cfg.get("assets_root", "")))
        self._master_key.setText(str(cfg.get("master_key_path", "")))
        dry_run = bool(cfg.get("dry_run_enabled", False))
        self._dry_run_on.setChecked(dry_run)
        self._dry_run_off.setChecked(not dry_run)
        self._append("SIGNATUR_SETTINGS_GELADEN", cfg)

    def _save_settings(self) -> None:
        try:
            if not self._is_admin:
                raise RuntimeError("Nur Admins dürfen globale Signatur-Einstellungen ändern.")
            self._require_privileged()
            payload = {
                "require_password": self._require_password.isChecked(),
                "default_mode": self._default_mode.currentText(),
                "dry_run_enabled": self._dry_run_on.isChecked(),
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
            self._profiles_cache = {p.template_id: p for p in profiles}
            self._profile_select.clear()
            self._profile_select.addItem("Neues Profil", "")
            for profile in profiles:
                self._profile_select.addItem(profile.name, profile.template_id)
            self._profiles_table.setSortingEnabled(False)
            self._profiles_table.setRowCount(len(profiles))
            for row, profile in enumerate(profiles):
                self._profiles_table.setItem(row, 0, QTableWidgetItem(profile.name))
                self._profiles_table.setItem(row, 1, QTableWidgetItem(str(profile.placement.page_index)))
                self._profiles_table.setItem(
                    row,
                    2,
                    QTableWidgetItem(
                        f"x={profile.placement.x:.1f}, y={profile.placement.y:.1f}, w={profile.placement.target_width:.1f}"
                    ),
                )
                self._profiles_table.setItem(
                    row,
                    3,
                    QTableWidgetItem(
                        f"Name:{'an' if profile.layout.show_name else 'aus'} | Datum:{'an' if profile.layout.show_date else 'aus'}"
                    ),
                )
                self._profiles_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, profile.template_id)
            self._profiles_table.resizeColumnsToContents()
            self._profiles_table.setSortingEnabled(True)
            self._profiles_table.sortItems(0, Qt.SortOrder.AscendingOrder)
            self._append("SIGNATUR_PROFILE_GELADEN", {"count": len(profiles)})
            self._refresh_active_signature()
            self._apply_selected_profile()
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _build_placement(self) -> SignaturePlacementInput:
        return self._current_profile_placement

    def _build_layout(self) -> LabelLayoutInput:
        return self._current_profile_layout

    def _create_profile_via_editor(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            profile_name = self._profile_name.text().strip()
            if not profile_name:
                raise RuntimeError("Bitte zuerst einen Profilnamen eingeben")
            pdf_path, _ = QFileDialog.getOpenFileName(self, "Vorschau-Dokument wählen", "", "PDF (*.pdf)")
            if not pdf_path:
                return
            dialog = SignaturePlacementDialog(
                input_pdf=Path(pdf_path),
                placement=self._current_profile_placement,
                layout=self._runtime_preview_layout(self._current_profile_layout),
                signature_pixmap=self._preview_sig_pixmap,
                template_save_callback=self._save_template_from_editor,
                template_list_provider=self._list_templates_for_editor,
                template_load_callback=self._load_template_for_editor,
                parent=self,
            )
            dialog.showFullScreen()
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            self._current_profile_placement = dialog.placement()
            self._current_profile_layout = replace(
                dialog.layout_result(),
                name_text=self._current_profile_layout.name_text,
                date_text=self._current_profile_layout.date_text,
            )
            created = self._signature.create_user_signature_template(
                owner_user_id=user.user_id,
                name=profile_name,
                placement=self._build_placement(),
                layout=self._build_layout(),
                signature_asset_id=self._signature.get_active_signature_asset_id(user.user_id),
                scope="user",
            )
            self._append("SIGNATUR_PROFIL_ANGELEGT", created)
            self._load_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signaturprofil", str(exc))

    def _edit_profile_via_editor(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            template_id = str(self._profile_select.currentData() or "").strip()
            if not template_id:
                raise RuntimeError("Bitte zuerst ein bestehendes Profil auswählen")
            selected = self._profiles_cache.get(template_id)
            if selected is None:
                raise RuntimeError("Ausgewähltes Profil konnte nicht geladen werden")
            pdf_path, _ = QFileDialog.getOpenFileName(self, "Vorschau-Dokument wählen", "", "PDF (*.pdf)")
            if not pdf_path:
                return
            dialog = SignaturePlacementDialog(
                input_pdf=Path(pdf_path),
                placement=selected.placement,
                layout=self._runtime_preview_layout(selected.layout),
                signature_pixmap=self._preview_sig_pixmap,
                template_save_callback=self._save_template_from_editor,
                template_list_provider=self._list_templates_for_editor,
                template_load_callback=self._load_template_for_editor,
                parent=self,
            )
            dialog.showFullScreen()
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            updated_name = self._profile_name.text().strip() or selected.name
            updated_layout = replace(
                dialog.layout_result(),
                name_text=selected.layout.name_text,
                date_text=selected.layout.date_text,
            )
            updated = self._signature.update_signature_template(
                template_id=template_id,
                owner_user_id=user.user_id,
                name=updated_name,
                placement=dialog.placement(),
                layout=updated_layout,
            )
            self._append("SIGNATUR_PROFIL_GEAENDERT", {"template_id": updated.template_id, "name": updated.name})
            self._load_profiles()
            idx = self._profile_select.findData(template_id)
            if idx >= 0:
                self._profile_select.setCurrentIndex(idx)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signaturprofil", str(exc))

    def _delete_profile(self) -> None:
        try:
            template_id = str(self._profile_select.currentData() or "").strip()
            if not template_id:
                raise RuntimeError("Bitte zuerst ein bestehendes Profil auswählen")
            self._signature.delete_signature_template(template_id)
            self._append("SIGNATUR_PROFIL_GELOESCHT", {"template_id": template_id})
            self._load_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signaturprofil", str(exc))

    def _on_profile_table_select(self) -> None:
        row = self._profiles_table.currentRow()
        if row < 0:
            return
        item = self._profiles_table.item(row, 0)
        if item is None:
            return
        template_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        idx = self._profile_select.findData(template_id)
        if idx >= 0:
            self._profile_select.setCurrentIndex(idx)

    def _apply_selected_profile(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                return
            selected_name = self._profile_select.currentText().strip()
            if not selected_name or selected_name == "Neues Profil":
                self._render_preview()
                return
            selected_id = str(self._profile_select.currentData() or "").strip()
            profiles = self._signature.list_user_signature_templates(user.user_id)
            selected = next((p for p in profiles if p.template_id == selected_id), None)
            if selected is None:
                return
            self._profile_name.setText(selected.name)
            self._current_profile_placement = selected.placement
            self._current_profile_layout = selected.layout
            self._render_preview()
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _render_preview(self) -> None:
        PREVIEW_W, PREVIEW_H = 520, 215
        pixmap = QPixmap(PREVIEW_W, PREVIEW_H)
        pixmap.fill(QColor("#e6e6e6"))
        painter = QPainter(pixmap)

        area_x, area_y = 20, 16
        area_w, area_h = 480, 180
        painter.fillRect(area_x, area_y, area_w, area_h, QColor("white"))
        painter.setPen(QPen(QColor("#7a7a7a"), 2))
        painter.drawRect(area_x, area_y, area_w, area_h)

        placement = self._current_profile_placement
        layout = self._runtime_preview_layout(self._current_profile_layout)

        # Settings preview shows composition only, not absolute page placement.
        scale = 1.0
        sig_w = max(1, int(placement.target_width * scale))
        sig_h = max(1, int(max(6.0, placement.target_width * 0.3) * scale))
        max_preview_width = int(area_w * 0.58)
        if sig_w > max_preview_width:
            scale = max_preview_width / max(1, sig_w)
            sig_w = max(1, int(placement.target_width * scale))
            sig_h = max(1, int(max(6.0, placement.target_width * 0.3) * scale))

        sig_x = area_x + max(12, int(area_w * 0.18))
        sig_y = area_y + max(18, int((area_h - sig_h) * 0.48))

        # --- Aktive Signatur anzeigen oder Platzhalter zeichnen ---
        if self._preview_sig_pixmap is not None:
            painter.drawPixmap(sig_x, sig_y, sig_w, sig_h, self._preview_sig_pixmap)
        else:
            painter.fillRect(sig_x, sig_y, sig_w, sig_h, QColor(255, 255, 255, 0))
            painter.setPen(QPen(QColor("#cc0000"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(sig_x, sig_y, max(1, sig_w - 1), max(1, sig_h - 1))

        # Rahmen der Signaturbox
        painter.setPen(QPen(QColor("#aaaaaa"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(sig_x, sig_y, sig_w, sig_h)

        name_pos = layout.name_position
        date_pos = layout.date_position
        name_fs = max(6, int(layout.name_font_size or 12))
        date_fs = max(6, int(layout.date_font_size or 12))
        color = QColor(layout.color_hex or "#000000")
        if not color.isValid():
            color = QColor("black")

        # --- Name-Label ---
        if layout.show_name and name_pos != "off":
            font = QFont()
            name_px = max(6, int(name_fs * scale * 0.85))
            font.setPixelSize(name_px)
            painter.setFont(font)
            painter.setPen(color)
            name_local = compute_label_local_position(
                position=name_pos,
                sig_height=float(sig_h),
                pixel_size=name_px,
                scale=scale,
                rel_x=layout.name_rel_x,
                rel_y=layout.name_rel_y,
                offset_above=layout.name_above,
                offset_below=layout.name_below,
                x_offset=layout.x_offset,
            )
            painter.drawText(
                int(sig_x + name_local.x()),
                int(sig_y + name_local.y() + name_px),
                layout.name_text or "",
            )

        # --- Datum-Label ---
        if layout.show_date and date_pos != "off":
            font = QFont()
            date_px = max(6, int(date_fs * scale * 0.85))
            font.setPixelSize(date_px)
            painter.setFont(font)
            painter.setPen(color)
            date_local = compute_label_local_position(
                position=date_pos,
                sig_height=float(sig_h),
                pixel_size=date_px,
                scale=scale,
                rel_x=layout.date_rel_x,
                rel_y=layout.date_rel_y,
                offset_above=layout.date_above,
                offset_below=layout.date_below,
                x_offset=layout.x_offset,
            )
            painter.drawText(
                int(sig_x + date_local.x()),
                int(sig_y + date_local.y() + date_px),
                layout.date_text or "",
            )

        painter.end()
        self._preview_canvas.setPixmap(pixmap)

        self._preview.setPlainText(
            "\n".join(
                [
                    f"Profil: {self._profile_name.text().strip() or 'Neu'}",
                    f"Gespeicherte Seite: {placement.page_index}",
                    f"Gespeicherte Position: x={placement.x}, y={placement.y}",
                    f"Signaturbreite: {placement.target_width}",
                    f"Name: {'an' if layout.show_name else 'aus'} ({name_pos}, {name_fs}pt)",
                    f"Datum: {'an' if layout.show_date else 'aus'} ({date_pos}, {date_fs}pt)",
                    f"Name rel: x={layout.name_rel_x if layout.name_rel_x is not None else '-'}, y={layout.name_rel_y if layout.name_rel_y is not None else '-'}",
                    f"Datum rel: x={layout.date_rel_x if layout.date_rel_x is not None else '-'}, y={layout.date_rel_y if layout.date_rel_y is not None else '-'}",
                ]
            )
        )

    def _current_user_display_name(self) -> str:
        user = self._um.get_current_user()
        if user is None:
            return ""
        first = (getattr(user, "first_name", None) or "").strip()
        last = (getattr(user, "last_name", None) or "").strip()
        if first and last:
            return f"{first}, {last}"
        if first:
            return first
        if last:
            return last
        return (getattr(user, "display_name", None) or user.username or user.user_id).strip()

    def _runtime_preview_layout(self, layout: LabelLayoutInput) -> LabelLayoutInput:
        return replace(
            layout,
            name_text=self._current_user_display_name() if layout.show_name else layout.name_text,
            date_text=datetime.now().strftime("%Y-%m-%d %H:%M:%S") if layout.show_date else layout.date_text,
        )

    def _save_template_from_editor(
        self,
        name: str,
        placement: SignaturePlacementInput,
        layout: LabelLayoutInput,
    ) -> object:
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        template_name = name.strip()
        if not template_name:
            raise RuntimeError("Vorlagenname fehlt")
        return self._signature.create_user_signature_template(
            owner_user_id=user.user_id,
            name=template_name,
            placement=placement,
            layout=layout,
            signature_asset_id=self._signature.get_active_signature_asset_id(user.user_id),
            scope="user",
        )

    def _list_templates_for_editor(self) -> list[tuple[str, str]]:
        user = self._um.get_current_user()
        if user is None:
            return []
        rows: list[tuple[str, str]] = []
        for template in self._signature.list_user_signature_templates(user.user_id):
            rows.append((str(template.template_id), str(template.name)))
        return rows

    def _load_template_for_editor(self, template_id: str) -> tuple[SignaturePlacementInput, LabelLayoutInput]:
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        for template in self._signature.list_user_signature_templates(user.user_id):
            if str(template.template_id) == str(template_id):
                return template.placement, self._runtime_preview_layout(template.layout)
        raise RuntimeError(f"Signaturprofil '{template_id}' wurde nicht gefunden")

    def _open_canvas(self) -> None:
        dialog = SignatureCanvasDialog(self)
        dialog.exec()
        user = self._um.get_current_user()
        if user is not None and dialog.signature_bytes() is not None:
            password = self._replace_password.text().strip() or None
            asset = self._signature.import_signature_asset_bytes_and_set_active(
                user.user_id,
                dialog.signature_bytes(),
                filename_hint="settings-canvas.png",
                password=password,
            )
            self._refresh_active_signature()
            self._append("AKTIVE_SIGNATUR_AKTUALISIERT", {"asset_id": asset.asset_id})

    def _import_and_set_active_signature(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            path, _ = QFileDialog.getOpenFileName(self, "Signatur importieren", "", "Images (*.png *.gif)")
            if not path:
                return
            password = self._replace_password.text().strip() or None
            asset = self._signature.import_signature_asset_and_set_active(user.user_id, Path(path), password=password)
            self._refresh_active_signature()
            self._append("AKTIVE_SIGNATUR_IMPORTIERT", {"asset_id": asset.asset_id})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signatur importieren", str(exc))

    def _refresh_active_signature(self) -> None:
        user = self._um.get_current_user()
        if user is None:
            self._active_asset.clear()
            self._preview_sig_pixmap = None
            self._render_preview()
            return
        asset_id = self._signature.get_active_signature_asset_id(user.user_id)
        self._active_asset.setText(asset_id or "-")
        # Aktuell aktive Signatur als Pixmap für die Vorschau laden
        self._preview_sig_pixmap = None
        if asset_id:
            try:
                tmp_path = Path(tempfile.mkdtemp(prefix="qmtool-prev-")) / "sig.png"
                exported = self._signature.export_active_signature(user.user_id, tmp_path)
                if exported.exists():
                    px = QPixmap(str(exported))
                    if not px.isNull():
                        self._preview_sig_pixmap = px
            except Exception:  # noqa: BLE001
                pass
        self._render_preview()

    def _set_active_signature_asset(self) -> None:
        QMessageBox.information(self, "Signatur aktiv", "Diese Aktion ist nicht mehr erforderlich.")

    def _export_active_signature(self) -> None:
        QMessageBox.information(self, "Signatur exportieren", "Diese Aktion wurde aus der Oberfläche entfernt.")

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
            if not self._is_admin:
                return
            self._global_profile_select.clear()
            self._global_profile_select.addItem("Global wählen", "")
            for profile in self._signature.list_global_signature_templates():
                self._global_profile_select.addItem(profile.name, profile.template_id)
            self._append("GLOBAL_PROFILE_GELADEN", {"count": self._global_profile_select.count() - 1})
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _create_global_profile(self) -> None:
        try:
            if not self._is_admin:
                raise RuntimeError("Nur Admins dürfen globale Templates verwalten.")
            self._require_privileged()
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            created = self._signature.create_user_signature_template(
                owner_user_id=user.user_id,
                name=self._global_profile_name.text().strip(),
                placement=self._build_placement(),
                layout=self._build_layout(),
                signature_asset_id=self._active_asset.text().strip() if self._active_asset.text().strip() not in ("", "-") else None,
                scope="global",
            )
            self._append("GLOBAL_PROFIL_ANGELEGT", {"template_id": created.template_id, "name": created.name})
            self._load_global_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Globales Profil", str(exc))

    def _delete_global_profile(self) -> None:
        try:
            if not self._is_admin:
                raise RuntimeError("Nur Admins dürfen globale Templates verwalten.")
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
            if not self._is_admin:
                raise RuntimeError("Nur Admins dürfen globale Templates verwenden.")
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
        has_qmb = is_effective_qmb(user) if user is not None else False

        self._add_section("Profil / Mein Benutzer", _ProfileWidget(self._container))
        self._add_section("Signatur", _SignatureSettingsWidget(self._container))
        if role == "ADMIN" or has_qmb:
            self._add_section("Benutzerverwaltung", UsersAdminWidget(self._container))
            self._add_section("Lizenzverwaltung", _LicenseManagementWidget(self._container))
            self._add_section("Schulung", _TrainingSettingsWidget(self._container))
        if role == "ADMIN":
            self._add_section("Workflow-Profile", _WorkflowProfilesWidget(self._container))
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


class SignatureSettingsDialog(QDialog):
    """Öffentlicher Dialog, der das Signatur-Einstellungs-Panel standalone öffnet."""

    def __init__(self, container: RuntimeContainer, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signatur verwalten")
        self.resize(820, 700)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(_SignatureSettingsWidget(container))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(scroll, stretch=1)
        layout.addWidget(buttons)


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
