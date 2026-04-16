"""Workflow Profiles section (extracted from settings_view.py)."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import as_json_text, normalize_role
from interfaces.pyqt.widgets.workflow_profile_wizard import WorkflowProfileWizardDialog
from qm_platform.runtime.container import RuntimeContainer


class WorkflowProfilesWidget(QWidget):
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

