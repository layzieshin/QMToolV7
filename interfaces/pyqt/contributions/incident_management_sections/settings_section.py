"""Incident module settings section."""
from __future__ import annotations

import json

from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton

from interfaces.pyqt.contributions.incident_management_sections.base import BaseIncidentArea
from qm_platform.runtime.container import RuntimeContainer


class SettingsSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="Einstellungen")
        toolbar = QHBoxLayout()
        reload_btn = QPushButton("Laden")
        reload_btn.clicked.connect(self.reload)
        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self._on_save)
        toolbar.addWidget(reload_btn)
        toolbar.addWidget(save_btn)
        toolbar.addStretch(1)
        self.layout().addLayout(toolbar)

        self._governance_ack = QCheckBox(
            "Governance-kritische Aenderung bestaetigen (erforderlich fuer kritische Keys)"
        )
        self.layout().addWidget(self._governance_ack)

        self._editor = QPlainTextEdit()
        self.layout().addWidget(self._editor, stretch=1)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self.layout().addWidget(self._status)

    def reload(self) -> None:
        try:
            settings = self._api().get_module_settings()
        except Exception as exc:  # noqa: BLE001
            self._editor.clear()
            self._status.setText(str(exc))
            return
        self._editor.setPlainText(json.dumps(settings, indent=2, ensure_ascii=False))
        self._status.setText("Einstellungen geladen.")

    def _on_save(self) -> None:
        try:
            values = json.loads(self._editor.toPlainText())
        except json.JSONDecodeError as exc:
            self.show_error(self, "Speichern", exc)
            return
        if not isinstance(values, dict):
            self.show_info(self, "Speichern", "JSON muss ein Objekt sein.")
            return
        try:
            saved = self._api().set_module_settings(
                values,
                acknowledge_governance_change=self._governance_ack.isChecked(),
            )
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Speichern fehlgeschlagen", exc)
            return
        self._editor.setPlainText(json.dumps(saved, indent=2, ensure_ascii=False))
        self._status.setText("Einstellungen gespeichert.")
