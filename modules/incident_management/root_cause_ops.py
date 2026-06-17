"""Root cause analysis operations."""
from __future__ import annotations

from . import authorization as auth
from . import eventing
from . import incident_ops
from .contracts import (
    IncidentStatus,
    IncidentTimelineEntry,
    RootCauseAnalysis,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository


def create_root_cause_analysis(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    immediate_event: str | None = None,
    trigger: str | None = None,
    root_causes: str | None = None,
    similar_prior: str | None = None,
    systemic_weakness: str | None = None,
    future_risk: str | None = None,
    method: str | None = None,
) -> RootCauseAnalysis:
    auth.require_qmb(user)
    case = repo.get_incident(incident_id)
    if not case.root_cause_required and not case.capa_required:
        raise ValidationError("root cause analysis not required for this incident")
    now = eventing.utcnow()
    existing = repo.get_rca(incident_id)
    rca = RootCauseAnalysis(
        rca_id=existing.rca_id if existing else eventing.new_id(),
        incident_id=incident_id,
        immediate_event=immediate_event,
        trigger=trigger,
        root_causes=root_causes,
        similar_prior=similar_prior,
        systemic_weakness=systemic_weakness,
        future_risk=future_risk,
        method=method,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    repo.upsert_rca(rca)
    if case.status == IncidentStatus.ROOT_CAUSE_REQUIRED:
        incident_ops.set_status(
            repo=repo,
            case=case,
            status=IncidentStatus.ROOT_CAUSE_IN_PROGRESS,
            actor_user_id=auth.user_id(user),
        )
    summary, details = eventing.timeline_summary(TimelineEntryType.RCA_CREATED, rca_id=rca.rca_id)
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.RCA_CREATED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.rca.create",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.incident.rca.created.v1",
        actor_user_id=auth.user_id(user),
        payload={"incident_id": incident_id, "rca_id": rca.rca_id},
    )
    return rca
