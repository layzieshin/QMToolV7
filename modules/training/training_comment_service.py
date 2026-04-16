"""Training comment service with status model (§3.13, §10)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import (
    CommentStatus,
    TrainingCommentListItem,
    TrainingCommentRecord,
)
from .errors import TrainingValidationError
from .training_comment_repository import TrainingCommentRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrainingCommentService:
    def __init__(
        self,
        *,
        comment_repo: TrainingCommentRepository,
        event_bus: object | None = None,
    ) -> None:
        self._repo = comment_repo
        self._event_bus = event_bus

    def add_comment(
        self,
        user_id: str,
        document_id: str,
        version: int,
        comment_text: str,
        *,
        document_title_snapshot: str = "",
        username_snapshot: str = "",
    ) -> TrainingCommentRecord:
        text = comment_text.strip()
        if not text:
            raise TrainingValidationError("comment_text is required")
        now = _utcnow()
        record = TrainingCommentRecord(
            comment_id=uuid4().hex,
            document_id=document_id,
            version=version,
            document_title_snapshot=document_title_snapshot,
            user_id=user_id,
            username_snapshot=username_snapshot,
            comment_text=text,
            status=CommentStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self._repo.create_comment(record)
        self._publish("domain.training.comment.created.v1", {
            "comment_id": record.comment_id,
            "document_id": document_id,
            "version": version,
            "user_id": user_id,
        }, actor=user_id)
        return record

    def list_active_comments(self) -> list[TrainingCommentListItem]:
        return self._repo.list_active_comments()

    def list_comments_for_document(self, document_id: str, version: int) -> list[TrainingCommentListItem]:
        return self._repo.list_comments_for_document(document_id, version)

    def resolve_comment(
        self, comment_id: str, resolved_by: str, resolution_note: str | None = None
    ) -> TrainingCommentRecord:
        record = self._repo.get_comment(comment_id)
        if record is None:
            raise TrainingValidationError("comment not found")
        now = _utcnow()
        updated = TrainingCommentRecord(
            comment_id=record.comment_id,
            document_id=record.document_id,
            version=record.version,
            document_title_snapshot=record.document_title_snapshot,
            user_id=record.user_id,
            username_snapshot=record.username_snapshot,
            comment_text=record.comment_text,
            status=CommentStatus.RESOLVED,
            created_at=record.created_at,
            updated_at=now,
            resolved_by=resolved_by,
            resolved_at=now,
            resolution_note=resolution_note,
            inactive_by=record.inactive_by,
            inactive_at=record.inactive_at,
            inactive_note=record.inactive_note,
        )
        self._repo.update_comment(updated)
        self._publish("domain.training.comment.resolved.v1", {
            "comment_id": comment_id, "resolved_by": resolved_by,
        }, actor=resolved_by)
        return updated

    def inactivate_comment(
        self, comment_id: str, inactive_by: str, inactive_note: str | None = None
    ) -> TrainingCommentRecord:
        record = self._repo.get_comment(comment_id)
        if record is None:
            raise TrainingValidationError("comment not found")
        now = _utcnow()
        updated = TrainingCommentRecord(
            comment_id=record.comment_id,
            document_id=record.document_id,
            version=record.version,
            document_title_snapshot=record.document_title_snapshot,
            user_id=record.user_id,
            username_snapshot=record.username_snapshot,
            comment_text=record.comment_text,
            status=CommentStatus.INACTIVE,
            created_at=record.created_at,
            updated_at=now,
            resolved_by=record.resolved_by,
            resolved_at=record.resolved_at,
            resolution_note=record.resolution_note,
            inactive_by=inactive_by,
            inactive_at=now,
            inactive_note=inactive_note,
        )
        self._repo.update_comment(updated)
        self._publish("domain.training.comment.inactivated.v1", {
            "comment_id": comment_id, "inactive_by": inactive_by,
        }, actor=inactive_by)
        return updated

    def _publish(self, name: str, payload: dict, *, actor: str | None = None) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="training", payload=payload, actor_user_id=actor))

