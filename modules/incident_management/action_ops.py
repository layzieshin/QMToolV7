"""Action tracking operations."""
from __future__ import annotations

from datetime import datetime

from . import authorization as auth
from . import eventing
from . import incident_ops
from . import settings_rules
from .contracts import (
    ActionStatus,
    ActionType,
    IncidentAction,
    IncidentStatus,
    IncidentTimelineEntry,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository
from .validation import require_non_empty


def create_action(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    settings: dict,
    user: object,
    incident_id: str,
    action_type: ActionType,
    description: str,
    owner_user_id: str | None = None,
    due_at: datetime | None = None,
) -> IncidentAction:
    auth.require_qmb(user)
    case = repo.get_incident(incident_id)
    if case.classification is None:
        raise ValidationError("incident must be assessed before creating actions")
    text = require_non_empty(description, "description")
    now = eventing.utcnow()
    effective_due_at = due_at if due_at is not None else settings_rules.default_action_due_at(
        settings, action_type, base=now
    )
    action = IncidentAction(
        action_id=eventing.new_id(),
        incident_id=incident_id,
        action_type=action_type,
        status=ActionStatus.OPEN,
        description=text,
        owner_user_id=owner_user_id,
        due_at=effective_due_at,
        completed_at=None,
        completed_by_user_id=None,
        created_at=now,
    )
    repo.add_action(action)
    if case.status in (
        IncidentStatus.ASSESSED,
        IncidentStatus.CAPA_PLANNING,
        IncidentStatus.ACTIONS_IN_PROGRESS,
    ):
        incident_ops.set_status(
            repo=repo,
            case=case,
            status=IncidentStatus.ACTIONS_IN_PROGRESS,
            actor_user_id=auth.user_id(user),
        )
    summary, details = eventing.timeline_summary(
        TimelineEntryType.ACTION_CREATED,
        action_id=action.action_id,
        action_type=action_type.value,
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.ACTION_CREATED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.action.create",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.action.created.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "action_id": action.action_id},
    )
    return action


def complete_action(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    action_id: str,
) -> IncidentAction:
    auth.require_qmb(user)
    action = repo.get_action(action_id)
    now = eventing.utcnow()
    updated = IncidentAction(
        action_id=action.action_id,
        incident_id=action.incident_id,
        action_type=action.action_type,
        status=ActionStatus.COMPLETED,
        description=action.description,
        owner_user_id=action.owner_user_id,
        due_at=action.due_at,
        completed_at=now,
        completed_by_user_id=auth.user_id(user),
        created_at=action.created_at,
    )
    repo.update_action(updated)
    summary, details = eventing.timeline_summary(
        TimelineEntryType.ACTION_COMPLETED,
        action_id=action_id,
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=action.incident_id,
            entry_type=TimelineEntryType.ACTION_COMPLETED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.action.complete",
        actor=auth.user_id(user),
        target=action.incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.action.completed.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": action.incident_id, "action_id": action_id},
    )
    return updated
