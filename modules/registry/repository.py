from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import RegistryEntry


class RegistryRepository(ABC):
    @abstractmethod
    def upsert(self, entry: RegistryEntry) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, document_id: str) -> RegistryEntry | None:
        raise NotImplementedError

    @abstractmethod
    def list_entries(self) -> list[RegistryEntry]:
        raise NotImplementedError
