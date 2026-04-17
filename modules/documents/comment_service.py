from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .comment_permissions import ensure_workflow_comment_access
from .comment_repository import WorkflowCommentRepository
from .contracts import (
    DocumentVersionState,
    SystemRole,
    WorkflowCommentContext,
    WorkflowCommentDetail,
    WorkflowCommentListItem,
    WorkflowCommentRecord,
    WorkflowCommentSourceKind,
    WorkflowCommentStatus,
)
from .errors import ValidationError


class WorkflowCommentService:
    def __init__(self, *, repository: WorkflowCommentRepository, event_bus: object | None = None) -> None:
        self._repository = repository
        self._event_bus = event_bus

    def list_comments(
        self, state: DocumentVersionState, *, context: WorkflowCommentContext
    ) -> list[WorkflowCommentListItem]:
        records = self._repository.list_for_context(state.document_id, state.version, context)
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

    def get_detail(self, comment_id: str) -> WorkflowCommentDetail:
        record = self._repository.get(comment_id)
        if record is None:
            raise ValidationError("comment not found")
        return WorkflowCommentDetail(
            comment_id=record.comment_id,
            ref_no=record.ref_no,
            document_id=record.document_id,
            version=record.version,
            context=record.context,
            page_number=record.page_number,
            author_display=record.author_display,
            created_at=record.source_created_at or record.created_at,
            full_text=record.full_text,
            status=record.status,
            status_note=record.status_note,
            source_kind=record.source_kind,
        )

    def create_pdf_comment(
        self,
        state: DocumentVersionState,
        *,
        context: WorkflowCommentContext,
        actor_user_id: str,
        actor_role: SystemRole,
        page_number: int,
        comment_text: str,
        anchor_json: str | None = None,
        artifact_id: str | None = None,
    ) -> WorkflowCommentRecord:
        ensure_workflow_comment_access(
            state, context=context, actor_user_id=actor_user_id, actor_role=actor_role
        )
        now = datetime.now(timezone.utc)
        records = self._repository.list_for_context(state.document_id, state.version, context)
        next_no = len(records) + 1
        ref_no = f"{state.document_id}-v{state.version}-{context.value}-{next_no:04d}"
        text = comment_text.strip()
        if not text:
            raise ValidationError("comment_text is required")
        record = WorkflowCommentRecord(
            comment_id=uuid4().hex,
            ref_no=ref_no,
            document_id=state.document_id,
            version=state.version,
            context=context,
            source_kind=WorkflowCommentSourceKind.PDF_APP,
            source_comment_key=f"pdf-app:{uuid4().hex}",
            artifact_id=artifact_id,
            page_number=page_number,
            anchor_json=anchor_json,
            author_display=actor_user_id,
            source_created_at=now,
            preview_text=text[:160],
            full_text=text,
            status=WorkflowCommentStatus.ACTIVE,
            status_note=None,
            status_changed_by=None,
            status_changed_at=None,
            created_at=now,
            updated_at=now,
        )
        self._repository.upsert(record)
        self._publish("domain.documents.workflow.comment.created.v1", {"comment_id": record.comment_id})
        return record

    def set_status(
        self,
        comment_id: str,
        *,
        new_status: WorkflowCommentStatus,
        actor_user_id: str,
        note: str | None = None,
    ) -> WorkflowCommentRecord:
        current = self._repository.get(comment_id)
        if current is None:
            raise ValidationError("comment not found")
        now = datetime.now(timezone.utc)
        updated = WorkflowCommentRecord(
            **{
                **current.__dict__,
                "status": new_status,
                "status_note": note,
                "status_changed_by": actor_user_id,
                "status_changed_at": now,
                "updated_at": now,
            }
        )
        self._repository.upsert(updated)
        self._publish("domain.documents.workflow.comment.status.changed.v1", {"comment_id": comment_id})
        return updated

    def _publish(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="documents", payload=payload))
