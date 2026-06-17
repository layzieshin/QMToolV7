"""Management review batch operations."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from . import authorization as auth
from . import eventing
from .contracts import (
    IncidentTimelineEntry,
    ManagementReviewBatch,
    ManagementReviewBatchStatus,
    ManagementReviewItem,
    ManagementReviewItemStatus,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository


def create_management_review(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    period_start: datetime,
    period_end: datetime,
) -> ManagementReviewBatch:
    auth.require_qmb(user)
    if period_end < period_start:
        raise ValidationError("period_end must be >= period_start")
    now = eventing.utcnow()
    batch = ManagementReviewBatch(
        batch_id=eventing.new_id(),
        period_start=period_start,
        period_end=period_end,
        status=ManagementReviewBatchStatus.OPEN,
        created_by_user_id=auth.user_id(user),
        created_at=now,
    )
    repo.insert_management_batch(batch)
    incidents = repo.list_incidents_in_period(period_start, period_end)
    for case in incidents:
        item = ManagementReviewItem(
            item_id=eventing.new_id(),
            batch_id=batch.batch_id,
            incident_id=case.incident_id,
            status=ManagementReviewItemStatus.INCLUDED,
        )
        repo.insert_management_item(item)
    summary, details = eventing.timeline_summary(
        TimelineEntryType.MANAGEMENT_REVIEW_CREATED,
        batch_id=batch.batch_id,
        item_count=str(len(incidents)),
    )
    for case in incidents:
        repo.add_timeline_entry(
            IncidentTimelineEntry(
                entry_id=eventing.new_id(),
                incident_id=case.incident_id,
                entry_type=TimelineEntryType.MANAGEMENT_REVIEW_CREATED,
                actor_user_id=auth.user_id(user),
                summary=summary,
                details=details,
                created_at=now,
            )
        )
    eventing.emit_audit(
        audit_logger,
        action="incident.management_review.create",
        actor=auth.user_id(user),
        target=batch.batch_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.management_review.created.v1",
        actor_user_id=auth.user_id(user),
        payload={"batch_id": batch.batch_id, "item_count": len(incidents)},
    )
    return batch


def mark_management_review_in_discussion(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    batch_id: str,
) -> ManagementReviewBatch:
    auth.require_qmb(user)
    batch = repo.get_management_batch(batch_id)
    now = eventing.utcnow()
    updated = replace(batch, status=ManagementReviewBatchStatus.IN_DISCUSSION)
    repo.update_management_batch(updated)
    for item in repo.list_management_items(batch_id):
        if item.status == ManagementReviewItemStatus.INCLUDED:
            repo.update_management_item(
                replace(item, status=ManagementReviewItemStatus.IN_DISCUSSION)
            )
            summary, details = eventing.timeline_summary(
                TimelineEntryType.MANAGEMENT_REVIEW_IN_DISCUSSION,
                batch_id=batch_id,
            )
            repo.add_timeline_entry(
                IncidentTimelineEntry(
                    entry_id=eventing.new_id(),
                    incident_id=item.incident_id,
                    entry_type=TimelineEntryType.MANAGEMENT_REVIEW_IN_DISCUSSION,
                    actor_user_id=auth.user_id(user),
                    summary=summary,
                    details=details,
                    created_at=now,
                )
            )
    eventing.emit_audit(
        audit_logger,
        action="incident.management_review.in_discussion",
        actor=auth.user_id(user),
        target=batch_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.management_review.in_discussion.v1",
        actor_user_id=auth.user_id(user),
        payload={"batch_id": batch_id},
    )
    return updated


def acknowledge_management_review_items(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    batch_id: str,
    incident_ids: list[str] | None = None,
) -> list[ManagementReviewItem]:
    auth.require_qmb(user)
    repo.get_management_batch(batch_id)
    now = eventing.utcnow()
    items = repo.list_management_items(batch_id)
    target_ids = set(incident_ids) if incident_ids else {i.incident_id for i in items}
    updated_items: list[ManagementReviewItem] = []
    for item in items:
        if item.incident_id not in target_ids:
            continue
        updated = replace(
            item,
            status=ManagementReviewItemStatus.ACKNOWLEDGED,
            acknowledged_at=now,
            acknowledged_by_user_id=auth.user_id(user),
        )
        repo.update_management_item(updated)
        updated_items.append(updated)
        summary, details = eventing.timeline_summary(
            TimelineEntryType.MANAGEMENT_REVIEW_ACKNOWLEDGED,
            batch_id=batch_id,
            incident_id=item.incident_id,
        )
        repo.add_timeline_entry(
            IncidentTimelineEntry(
                entry_id=eventing.new_id(),
                incident_id=item.incident_id,
                entry_type=TimelineEntryType.MANAGEMENT_REVIEW_ACKNOWLEDGED,
                actor_user_id=auth.user_id(user),
                summary=summary,
                details=details,
                created_at=now,
            )
        )
    batch = repo.get_management_batch(batch_id)
    all_items = repo.list_management_items(batch_id)
    if all(i.status == ManagementReviewItemStatus.ACKNOWLEDGED for i in all_items):
        repo.update_management_batch(replace(batch, status=ManagementReviewBatchStatus.COMPLETED))
    eventing.emit_audit(
        audit_logger,
        action="incident.management_review.ack",
        actor=auth.user_id(user),
        target=batch_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.management_review.acknowledged.v1",
        actor_user_id=auth.user_id(user),
        payload={"batch_id": batch_id, "count": len(updated_items)},
    )
    return updated_items
