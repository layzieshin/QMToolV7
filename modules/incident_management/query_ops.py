"""Query and queue operations for incident_management."""
from __future__ import annotations

from . import authorization as auth
from .contracts import (
    EffectivenessReview,
    IncidentAction,
    IncidentCase,
    IncidentInquiry,
    IncidentStatus,
    SimilarIncidentQuery,
)
from .sqlite_repository import SQLiteIncidentRepository

# Migrated from PyQt presenter filter_qmb_queue (Package B).
_QMB_REVIEW_QUEUE_STATUSES = frozenset({
    IncidentStatus.SUBMITTED,
    IncidentStatus.QMB_REVIEW,
    IncidentStatus.INQUIRY_OPEN,
    IncidentStatus.INQUIRY_ANSWERED,
})


def list_similar_incidents(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
    query: SimilarIncidentQuery,
) -> list[IncidentCase]:
    auth.require_qmb(user)
    return repo.list_similar_incidents(query)


def list_qmb_review_queue(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
) -> list[IncidentCase]:
    """Incidents awaiting QMB assessment (classification still null)."""
    auth.require_qmb(user)
    cases = repo.list_incidents()
    return [
        case
        for case in cases
        if case.status in _QMB_REVIEW_QUEUE_STATUSES and case.classification is None
    ]


def list_open_inquiries(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
) -> list[IncidentInquiry]:
    auth.require_qmb(user)
    return repo.list_open_inquiries()


def list_open_actions(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
) -> list[IncidentAction]:
    auth.require_qmb(user)
    return repo.list_all_open_actions()


def list_pending_effectiveness_reviews(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
) -> list[EffectivenessReview]:
    auth.require_qmb(user)
    return repo.list_pending_effectiveness_reviews()


def list_similar_incident_candidates(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
    incident_id: str,
) -> list[IncidentCase]:
    auth.require_qmb(user)
    case = repo.get_incident(incident_id)
    query = SimilarIncidentQuery(
        incident_id=incident_id,
        category=case.category,
        labels=case.labels,
        area=case.area,
        process_name=case.process_name,
        device=case.device,
    )
    return repo.list_similar_incidents(query)


def list_capa_relevant_incidents(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
) -> list[IncidentCase]:
    """Open incidents flagged as CAPA-relevant (migrated from PyQt _count_capa filter)."""
    auth.require_qmb(user)
    return [
        case
        for case in repo.list_incidents()
        if case.capa_required is True
        and case.status not in (IncidentStatus.CLOSED, IncidentStatus.ARCHIVED)
    ]
