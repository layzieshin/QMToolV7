"""Incident register with API-backed filters."""
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QPushButton

from interfaces.pyqt.contributions.incident_management_sections.case_table import IncidentCaseTableArea
from modules.incident_management.contracts import IncidentListFilter, IncidentStatus
from qm_platform.runtime.container import RuntimeContainer


class RegisterSection(IncidentCaseTableArea):
    def __init__(self, container: RuntimeContainer) -> None:
        self._status_filter = QComboBox()
        self._status_filter.addItem("Alle Status", None)
        for status in IncidentStatus:
            self._status_filter.addItem(status.value, status)
        self._category_filter = QComboBox()
        self._category_filter.addItem("Alle Kategorien", None)
        super().__init__(
            container,
            title="Ereignisregister",
            loader=self._load_cases,
            extra_columns=("CAPA", "Kritisch"),
        )
        filter_form = QFormLayout()
        filter_form.addRow("Status", self._status_filter)
        filter_form.addRow("Kategorie", self._category_filter)
        filter_row = QHBoxLayout()
        apply_filter = QPushButton("Filter anwenden")
        apply_filter.clicked.connect(self.reload)
        filter_row.addLayout(filter_form)
        filter_row.addWidget(apply_filter)
        filter_row.addStretch(1)
        self.layout().insertLayout(1, filter_row)

    def reload(self) -> None:
        try:
            settings = self._api().get_module_settings()
            categories = list(settings.get("categories") or [])
        except Exception:
            categories = []
        current = self._category_filter.currentData()
        self._category_filter.blockSignals(True)
        self._category_filter.clear()
        self._category_filter.addItem("Alle Kategorien", None)
        for category in categories:
            self._category_filter.addItem(category, category)
        if current:
            idx = self._category_filter.findData(current)
            if idx >= 0:
                self._category_filter.setCurrentIndex(idx)
        self._category_filter.blockSignals(False)
        super().reload()

    def _load_cases(self, api):
        flt = IncidentListFilter(
            status=self._status_filter.currentData(),
            category=self._category_filter.currentData(),
        )
        return api.list_incidents(flt)
