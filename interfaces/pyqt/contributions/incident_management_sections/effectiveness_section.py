"""Effectiveness review section."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
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


class EffectivenessSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="Wirksamkeitspruefungen")
        toolbar = QHBoxLayout()
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self.reload)
        toolbar.addWidget(refresh)
        toolbar.addStretch(1)
        self.layout().addLayout(toolbar)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Ereignis", "Pruefung", "Status", "Geplant"])
        self.layout().addWidget(self._table, stretch=1)

        form = QFormLayout()
        self._incident_id = QLineEdit()
        self._criteria = QLineEdit()
        self._result = QLineEdit()
        self._notes = QLineEdit()
        self._effective = QCheckBox("Wirksam")
        form.addRow("Ereignis-ID", self._incident_id)
        form.addRow("Kriterien", self._criteria)
        form.addRow("Ergebnis", self._result)
        form.addRow("Notizen", self._notes)
        form.addRow("", self._effective)
        self.layout().addLayout(form)

        row = QHBoxLayout()
        plan_btn = QPushButton("Pruefung planen")
        plan_btn.clicked.connect(self._on_plan)
        complete_btn = QPushButton("Pruefung abschliessen")
        complete_btn.clicked.connect(self._on_complete)
        row.addWidget(plan_btn)
        row.addWidget(complete_btn)
        self.layout().addLayout(row)

        self._status = QLabel("")
        self.layout().addWidget(self._status)

    def reload(self) -> None:
        try:
            reviews = self._api().list_pending_effectiveness_reviews()
        except Exception as exc:  # noqa: BLE001
            self._table.setRowCount(0)
            self._status.setText(str(exc))
            return
        self._table.setRowCount(len(reviews))
        for row, review in enumerate(reviews):
            for col, value in enumerate(self._presenter.format_effectiveness_row(review)):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._status.setText(self._presenter.status_line(count=len(reviews), label="Wirksamkeitspruefungen"))

    def _selected_incident_id(self) -> str | None:
        row = self._table.currentRow()
        if row >= 0:
            item = self._table.item(row, 0)
            if item:
                return item.text()
        return self._incident_id.text().strip() or None

    def _on_plan(self) -> None:
        incident_id = self._selected_incident_id()
        criteria = self._criteria.text().strip()
        if not incident_id or not criteria:
            self.show_info(self, "Planen", "Ereignis-ID und Kriterien erforderlich.")
            return
        try:
            self._api().plan_effectiveness_review(incident_id, criteria)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Planen fehlgeschlagen", exc)
            return
        self._status.setText(f"Wirksamkeitspruefung fuer {incident_id} geplant.")
        self.reload()

    def _on_complete(self) -> None:
        incident_id = self._selected_incident_id()
        result = self._result.text().strip()
        if not incident_id or not result:
            self.show_info(self, "Abschliessen", "Ereignis-ID und Ergebnis erforderlich.")
            return
        try:
            review = self._api().complete_effectiveness_review(
                incident_id,
                effective=self._effective.isChecked(),
                result=result,
                notes=self._notes.text().strip() or None,
            )
            case = self._api().get_incident(incident_id)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Abschliessen fehlgeschlagen", exc)
            return
        self._status.setText(
            f"Pruefung {review.review_id} abgeschlossen. Ereignisstatus: {case.status.value}"
        )
        self.reload()
