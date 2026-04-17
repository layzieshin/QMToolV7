from __future__ import annotations

from .comment_repository import WorkflowCommentRepository
from .contracts import WorkflowCommentContext, WorkflowCommentRecord
from .sqlite_repository import SQLiteDocumentsRepository


class SQLiteWorkflowCommentRepository(WorkflowCommentRepository):
    def __init__(self, repository: SQLiteDocumentsRepository) -> None:
        self._repository = repository

    def upsert(self, record: WorkflowCommentRecord) -> None:
        self._repository.upsert_workflow_comment(record)

    def get(self, comment_id: str) -> WorkflowCommentRecord | None:
        return self._repository.get_workflow_comment(comment_id)

    def list_for_context(
        self, document_id: str, version: int, context: WorkflowCommentContext
    ) -> list[WorkflowCommentRecord]:
        return self._repository.list_workflow_comments(document_id, version, context)
