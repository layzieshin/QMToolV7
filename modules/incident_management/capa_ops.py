"""CAPA operations."""
from __future__ import annotations

from . import authorization as auth
from . import eventing
from . import incident_ops
from .contracts import (
    CapaStatus,
    IncidentCapa,
    IncidentStatus,
    IncidentTimelineEntry,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository


def start_capa(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    trigger_reason: str | None = None,
    goal: str | None = None,
    description: str | None = None,
) -> IncidentCapa:
    auth.require_qmb(user)
    case = repo.get_incident(incident_id)
    if not case.capa_required:
        raise ValidationError("CAPA is not required for this incident")
    now = eventing.utcnow()
    capa = IncidentCapa(
        capa_id=eventing.new_id(),
        incident_id=incident_id,
        status=CapaStatus.PLANNING,
        trigger_reason=trigger_reason or case.capa_reason,
        goal=goal,
        description=description,
        created_at=now,
        updated_at=now,
    )
    repo.upsert_capa(capa)
    if case.status == IncidentStatus.ROOT_CAUSE_REQUIRED:
        case = incident_ops.set_status(
            repo=repo,
            case=case,
            status=IncidentStatus.CAPA_REQUIRED,
            actor_user_id=auth.user_id(user),
        )
    incident_ops.set_status(
        repo=repo,
        case=case,
        status=IncidentStatus.CAPA_PLANNING,
        actor_user_id=auth.user_id(user),
    )
    summary, details = eventing.timeline_summary(TimelineEntryType.CAPA_STARTED, capa_id=capa.capa_id)
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.CAPA_STARTED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.capa.start",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.capa.updated.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "capa_id": capa.capa_id, "status": capa.status.value},
    )
    return capa


def update_capa(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    status: CapaStatus | None = None,
    goal: str | None = None,
    description: str | None = None,
) -> IncidentCapa:
    auth.require_qmb(user)
    existing = repo.get_capa(incident_id)
    if existing is None:
        raise ValidationError("CAPA not started for incident")
    now = eventing.utcnow()
    capa = IncidentCapa(
        capa_id=existing.capa_id,
        incident_id=incident_id,
        status=status or existing.status,
        trigger_reason=existing.trigger_reason,
        goal=goal if goal is not None else existing.goal,
        description=description if description is not None else existing.description,
        created_at=existing.created_at,
        updated_at=now,
    )
    repo.upsert_capa(capa)
    if capa.status == CapaStatus.IN_PROGRESS:
        case = repo.get_incident(incident_id)
        incident_ops.set_status(
            repo=repo,
            case=case,
            status=IncidentStatus.ACTIONS_IN_PROGRESS,
            actor_user_id=auth.user_id(user),
        )
    summary, details = eventing.timeline_summary(TimelineEntryType.CAPA_UPDATED, capa_id=capa.capa_id)
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.CAPA_UPDATED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.capa.update",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.capa.updated.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "capa_id": capa.capa_id, "status": capa.status.value},
    )
    return capa
