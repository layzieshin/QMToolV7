"""Incident grouping operations."""
from __future__ import annotations

from dataclasses import replace

from . import authorization as auth
from . import eventing
from .contracts import (
    IncidentGroup,
    IncidentTimelineEntry,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository
from .validation import require_non_empty


def create_incident_group(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    name: str,
    description: str | None = None,
) -> IncidentGroup:
    auth.require_qmb(user)
    now = eventing.utcnow()
    group = IncidentGroup(
        group_id=eventing.new_id(),
        name=require_non_empty(name, "name"),
        description=description,
        created_by_user_id=auth.user_id(user),
        created_at=now,
    )
    repo.insert_group(group)
    eventing.emit_audit(
        audit_logger,
        action="incident.group.create",
        actor=auth.user_id(user),
        target=group.group_id,
        result="ok",
    )
    return group


def link_incident_to_group(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    group_id: str,
) -> object:
    auth.require_qmb(user)
    repo.get_group(group_id)
    case = repo.get_incident(incident_id)
    now = eventing.utcnow()
    updated = replace(case, group_id=group_id, updated_at=now)
    repo.update_incident(updated)
    summary, details = eventing.timeline_summary(
        TimelineEntryType.GROUPED,
        group_id=group_id,
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.GROUPED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.group.link",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.incident.grouped.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "group_id": group_id},
    )
    return updated
