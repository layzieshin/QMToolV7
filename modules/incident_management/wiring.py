"""Port wiring for incident_management."""
from __future__ import annotations

from qm_platform.licensing.licensed_proxy import LicensedPortProxy

from .api import IncidentManagementApi
from .service import IncidentManagementService
from .sqlite_repository import SQLiteIncidentRepository
from .storage import IncidentArtifactStorage


def register_incident_management_ports(container) -> None:
    app_home = container.get_port("app_home")
    settings_service = container.get_port("settings_service")
    cfg = settings_service.get_module_settings("incident_management")

    db_path = app_home / cfg.get("incident_db_path", "storage/incident_management/incidents.db")
    artifacts_root = app_home / cfg.get("artifacts_root", "storage/incident_management/artifacts")

    repo = SQLiteIncidentRepository(db_path=db_path)
    storage = IncidentArtifactStorage(artifacts_root)

    service = IncidentManagementService(
        repo=repo,
        storage=storage,
        event_bus=container.get_port("event_bus"),
        audit_logger=container.get_port("audit_logger"),
        settings_service=settings_service,
        usermanagement_service=container.get_port("usermanagement_service"),
    )
    api = IncidentManagementApi(service)

    if container.has_port("license_guard"):
        guard = container.get_port("license_guard")
        api = LicensedPortProxy(api, guard, "incident_management")

    container.register_port("incident_management_api", api)
