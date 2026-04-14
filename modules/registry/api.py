from __future__ import annotations

from .contracts import RegistryEntry
from .service import RegistryService


class RegistryApi:
    def __init__(self, service: RegistryService) -> None:
        self._service = service

    def get_entry(self, document_id: str) -> RegistryEntry | None:
        return self._service.get_entry(document_id)

    def list_entries(self) -> list[RegistryEntry]:
        return self._service.list_entries()
