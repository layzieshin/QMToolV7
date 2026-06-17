"""Incident submission and query operations."""
from __future__ import annotations

from dataclasses import replace

from . import authorization as auth
from . import eventing
from . import status_transitions
from .contracts import (
    IncidentCase,
    IncidentListFilter,
    IncidentStatus,
    IncidentSubmission,
    IncidentTimelineEntry,
    TimelineEntryType,
)
from .sqlite_repository import SQLiteIncidentRepository
from .settings_rules import validate_submission_against_settings
from .validation import validate_submission


def submit_incident(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    submission: IncidentSubmission,
    settings: dict | None = None,
) -> IncidentCase:
    auth.require_authenticated(user)
    validate_submission(submission)
    if settings:
        validate_submission_against_settings(submission, settings)
    now = eventing.utcnow()
    incident_id = repo.allocate_incident_id(submission.reported_at)
    case = IncidentCase(
        incident_id=incident_id,
        status=IncidentStatus.SUBMITTED,
        reporter_user_id=auth.user_id(user),
        reported_at=submission.reported_at,
        title=submission.title.strip(),
        description=submission.description.strip(),
        category=submission.category.strip(),
        labels=submission.labels,
        area=submission.area,
        process_name=submission.process_name,
        device=submission.device,
        classification=None,
        is_critical=None,
        criticality_reason=None,
        is_repeated=None,
        capa_required=None,
        capa_reason=None,
        root_cause_required=None,
        group_id=None,
        leadership_required=False,
        created_at=now,
        updated_at=now,
    )
    repo.insert_incident(case)
    summary, details = eventing.timeline_summary(TimelineEntryType.SUBMITTED, incident_id=incident_id)
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.SUBMITTED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.submit",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.incident.submitted.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "status": case.status.value},
    )
    return case


def get_incident(*, repo: SQLiteIncidentRepository, user: object, incident_id: str) -> IncidentCase:
    case = repo.get_incident(incident_id)
    auth.require_can_read_incident(user, case)
    return case


def list_incidents(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
    flt: IncidentListFilter | None = None,
) -> list[IncidentCase]:
    # Product rule: all authenticated users see all incidents (no per-case filter).
    auth.require_authenticated(user)
    return repo.list_incidents(flt)


def list_my_incidents(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
) -> list[IncidentCase]:
    return list_incidents(
        repo=repo,
        user=user,
        flt=IncidentListFilter(reporter_user_id=auth.user_id(user)),
    )


def list_incident_timeline(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
    incident_id: str,
) -> list[IncidentTimelineEntry]:
    case = repo.get_incident(incident_id)
    auth.require_can_read_incident(user, case)
    return repo.list_timeline(incident_id)


def set_status(
    *,
    repo: SQLiteIncidentRepository,
    case: IncidentCase,
    status: IncidentStatus,
    actor_user_id: str | None = None,
    skip_validation: bool = False,
) -> IncidentCase:
    if not skip_validation:
        status_transitions.validate_transition(case.status, status)
    now = eventing.utcnow()
    updated = replace(case, status=status, updated_at=now)
    repo.update_incident(updated)
    summary, details = eventing.timeline_summary(
        TimelineEntryType.STATUS_CHANGED,
        from_status=case.status.value,
        to_status=status.value,
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=case.incident_id,
            entry_type=TimelineEntryType.STATUS_CHANGED,
            actor_user_id=actor_user_id,
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    return updated
