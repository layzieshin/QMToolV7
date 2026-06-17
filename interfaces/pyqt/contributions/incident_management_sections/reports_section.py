"""Reports and export section."""
from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton

from interfaces.pyqt.contributions.incident_management_sections.base import BaseIncidentArea
from qm_platform.runtime.container import RuntimeContainer


class ReportsSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="Berichte / Export")
        form = QFormLayout()
        self._incident_id = QLineEdit()
        form.addRow("Ereignis-ID (Einzelbericht)", self._incident_id)
        self.layout().addLayout(form)

        row = QHBoxLayout()
        case_btn = QPushButton("Einzelbericht")
        case_btn.clicked.connect(self._on_case_report)
        register_btn = QPushButton("Register-PDF")
        register_btn.clicked.connect(self._on_register_pdf)
        capa_btn = QPushButton("CAPA-Bericht")
        capa_btn.clicked.connect(self._on_capa_report)
        patterns_btn = QPushButton("Musteruebersicht")
        patterns_btn.clicked.connect(self._on_patterns_report)
        row.addWidget(case_btn)
        row.addWidget(register_btn)
        row.addWidget(capa_btn)
        row.addWidget(patterns_btn)
        self.layout().addLayout(row)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self.layout().addWidget(self._output, stretch=1)

        self._status = QLabel("")
        self.layout().addWidget(self._status)

    def reload(self) -> None:
        self._status.setText("Bereit")

    def _show_result(self, result) -> None:
        self._output.setPlainText(self._presenter.format_report_result(result))

    def _on_case_report(self) -> None:
        incident_id = self._incident_id.text().strip()
        if not incident_id:
            self.show_info(self, "Einzelbericht", "Ereignis-ID erforderlich.")
            return
        try:
            result = self._api().generate_incident_report(incident_id)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Einzelbericht fehlgeschlagen", exc)
            return
        self._show_result(result)
        self._status.setText(f"Einzelbericht fuer {incident_id} erzeugt.")

    def _on_register_pdf(self) -> None:
        try:
            result = self._api().generate_register_pdf()
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Register-PDF fehlgeschlagen", exc)
            return
        self._show_result(result)
        self._status.setText("Register-PDF erzeugt.")

    def _on_capa_report(self) -> None:
        try:
            result = self._api().generate_capa_report()
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "CAPA-Bericht fehlgeschlagen", exc)
            return
        self._show_result(result)
        self._status.setText("CAPA-Bericht erzeugt.")

    def _on_patterns_report(self) -> None:
        try:
            result = self._api().generate_patterns_report()
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Musteruebersicht fehlgeschlagen", exc)
            return
        self._show_result(result)
        self._status.setText("Musteruebersicht erzeugt.")
