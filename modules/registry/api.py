from __future__ import annotations

from .contracts import RegistryEntry
from .service import RegistryService


def ensure_postgres_schema_ready(container) -> int:
    """Verify the Registry PostgreSQL schema matches the registered target.

    Uses the runtime DSN only; never applies migrations.
    """
    from .postgres_schema import assert_runtime_schema_ready

    dsn = container.get_port("registry_postgres_dsn")
    return assert_runtime_schema_ready(str(dsn))


class RegistryApi:
    def __init__(self, service: RegistryService) -> None:
        self._service = service

    def get_entry(self, document_id: str) -> RegistryEntry | None:
        return self._service.get_entry(document_id)

    def list_entries(self) -> list[RegistryEntry]:
        return self._service.list_entries()
