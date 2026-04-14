from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import ArtifactType, DocumentArtifact, DocumentHeader, DocumentStatus, DocumentVersionState


class DocumentsRepository(ABC):
    @abstractmethod
    def upsert_header(self, header: DocumentHeader) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_header(self, document_id: str) -> DocumentHeader | None:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, state: DocumentVersionState) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, document_id: str, version: int) -> DocumentVersionState | None:
        raise NotImplementedError

    @abstractmethod
    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        raise NotImplementedError

    @abstractmethod
    def list_versions(self, document_id: str) -> list[DocumentVersionState]:
        raise NotImplementedError

    @abstractmethod
    def add_artifact(self, artifact: DocumentArtifact) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        raise NotImplementedError

    @abstractmethod
    def mark_current_artifact(
        self,
        document_id: str,
        version: int,
        artifact_type: ArtifactType,
        artifact_id: str,
    ) -> None:
        raise NotImplementedError

