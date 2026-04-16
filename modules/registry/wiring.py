"""Port wiring for the registry module (SRP split B5)."""
from __future__ import annotations

from pathlib import Path

from .api import RegistryApi
from .projection_api import RegistryProjectionApi
from .service import RegistryService
from .sqlite_repository import SQLiteRegistryRepository


def register_registry_ports(container) -> None:
    app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
    settings_service = container.get_port("settings_service")
    cfg = settings_service.get_module_settings("registry")
    db_path = Path(cfg.get("registry_db_path", "storage/documents/registry.db"))
    if not db_path.is_absolute():
        db_path = app_home / db_path
    repository = SQLiteRegistryRepository(
        db_path=db_path,
        schema_path=Path(__file__).parent / "schema.sql",
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

