"""Module Settings section (extracted from settings_view.py)."""
from __future__ import annotations

import json

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import as_json_text
from interfaces.pyqt.presenters.settings_policy_presenter import SettingsPolicyPresenter
from interfaces.pyqt.widgets.access_guards import require_admin_or_qmb
from qm_platform.runtime.container import RuntimeContainer


class ModuleSettingsWidget(QWidget):
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
                module_id, payload, acknowledge_governance_change=self._ack.isChecked(),
            )
            persisted = self._svc.get_module_settings(module_id)
            self._editor.setPlainText(json.dumps(persisted, indent=2, ensure_ascii=True))
            self._append("GESPEICHERT", {"module_id": module_id, "settings": persisted})
            self._append("GOVERNANCE_ACK", {"status": self._policy.summarize_governance_ack(acknowledged=self._ack.isChecked())})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Einstellungen", str(exc))

