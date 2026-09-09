from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

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


@dataclass(frozen=True)
class DocumentQueryKeyset:
    sort_value: str
    document_id: str
    version: int


def document_query_sort_sql_expression(sort: str, *, dialect: str = "sqlite") -> str:
    if sort == "updated_at":
        if dialect == "postgres":
            return "COALESCE(updated_at, last_event_at, created_at)"
        return "COALESCE(updated_at, last_event_at, created_at, '')"
    if sort == "title":
        return "COALESCE(title, '')"
    if sort == "status":
        return "status"
    raise ValueError(f"unsupported sort field: {sort}")


def document_query_keyset_bind_value(sort: str, sort_value: str, *, dialect: str = "sqlite") -> object:
    """Return a SQL-bindable keyset sort value for the target dialect."""
    if sort == "updated_at" and dialect == "postgres":
        if not sort_value:
            # timestamptz columns cannot compare against an empty string bind.
            return "1970-01-01T00:00:00+00:00"
        return sort_value
    return sort_value


def document_query_keyset_sort_value(state: DocumentVersionState, sort: str) -> str:
    if sort == "updated_at":
        moment = state.updated_at or state.last_event_at or state.created_at
        return moment.isoformat() if moment is not None else ""
    if sort == "title":
        return state.title or ""
    if sort == "status":
        return state.status.value
    raise ValueError(f"unsupported sort field: {sort}")


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
    def query_document_versions(
        self,
        *,
        status: DocumentStatus | None,
        search_q: str | None,
        sort: str,
        order: str,
        limit: int,
        after: DocumentQueryKeyset | None,
    ) -> tuple[list[DocumentVersionState], bool]:
        """Return up to ``limit`` rows in sort order and whether more rows exist."""
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
    def get_artifact_by_id(self, artifact_id: str) -> DocumentArtifact | None:
        raise NotImplementedError

    @abstractmethod
    def delete_artifact(self, artifact_id: str) -> None:
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

