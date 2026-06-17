"""Leadership acknowledgement section."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from interfaces.pyqt.contributions.incident_management_sections.base import BaseIncidentArea
from qm_platform.runtime.container import RuntimeContainer


class LeadershipSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="Leitung / Kenntnisnahme")
        toolbar = QHBoxLayout()
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self.reload)
        toolbar.addWidget(refresh)
        toolbar.addStretch(1)
        self.layout().addLayout(toolbar)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Ereignis", "Leitung", "Status", "Weitergeleitet"])
        self.layout().addWidget(self._table, stretch=1)

        form = QFormLayout()
        self._forward_incident = QLineEdit()
        self._leadership_user = QLineEdit()
        self._ack_comment = QLineEdit()
        form.addRow("Ereignis-ID (Weiterleitung)", self._forward_incident)
        form.addRow("Leitung User-ID", self._leadership_user)
        form.addRow("Kenntnisnahme-Kommentar", self._ack_comment)
        self.layout().addLayout(form)

        row = QHBoxLayout()
        forward_btn = QPushButton("An Leitung weiterleiten")
        forward_btn.clicked.connect(self._on_forward)
        ack_btn = QPushButton("Kenntnisnahme bestaetigen")
        ack_btn.clicked.connect(self._on_ack)
        row.addWidget(forward_btn)
        row.addWidget(ack_btn)
        self.layout().addLayout(row)

        self._status = QLabel("")
        self.layout().addWidget(self._status)

    def reload(self) -> None:
        try:
            queue = self._api().list_leadership_queue()
        except Exception as exc:  # noqa: BLE001
            self._table.setRowCount(0)
            self._status.setText(str(exc))
            return
        self._table.setRowCount(len(queue))
        for row, ack in enumerate(queue):
            for col, value in enumerate(self._presenter.format_leadership_row(ack)):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._status.setText(self._presenter.status_line(count=len(queue), label="Leitung"))

    def _selected_incident_id(self) -> str | None:
        row = self._table.currentRow()
        if row >= 0:
            item = self._table.item(row, 0)
            if item:
                return item.text()
        return self._forward_incident.text().strip() or None

    def _on_forward(self) -> None:
        incident_id = self._forward_incident.text().strip()
        leadership_user_id = self._leadership_user.text().strip()
        if not incident_id or not leadership_user_id:
            self.show_info(self, "Weiterleitung", "Ereignis-ID und Leitung User-ID erforderlich.")
            return
        try:
            self._api().forward_to_leadership(incident_id, leadership_user_id)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Weiterleitung fehlgeschlagen", exc)
            return
        self._status.setText(f"Ereignis {incident_id} an {leadership_user_id} weitergeleitet.")
        self.reload()

    def _on_ack(self) -> None:
        incident_id = self._selected_incident_id()
        if not incident_id:
            self.show_info(self, "Kenntnisnahme", "Ereignis-ID erforderlich.")
            return
        comment = self._ack_comment.text().strip() or None
        try:
            self._api().acknowledge_leadership_review(incident_id, comment)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Kenntnisnahme fehlgeschlagen", exc)
            return
        self._status.setText(f"Kenntnisnahme fuer {incident_id} gespeichert.")
        self.reload()
