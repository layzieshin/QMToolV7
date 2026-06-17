"""Leadership acknowledgement operations."""
from __future__ import annotations

from . import authorization as auth
from . import eventing
from . import incident_ops
from .contracts import (
    IncidentStatus,
    IncidentTimelineEntry,
    LeadershipAckStatus,
    LeadershipAcknowledgement,
    ModuleInternalRole,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository


def forward_to_leadership(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    leadership_user_id: str,
) -> LeadershipAcknowledgement:
    auth.require_qmb(user)
    case = repo.get_incident(incident_id)
    if case.status != IncidentStatus.CLOSURE_REVIEW:
        raise ValidationError("leadership forward only allowed during closure review")
    if not case.leadership_required:
        raise ValidationError("leadership acknowledgement not required for this incident")
    assignments = repo.list_module_roles(ModuleInternalRole.LEITUNG)
    leadership_ids = {a.user_id for a in assignments}
    if leadership_user_id not in leadership_ids:
        raise ValidationError("target user does not have Leitung module role")
    now = eventing.utcnow()
    ack = LeadershipAcknowledgement(
        ack_id=eventing.new_id(),
        incident_id=incident_id,
        forwarded_by_user_id=auth.user_id(user),
        forwarded_at=now,
        leadership_user_id=leadership_user_id,
        comment=None,
        acknowledged_at=None,
        status=LeadershipAckStatus.PENDING,
    )
    repo.add_leadership_ack(ack)
    incident_ops.set_status(
        repo=repo,
        case=case,
        status=IncidentStatus.LEADERSHIP_ACK_REQUIRED,
        actor_user_id=auth.user_id(user),
    )
    summary, details = eventing.timeline_summary(
        TimelineEntryType.LEADERSHIP_FORWARDED,
        leadership_user_id=leadership_user_id,
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.LEADERSHIP_FORWARDED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.leadership.forward",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.leadership.forwarded.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "leadership_user_id": leadership_user_id},
    )
    return ack


def acknowledge_leadership_review(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    comment: str | None = None,
) -> LeadershipAcknowledgement:
    assignments = repo.list_module_roles(ModuleInternalRole.LEITUNG)
    auth.require_module_role(user, ModuleInternalRole.LEITUNG, assignments=assignments)
    ack = repo.get_leadership_ack(incident_id)
    if ack is None:
        raise ValidationError("no leadership forward for incident")
    auth.require_leadership_recipient(user, ack)
    now = eventing.utcnow()
    updated = LeadershipAcknowledgement(
        ack_id=ack.ack_id,
        incident_id=incident_id,
        forwarded_by_user_id=ack.forwarded_by_user_id,
        forwarded_at=ack.forwarded_at,
        leadership_user_id=ack.leadership_user_id,
        comment=comment,
        acknowledged_at=now,
        status=LeadershipAckStatus.ACKNOWLEDGED,
    )
    repo.update_leadership_ack(updated)
    case = repo.get_incident(incident_id)
    if case.status == IncidentStatus.LEADERSHIP_ACK_REQUIRED:
        incident_ops.set_status(
            repo=repo,
            case=case,
            status=IncidentStatus.CLOSURE_REVIEW,
            actor_user_id=auth.user_id(user),
        )
    summary, details = eventing.timeline_summary(TimelineEntryType.LEADERSHIP_ACKNOWLEDGED)
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.LEADERSHIP_ACKNOWLEDGED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.leadership.ack",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.leadership.acknowledged.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id},
    )
    return updated


def list_leadership_queue(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
) -> list[LeadershipAcknowledgement]:
    auth.require_authenticated(user)
    assignments = repo.list_module_roles(ModuleInternalRole.LEITUNG)
    if not auth.has_module_role(user, ModuleInternalRole.LEITUNG, assignments=assignments):
        return []
    return repo.list_leadership_queue(auth.user_id(user))
