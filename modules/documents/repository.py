from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import (
    ArtifactType,
    DocumentArtifact,
    DocumentHeader,
    DocumentReadReceipt,
    DocumentStatus,
    DocumentVersionState,
    PdfReadProgress,
    TrackedPdfReadSession,
    WorkflowCommentContext,
    WorkflowCommentRecord,
)


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

    @abstractmethod
    def create_read_receipt(self, receipt: DocumentReadReceipt) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_read_receipt(self, user_id: str, document_id: str, version: int) -> DocumentReadReceipt | None:
        raise NotImplementedError

    @abstractmethod
    def upsert_workflow_comment(self, record: WorkflowCommentRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_workflow_comment(self, comment_id: str) -> WorkflowCommentRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_workflow_comments(
        self, document_id: str, version: int, context: WorkflowCommentContext
    ) -> list[WorkflowCommentRecord]:
        raise NotImplementedError

    @abstractmethod
    def create_pdf_read_session(self, session: TrackedPdfReadSession) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_pdf_read_session(self, session_id: str) -> TrackedPdfReadSession | None:
        raise NotImplementedError

    @abstractmethod
    def update_pdf_read_page_progress(
        self, session_id: str, page_number: int, accumulated_seconds: int, reached_threshold: bool
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_pdf_read_progress(self, session_id: str) -> PdfReadProgress | None:
        raise NotImplementedError

    @abstractmethod
    def complete_pdf_read_session(self, session_id: str, *, completed_at: str, completion_result: str) -> None:
        raise NotImplementedError

