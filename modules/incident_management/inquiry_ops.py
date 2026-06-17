"""Inquiry operations."""
from __future__ import annotations

from . import authorization as auth
from . import eventing
from . import incident_ops
from .contracts import (
    IncidentInquiry,
    IncidentStatus,
    IncidentTimelineEntry,
    InquiryStatus,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository
from .validation import require_non_empty


def open_inquiry(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    question: str,
) -> IncidentInquiry:
    auth.require_qmb(user)
    case = repo.get_incident(incident_id)
    text = require_non_empty(question, "question")
    now = eventing.utcnow()
    inquiry = IncidentInquiry(
        inquiry_id=eventing.new_id(),
        incident_id=incident_id,
        question=text,
        answer=None,
        asked_by_user_id=auth.user_id(user),
        answered_by_user_id=None,
        asked_at=now,
        answered_at=None,
        status=InquiryStatus.OPEN,
    )
    repo.add_inquiry(inquiry)
    incident_ops.set_status(
        repo=repo,
        case=case,
        status=IncidentStatus.INQUIRY_OPEN,
        actor_user_id=auth.user_id(user),
    )
    summary, details = eventing.timeline_summary(TimelineEntryType.INQUIRY_OPENED, inquiry_id=inquiry.inquiry_id)
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.INQUIRY_OPENED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.inquiry.open",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.inquiry.opened.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "inquiry_id": inquiry.inquiry_id},
    )
    return inquiry


def answer_inquiry(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    answer: str,
) -> IncidentInquiry:
    inquiry = repo.get_open_inquiry(incident_id)
    if inquiry is None:
        raise ValidationError("no open inquiry for incident")
    case = repo.get_incident(incident_id)
    auth.require_can_answer_inquiry(user, case, inquiry)
    text = require_non_empty(answer, "answer")
    now = eventing.utcnow()
    updated = IncidentInquiry(
        inquiry_id=inquiry.inquiry_id,
        incident_id=incident_id,
        question=inquiry.question,
        answer=text,
        asked_by_user_id=inquiry.asked_by_user_id,
        answered_by_user_id=auth.user_id(user),
        asked_at=inquiry.asked_at,
        answered_at=now,
        status=InquiryStatus.ANSWERED,
    )
    repo.update_inquiry(updated)
    incident_ops.set_status(
        repo=repo,
        case=case,
        status=IncidentStatus.INQUIRY_ANSWERED,
        actor_user_id=auth.user_id(user),
    )
    summary, details = eventing.timeline_summary(TimelineEntryType.INQUIRY_ANSWERED, inquiry_id=inquiry.inquiry_id)
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.INQUIRY_ANSWERED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.inquiry.answer",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.inquiry.answered.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "inquiry_id": inquiry.inquiry_id},
    )
    return updated
