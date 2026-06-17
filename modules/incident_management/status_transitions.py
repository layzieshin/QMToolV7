"""Central incident status transition rules."""
from __future__ import annotations

from .contracts import IncidentStatus, ValidationError

# Allowed transitions: from_status -> set of to_status
_ALLOWED: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    IncidentStatus.SUBMITTED: frozenset({
        IncidentStatus.QMB_REVIEW,
        IncidentStatus.INQUIRY_OPEN,
    }),
    IncidentStatus.QMB_REVIEW: frozenset({
        IncidentStatus.INQUIRY_OPEN,
        IncidentStatus.DOCUMENTATION_ONLY,
        IncidentStatus.ASSESSED,
        IncidentStatus.ROOT_CAUSE_REQUIRED,
        IncidentStatus.CAPA_REQUIRED,
    }),
    IncidentStatus.INQUIRY_OPEN: frozenset({IncidentStatus.INQUIRY_ANSWERED}),
    IncidentStatus.INQUIRY_ANSWERED: frozenset({
        IncidentStatus.QMB_REVIEW,
        IncidentStatus.DOCUMENTATION_ONLY,
        IncidentStatus.ASSESSED,
        IncidentStatus.ROOT_CAUSE_REQUIRED,
        IncidentStatus.CAPA_REQUIRED,
    }),
    IncidentStatus.DOCUMENTATION_ONLY: frozenset({IncidentStatus.CLOSURE_REVIEW}),
    IncidentStatus.ASSESSED: frozenset({
        IncidentStatus.ACTIONS_IN_PROGRESS,
        IncidentStatus.CAPA_PLANNING,
        IncidentStatus.CLOSURE_REVIEW,
    }),
    IncidentStatus.ROOT_CAUSE_REQUIRED: frozenset({
        IncidentStatus.ROOT_CAUSE_IN_PROGRESS,
        IncidentStatus.CAPA_REQUIRED,
    }),
    IncidentStatus.ROOT_CAUSE_IN_PROGRESS: frozenset({
        IncidentStatus.CAPA_REQUIRED,
        IncidentStatus.CAPA_PLANNING,
        IncidentStatus.CLOSURE_REVIEW,
    }),
    IncidentStatus.CAPA_REQUIRED: frozenset({
        IncidentStatus.CAPA_PLANNING,
        IncidentStatus.ROOT_CAUSE_IN_PROGRESS,
    }),
    IncidentStatus.CAPA_PLANNING: frozenset({IncidentStatus.ACTIONS_IN_PROGRESS}),
    IncidentStatus.ACTIONS_IN_PROGRESS: frozenset({
        IncidentStatus.FOLLOW_UP,
        IncidentStatus.EFFECTIVENESS_PLANNED,
    }),
    IncidentStatus.FOLLOW_UP: frozenset({
        IncidentStatus.ACTIONS_IN_PROGRESS,
        IncidentStatus.EFFECTIVENESS_PLANNED,
        IncidentStatus.CAPA_PLANNING,
    }),
    IncidentStatus.EFFECTIVENESS_PLANNED: frozenset({
        IncidentStatus.EFFECTIVENESS_REVIEW,
        IncidentStatus.FOLLOW_UP,
    }),
    IncidentStatus.EFFECTIVENESS_REVIEW: frozenset({
        IncidentStatus.CLOSURE_REVIEW,
        IncidentStatus.FOLLOW_UP,
    }),
    IncidentStatus.CLOSURE_REVIEW: frozenset({
        IncidentStatus.LEADERSHIP_ACK_REQUIRED,
        IncidentStatus.CLOSED,
    }),
    IncidentStatus.LEADERSHIP_ACK_REQUIRED: frozenset({IncidentStatus.CLOSURE_REVIEW}),
    IncidentStatus.CLOSED: frozenset({IncidentStatus.ARCHIVED}),
    IncidentStatus.ARCHIVED: frozenset(),
}


def validate_transition(from_status: IncidentStatus, to_status: IncidentStatus) -> None:
    if from_status == to_status:
        return
    allowed = _ALLOWED.get(from_status, frozenset())
    if to_status not in allowed:
        raise ValidationError(
            f"invalid status transition: {from_status.value} -> {to_status.value}"
        )
