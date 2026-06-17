"""PyQt workspace for incident_management (single shell nav entry)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget, QWidget

from interfaces.pyqt.contributions.incident_management_sections import (
    ActionsSection,
    CapaSection,
    EffectivenessSection,
    InquiriesSection,
    LeadershipSection,
    ManagementReviewSection,
    MyIncidentsSection,
    QmbReviewSection,
    RegisterSection,
    ReportEventSection,
    ReportsSection,
    SettingsSection,
)
from interfaces.pyqt.registry.contribution import QtModuleContribution
from qm_platform.runtime.container import RuntimeContainer

_AREA_SPECS: tuple[tuple[str, str], ...] = (
    ("report_event", "Ereignis melden"),
    ("my_incidents", "Meine Ereignisse"),
    ("register", "Ereignisregister"),
    ("qmb_review", "QMB-Pruefung"),
    ("inquiries", "Rueckfragen"),
    ("actions", "Massnahmen"),
    ("capa", "CAPA"),
    ("effectiveness", "Wirksamkeitspruefung"),
    ("reports", "Berichte"),
    ("management_review", "Managementbewertung"),
    ("leadership", "Leitung"),
    ("settings", "Einstellungen"),
)


def _build_area(container: RuntimeContainer, area_id: str) -> QWidget:
    factories = {
        "report_event": lambda: ReportEventSection(container),
        "my_incidents": lambda: MyIncidentsSection(container),
        "register": lambda: RegisterSection(container),
        "qmb_review": lambda: QmbReviewSection(container),
        "inquiries": lambda: InquiriesSection(container),
        "actions": lambda: ActionsSection(container),
        "capa": lambda: CapaSection(container),
        "effectiveness": lambda: EffectivenessSection(container),
        "reports": lambda: ReportsSection(container),
        "management_review": lambda: ManagementReviewSection(container),
        "leadership": lambda: LeadershipSection(container),
        "settings": lambda: SettingsSection(container),
    }
    return factories[area_id]()


class IncidentManagementWorkspace(QWidget):
    """Single workspace: sub-areas live in the left list, not in shell navigation."""

    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container

        root = QHBoxLayout(self)
        self._nav = QListWidget()
        self._nav.setMinimumWidth(220)
        self._nav.setSpacing(2)

        self._stack = QStackedWidget()
        root.addWidget(self._nav)
        root.addWidget(self._stack, stretch=1)

        for area_id, label in _AREA_SPECS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, area_id)
            self._nav.addItem(item)
            self._stack.addWidget(_build_area(container, area_id))

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        if self._nav.count() > 0:
            self._nav.setCurrentRow(0)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="incident_management.workspace",
            module_id="incident_management",
            title="Fehler und Abweichung",
            sort_order=45,
            factory=lambda container: IncidentManagementWorkspace(container),
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
