"""My incidents section."""
from __future__ import annotations

from interfaces.pyqt.contributions.incident_management_sections.case_table import IncidentCaseTableArea
from qm_platform.runtime.container import RuntimeContainer


class MyIncidentsSection(IncidentCaseTableArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(
            container,
            title="Meine Ereignisse",
            loader=lambda api: api.list_my_incidents(),
            extra_columns=("CAPA", "Kritisch"),
        )
