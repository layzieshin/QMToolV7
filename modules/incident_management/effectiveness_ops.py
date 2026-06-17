"""Effectiveness review and closure operations."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from . import authorization as auth
from . import eventing
from . import incident_ops
from .contracts import (
    EffectivenessReviewStatus,
    EffectivenessReview,
    IncidentStatus,
    IncidentTimelineEntry,
    LeadershipAckStatus,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository


def _settings_delay_days(settings: dict) -> int:
    return int(settings.get("effectiveness_delay", 30) or 30)


def plan_effectiveness_review(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    settings: dict,
    user: object,
    incident_id: str,
    criteria: str,
    planned_at: datetime | None = None,
) -> EffectivenessReview:
    auth.require_qmb(user)
    case = repo.get_incident(incident_id)
    if case.status not in (IncidentStatus.ACTIONS_IN_PROGRESS, IncidentStatus.FOLLOW_UP):
        raise ValidationError(
            "effectiveness review can only be planned from actions in progress or follow-up"
        )
    if not case.capa_required:
        raise ValidationError("effectiveness review only required for CAPA incidents")
    if not criteria.strip():
        raise ValidationError("criteria is required")
    now = eventing.utcnow()
    planned = planned_at or (now + timedelta(days=_settings_delay_days(settings)))
    review = EffectivenessReview(
        review_id=eventing.new_id(),
        incident_id=incident_id,
        planned_at=planned,
        criteria=criteria.strip(),
        completed_at=None,
        completed_by_user_id=None,
        result=None,
        effective=None,
        notes=None,
        status=EffectivenessReviewStatus.PLANNED,
        created_at=now,
    )
    repo.add_effectiveness_review(review)
    incident_ops.set_status(
        repo=repo,
        case=case,
        status=IncidentStatus.EFFECTIVENESS_PLANNED,
        actor_user_id=auth.user_id(user),
    )
    summary, details = eventing.timeline_summary(
        TimelineEntryType.EFFECTIVENESS_PLANNED,
        review_id=review.review_id,
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.EFFECTIVENESS_PLANNED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.effectiveness.plan",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.effectiveness.planned.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "review_id": review.review_id},
    )
    return review


def complete_effectiveness_review(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    effective: bool,
    result: str,
    notes: str | None = None,
) -> EffectivenessReview:
    auth.require_qmb(user)
    existing = repo.get_effectiveness_review(incident_id)
    if existing is None:
        raise ValidationError("no effectiveness review planned")
    now = eventing.utcnow()
    review = EffectivenessReview(
        review_id=existing.review_id,
        incident_id=incident_id,
        planned_at=existing.planned_at,
        criteria=existing.criteria,
        completed_at=now,
        completed_by_user_id=auth.user_id(user),
        result=result,
        effective=effective,
        notes=notes,
        status=EffectivenessReviewStatus.COMPLETED,
        created_at=existing.created_at,
    )
    repo.update_effectiveness_review(review)
    case = repo.get_incident(incident_id)
    case = incident_ops.set_status(
        repo=repo,
        case=case,
        status=IncidentStatus.EFFECTIVENESS_REVIEW,
        actor_user_id=auth.user_id(user),
    )
    if effective:
        case = incident_ops.set_status(
            repo=repo,
            case=case,
            status=IncidentStatus.CLOSURE_REVIEW,
            actor_user_id=auth.user_id(user),
        )
    else:
        case = incident_ops.set_status(
            repo=repo,
            case=case,
            status=IncidentStatus.FOLLOW_UP,
            actor_user_id=auth.user_id(user),
        )
    summary, details = eventing.timeline_summary(
        TimelineEntryType.EFFECTIVENESS_REVIEWED,
        review_id=review.review_id,
        effective=str(effective),
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.EFFECTIVENESS_REVIEWED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.effectiveness.complete",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.effectiveness.reviewed.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "review_id": review.review_id, "effective": effective},
    )
    return review


def _validate_closure(repo: SQLiteIncidentRepository, case) -> None:
    if case.classification is None:
        raise ValidationError("assessment required before closure")
    if repo.count_open_inquiries(case.incident_id) > 0:
        raise ValidationError("open inquiries block closure")
    if case.capa_required:
        if repo.get_rca(case.incident_id) is None:
            raise ValidationError("root cause analysis required before closure")
        capa = repo.get_capa(case.incident_id)
        if capa is None:
            raise ValidationError("CAPA must be started before closure")
        open_actions = repo.list_open_actions(case.incident_id)
        if open_actions:
            raise ValidationError("open actions block closure")
        review = repo.get_effectiveness_review(case.incident_id)
        if review is None or review.status != EffectivenessReviewStatus.COMPLETED:
            raise ValidationError("completed effectiveness review required")
        if review.effective is False:
            raise ValidationError("effectiveness review must be effective before closure")
    if case.leadership_required:
        ack = repo.get_leadership_ack(case.incident_id)
        if ack is None or ack.status != LeadershipAckStatus.ACKNOWLEDGED:
            raise ValidationError("leadership acknowledgement required before closure")


def close_incident(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
) -> object:
    auth.require_qmb(user)
    case = repo.get_incident(incident_id)
    if case.status in (IncidentStatus.CLOSED, IncidentStatus.ARCHIVED):
        raise ValidationError("incident already closed or archived")
    _validate_closure(repo, case)
    case = repo.get_incident(incident_id)
    if case.status in (IncidentStatus.DOCUMENTATION_ONLY, IncidentStatus.ASSESSED):
        case = incident_ops.set_status(
            repo=repo,
            case=case,
            status=IncidentStatus.CLOSURE_REVIEW,
            actor_user_id=auth.user_id(user),
        )
    if case.status == IncidentStatus.LEADERSHIP_ACK_REQUIRED:
        raise ValidationError("complete leadership acknowledgement before closure")
    if case.status != IncidentStatus.CLOSURE_REVIEW:
        raise ValidationError("incident must reach closure review before close")
    now = eventing.utcnow()
    closed_case = incident_ops.set_status(
        repo=repo,
        case=case,
        status=IncidentStatus.CLOSED,
        actor_user_id=auth.user_id(user),
    )
    updated = replace(closed_case, closed_at=now)
    repo.update_incident(updated)
    summary, details = eventing.timeline_summary(TimelineEntryType.CLOSED)
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.CLOSED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.close",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.incident.closed.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id},
    )
    return updated


def archive_incident(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
) -> object:
    auth.require_qmb(user)
    case = repo.get_incident(incident_id)
    if case.status != IncidentStatus.CLOSED:
        raise ValidationError("incident must be closed before archive")
    now = eventing.utcnow()
    archived_case = incident_ops.set_status(
        repo=repo,
        case=case,
        status=IncidentStatus.ARCHIVED,
        actor_user_id=auth.user_id(user),
    )
    updated = replace(archived_case, archived_at=now)
    repo.update_incident(updated)
    summary, details = eventing.timeline_summary(TimelineEntryType.ARCHIVED)
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.ARCHIVED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.archive",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.incident.archived.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id},
    )
    return updated
