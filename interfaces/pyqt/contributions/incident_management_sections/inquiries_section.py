"""Open inquiries section."""
from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem

from interfaces.pyqt.contributions.incident_management_sections.base import BaseIncidentArea
from qm_platform.runtime.container import RuntimeContainer


class InquiriesSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="Offene Rueckfragen")
        toolbar = QHBoxLayout()
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self.reload)
        toolbar.addWidget(refresh)
        toolbar.addStretch(1)
        self.layout().addLayout(toolbar)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Ereignis", "Rueckfrage-ID", "Frage", "Status"])
        self.layout().addWidget(self._table, stretch=1)

        answer_form = QFormLayout()
        self._answer_incident = QLineEdit()
        self._answer_text = QLineEdit()
        answer_form.addRow("Ereignis-ID", self._answer_incident)
        answer_form.addRow("Antwort", self._answer_text)
        answer_btn = QPushButton("Antwort senden")
        answer_btn.clicked.connect(self._on_answer)
        answer_row = QHBoxLayout()
        answer_row.addLayout(answer_form)
        answer_row.addWidget(answer_btn)
        self.layout().addLayout(answer_row)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self.layout().addWidget(self._status)

    def reload(self) -> None:
        try:
            inquiries = self._api().list_open_inquiries()
        except Exception as exc:  # noqa: BLE001
            self._table.setRowCount(0)
            self._status.setText(
                f"Liste nicht verfuegbar ({exc}). Antwort ueber Ereignis-ID moeglich."
            )
            return
        self._table.setRowCount(len(inquiries))
        for row, inquiry in enumerate(inquiries):
            for col, value in enumerate(self._presenter.format_inquiry_row(inquiry)):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._status.setText(self._presenter.status_line(count=len(inquiries), label="Offene Rueckfragen"))

    def _on_answer(self) -> None:
        incident_id = self._answer_incident.text().strip()
        answer = self._answer_text.text().strip()
        if not incident_id or not answer:
            self.show_info(self, "Antwort", "Ereignis-ID und Antwort erforderlich.")
            return
        try:
            self._api().answer_inquiry(incident_id, answer)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Antwort fehlgeschlagen", exc)
            return
        self._answer_text.clear()
        self._status.setText(f"Antwort fuer {incident_id} gespeichert.")
        self.reload()
