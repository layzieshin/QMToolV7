"""Reusable incident case table with optional detail panel."""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.incident_management_sections.base import BaseIncidentArea
from qm_platform.runtime.container import RuntimeContainer


class IncidentCaseTableArea(BaseIncidentArea):
    def __init__(
        self,
        container: RuntimeContainer,
        *,
        title: str,
        loader: Callable,
        extra_columns: tuple[str, ...] = (),
    ) -> None:
        super().__init__(container, title=title)
        self._loader = loader
        self._area_title = title
        self._extra_columns = extra_columns

        toolbar = QHBoxLayout()
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self.reload)
        detail_btn = QPushButton("Details laden")
        detail_btn.clicked.connect(self._load_detail)
        toolbar.addWidget(refresh)
        toolbar.addWidget(detail_btn)
        toolbar.addStretch(1)
        self.layout().addLayout(toolbar)

        headers = ["ID", "Titel", "Kategorie", "Status", "Einstufung", *extra_columns]
        self._table = QTableWidget(0, len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.layout().addWidget(self._table, stretch=1)

        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(180)
        self.layout().addWidget(self._detail)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self.layout().addWidget(self._status)

    def _selected_incident_id(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def reload(self) -> None:
        try:
            cases = self._loader(self._api())
        except Exception as exc:  # noqa: BLE001
            self._table.setRowCount(0)
            self._detail.clear()
            self._status.setText(f"Fehler: {exc}")
            return
        self._table.setRowCount(len(cases))
        for row, case in enumerate(cases):
            values = list(self._presenter.format_case_row(case))
            if self._extra_columns:
                values.extend(self._presenter.format_case_flags(case))
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._status.setText(self._presenter.status_line(count=len(cases), label=self._area_title))

    def _load_detail(self) -> None:
        incident_id = self._selected_incident_id()
        if not incident_id:
            self.show_info(self, "Details", "Bitte zuerst ein Ereignis auswaehlen.")
            return
        try:
            case = self._api().get_incident(incident_id)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Details", exc)
            return
        self._detail.setPlainText(self._presenter.format_incident_detail(case))
