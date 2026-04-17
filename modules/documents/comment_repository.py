from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import WorkflowCommentContext, WorkflowCommentRecord


class WorkflowCommentRepository(ABC):
    @abstractmethod
    def upsert(self, record: WorkflowCommentRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, comment_id: str) -> WorkflowCommentRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_for_context(
        self, document_id: str, version: int, context: WorkflowCommentContext
    ) -> list[WorkflowCommentRecord]:
        raise NotImplementedError
