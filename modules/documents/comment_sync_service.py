from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .comment_extractors.docx_comment_reader import DocxCommentReader
from .comment_repository import WorkflowCommentRepository
from .contracts import (
    DocumentVersionState,
    WorkflowCommentContext,
    WorkflowCommentListItem,
    WorkflowCommentRecord,
    WorkflowCommentSourceKind,
    WorkflowCommentStatus,
)


class CommentSyncService:
    def __init__(
        self,
        *,
        comment_repository: WorkflowCommentRepository,
        docx_comment_reader: DocxCommentReader,
        event_bus: object | None = None,
    ) -> None:
        self._comments = comment_repository
        self._reader = docx_comment_reader
        self._event_bus = event_bus

    def sync_docx_comments(
        self, state: DocumentVersionState, *, docx_path: Path, actor_user_id: str
    ) -> list[WorkflowCommentListItem]:
        context = WorkflowCommentContext.DOCX_EDIT
        extracted = self._reader.read_comments(docx_path, context=context.value)
        existing = {
            c.source_comment_key: c
            for c in self._comments.list_for_context(state.document_id, state.version, context)
        }
        now = datetime.now(timezone.utc)
        for item in extracted:
            current = existing.get(item.source_comment_key)
            status = current.status if current else WorkflowCommentStatus.ACTIVE
            record = WorkflowCommentRecord(
                comment_id=current.comment_id if current else uuid4().hex,
                ref_no=current.ref_no if current else f"{state.document_id}-v{state.version}-DOCX-{len(existing)+1:04d}",
                document_id=state.document_id,
                version=state.version,
                context=context,
                source_kind=WorkflowCommentSourceKind.DOCX_EXTRACTED,
                source_comment_key=item.source_comment_key,
                artifact_id=None,
                page_number=None,
                anchor_json=None,
                author_display=item.author,
                source_created_at=item.created_at,
                preview_text=item.preview_text,
                full_text=item.text,
                status=status,
                status_note=current.status_note if current else None,
                status_changed_by=current.status_changed_by if current else None,
                status_changed_at=current.status_changed_at if current else None,
                created_at=current.created_at if current else now,
                updated_at=now,
            )
            self._comments.upsert(record)
        records = self._comments.list_for_context(state.document_id, state.version, context)
        self._publish(
            "domain.documents.workflow.comment.synced.v1",
            {"document_id": state.document_id, "version": state.version, "actor_user_id": actor_user_id},
        )
        return [
            WorkflowCommentListItem(
                comment_id=r.comment_id,
                ref_no=r.ref_no,
                document_id=r.document_id,
                version=r.version,
                context=r.context,
                page_number=r.page_number,
                anchor_json=r.anchor_json,
                author_display=r.author_display,
                created_at=r.source_created_at or r.created_at,
                preview_text=r.preview_text,
                status=r.status,
            )
            for r in records
        ]

    def _publish(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="documents", payload=payload))
