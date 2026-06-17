"""QMB assessment operations."""
from __future__ import annotations

from dataclasses import replace

from . import authorization as auth
from . import capa_rules
from . import eventing
from . import incident_ops
from . import settings_rules
from .contracts import (
    IncidentAssessmentInput,
    IncidentCase,
    IncidentClassification,
    IncidentStatus,
    IncidentTimelineEntry,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository
from .validation import validate_assessment


def _effective_root_cause_required(assessment: IncidentAssessmentInput, *, capa_required: bool) -> bool:
    return assessment.root_cause_required or capa_required


def _stored_capa_reason(assessment: IncidentAssessmentInput, *, capa_required: bool) -> str | None:
    reason = (assessment.capa_reason or "").strip() or None
    if capa_required and reason is None:
        return (assessment.criticality_reason or "").strip() or None
    return assessment.capa_reason


def _next_status_after_assessment(
    *,
    classification: IncidentClassification,
    capa_required: bool,
    root_cause_required: bool,
) -> IncidentStatus:
    if not capa_required and not root_cause_required and classification == IncidentClassification.OBSERVATION:
        return IncidentStatus.DOCUMENTATION_ONLY
    if root_cause_required:
        return IncidentStatus.ROOT_CAUSE_REQUIRED
    if capa_required:
        return IncidentStatus.CAPA_REQUIRED
    return IncidentStatus.ASSESSED


def assess_incident(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    settings: dict,
    user: object,
    incident_id: str,
    assessment: IncidentAssessmentInput,
) -> IncidentCase:
    auth.require_qmb(user)
    validate_assessment(assessment)
    case = repo.get_incident(incident_id)
    if case.status in (IncidentStatus.CLOSED, IncidentStatus.ARCHIVED):
        raise ValidationError("cannot assess closed or archived incident")
    if repo.count_open_inquiries(incident_id) > 0:
        raise ValidationError("open inquiry must be answered before assessment")

    capa_required = capa_rules.derive_capa_required(assessment, settings)
    root_cause_required = _effective_root_cause_required(assessment, capa_required=capa_required)
    capa_reason = _stored_capa_reason(assessment, capa_required=capa_required)
    leadership_required = capa_required or assessment.is_critical
    now = eventing.utcnow()
    next_status = _next_status_after_assessment(
        classification=assessment.classification,
        capa_required=capa_required,
        root_cause_required=root_cause_required,
    )
    if case.status == IncidentStatus.SUBMITTED:
        case = incident_ops.set_status(
            repo=repo,
            case=case,
            status=IncidentStatus.QMB_REVIEW,
            actor_user_id=auth.user_id(user),
        )
    case = incident_ops.set_status(
        repo=repo,
        case=case,
        status=next_status,
        actor_user_id=auth.user_id(user),
    )
    updated = replace(
        case,
        classification=assessment.classification,
        is_critical=assessment.is_critical,
        criticality_reason=assessment.criticality_reason,
        is_repeated=assessment.is_repeated,
        capa_required=capa_required,
        capa_reason=capa_reason,
        root_cause_required=root_cause_required,
        group_id=assessment.group_id or case.group_id,
        leadership_required=leadership_required,
    )
    repo.update_incident(updated)
    summary, details = eventing.timeline_summary(
        TimelineEntryType.ASSESSED,
        classification=assessment.classification.value,
        capa_required=str(capa_required),
        patient_safety=str(assessment.patient_safety_relevant),
        system_risk=str(assessment.system_risk_relevant),
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.ASSESSED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.assess",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.incident.assessed.v1",
        actor_user_id=auth.user_id(user),
        payload={
            "incident_id": incident_id,
            "classification": assessment.classification.value,
            "capa_required": capa_required,
            "criticality_group": settings_rules.resolve_criticality_group(
                settings, is_critical=assessment.is_critical
            ),
            "patient_safety_relevant": assessment.patient_safety_relevant,
            "system_risk_relevant": assessment.system_risk_relevant,
        },
    )
    if capa_required:
        eventing.publish_event(
            event_bus,
            "domain.incident_management.capa.required.v1",
            actor_user_id=auth.user_id(user),
            payload={"incident_id": incident_id},
        )
    return updated
