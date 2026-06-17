"""CAPA overview section."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from interfaces.pyqt.contributions.incident_management_sections.base import BaseIncidentArea
from modules.incident_management.contracts import CapaStatus
from qm_platform.runtime.container import RuntimeContainer


class CapaSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="CAPA-Uebersicht")
        toolbar = QHBoxLayout()
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self.reload)
        toolbar.addWidget(refresh)
        toolbar.addStretch(1)
        self.layout().addLayout(toolbar)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["ID", "Titel", "Kategorie", "Status", "CAPA"])
        self.layout().addWidget(self._table, stretch=1)

        form = QFormLayout()
        self._incident_id = QLineEdit()
        self._capa_status = QComboBox()
        for status in CapaStatus:
            self._capa_status.addItem(status.value, status)
        self._goal = QLineEdit()
        self._description = QPlainTextEdit()
        self._description.setMaximumHeight(80)
        self._root_causes = QPlainTextEdit()
        self._root_causes.setMaximumHeight(80)
        form.addRow("Ereignis-ID", self._incident_id)
        form.addRow("CAPA-Status", self._capa_status)
        form.addRow("Ziel", self._goal)
        form.addRow("Beschreibung", self._description)
        form.addRow("RCA Ursachen", self._root_causes)
        self.layout().addLayout(form)

        row = QHBoxLayout()
        start_btn = QPushButton("CAPA starten")
        start_btn.clicked.connect(self._on_start)
        update_btn = QPushButton("CAPA aktualisieren")
        update_btn.clicked.connect(self._on_update)
        rca_btn = QPushButton("RCA anlegen")
        rca_btn.clicked.connect(self._on_rca)
        row.addWidget(start_btn)
        row.addWidget(update_btn)
        row.addWidget(rca_btn)
        self.layout().addLayout(row)

        self._status = QLabel("")
        self.layout().addWidget(self._status)

    def reload(self) -> None:
        try:
            cases = self._api().list_capa_relevant_incidents()
        except Exception as exc:  # noqa: BLE001
            self._table.setRowCount(0)
            self._status.setText(str(exc))
            return
        self._table.setRowCount(len(cases))
        for row, case in enumerate(cases):
            for col, value in enumerate(self._presenter.format_case_row(case)):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._status.setText(self._presenter.status_line(count=len(cases), label="CAPA-relevant"))

    def _selected_incident_id(self) -> str | None:
        row = self._table.currentRow()
        if row >= 0:
            item = self._table.item(row, 0)
            if item:
                return item.text()
        text = self._incident_id.text().strip()
        return text or None

    def _on_start(self) -> None:
        incident_id = self._selected_incident_id()
        if not incident_id:
            self.show_info(self, "CAPA", "Ereignis-ID erforderlich.")
            return
        try:
            self._api().start_capa(
                incident_id,
                goal=self._goal.text().strip() or None,
                description=self._description.toPlainText().strip() or None,
            )
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "CAPA starten fehlgeschlagen", exc)
            return
        self._status.setText(f"CAPA fuer {incident_id} gestartet.")
        self.reload()

    def _on_update(self) -> None:
        incident_id = self._selected_incident_id()
        if not incident_id:
            self.show_info(self, "CAPA", "Ereignis-ID erforderlich.")
            return
        try:
            self._api().update_capa(
                incident_id,
                status=self._capa_status.currentData(),
                goal=self._goal.text().strip() or None,
                description=self._description.toPlainText().strip() or None,
            )
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "CAPA aktualisieren fehlgeschlagen", exc)
            return
        self._status.setText(f"CAPA fuer {incident_id} aktualisiert.")
        self.reload()

    def _on_rca(self) -> None:
        incident_id = self._selected_incident_id()
        if not incident_id:
            self.show_info(self, "RCA", "Ereignis-ID erforderlich.")
            return
        root_causes = self._root_causes.toPlainText().strip()
        if not root_causes:
            self.show_info(self, "RCA", "Ursachen erforderlich.")
            return
        try:
            self._api().create_root_cause_analysis(incident_id, root_causes=root_causes)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "RCA fehlgeschlagen", exc)
            return
        self._status.setText(f"RCA fuer {incident_id} angelegt.")
