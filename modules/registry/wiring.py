"""Port wiring for the registry module (SRP split B5)."""
from __future__ import annotations

from pathlib import Path

from qm_platform.persistence.path_resolver import resolve_bootstrap_absolute_path

from .api import RegistryApi
from .projection_api import RegistryProjectionApi
from .service import RegistryService
from .sqlite_repository import SQLiteRegistryRepository


def register_registry_ports(container) -> None:
    app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
    repository = SQLiteRegistryRepository(
        db_path=resolve_bootstrap_absolute_path(app_home, "registry", "registry_db_path"),
    )
    service = RegistryService(repository)
    container.register_port("registry_service", service)
    container.register_port("registry_api", RegistryApi(service))
    container.register_port(
        "registry_projection_api",
        RegistryProjectionApi(
            service,
            event_bus=container.get_port("event_bus"),
            logger=container.get_port("logger"),
        ),
    )
