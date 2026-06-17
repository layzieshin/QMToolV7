"""Input validation helpers."""
from __future__ import annotations

from datetime import datetime

from .contracts import IncidentAssessmentInput, IncidentSubmission, ValidationError


def require_non_empty(value: str | None, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{field} is required")
    return text


def validate_submission(submission: IncidentSubmission) -> None:
    require_non_empty(submission.title, "title")
    require_non_empty(submission.description, "description")
    require_non_empty(submission.category, "category")
    if submission.reported_at is None:
        raise ValidationError("reported_at is required")


def validate_assessment(assessment: IncidentAssessmentInput) -> None:
    if assessment.is_critical and not (assessment.criticality_reason or "").strip():
        raise ValidationError("criticality_reason is required when incident is critical")
    if assessment.capa_required and not (assessment.capa_reason or "").strip():
        raise ValidationError("capa_reason is required when CAPA is required")


def parse_iso_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)
