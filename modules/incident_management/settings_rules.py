"""Settings-derived defaults and validation for incident_management."""
from __future__ import annotations

from datetime import datetime, timedelta

from .contracts import ActionType, IncidentSubmission, ValidationError


_ACTION_DEADLINE_KEYS: dict[ActionType, tuple[str, str]] = {
    ActionType.IMMEDIATE_ACTION: ("immediate_action_days", "action_days"),
    ActionType.CORRECTIVE_ACTION: ("corrective_action_days", "action_days"),
    ActionType.PREVENTIVE_ACTION: ("preventive_action_days", "action_days"),
}


def default_action_due_at(settings: dict, action_type: ActionType, *, base: datetime) -> datetime:
    deadlines = settings.get("standard_deadlines") or {}
    primary, fallback = _ACTION_DEADLINE_KEYS.get(action_type, ("action_days", "action_days"))
    days = int(deadlines.get(primary, deadlines.get(fallback, 30)) or 30)
    if days < 1:
        days = 30
    return base + timedelta(days=days)


def qmb_review_deadline_days(settings: dict) -> int:
    deadlines = settings.get("standard_deadlines") or {}
    return max(1, int(deadlines.get("qmb_review_days", deadlines.get("assessment_days", 5)) or 5))


def resolve_report_template_id(settings: dict, report_kind: str) -> str:
    templates = settings.get("report_templates") or {}
    return str(templates.get(report_kind, "default"))


def resolve_criticality_group(settings: dict, *, is_critical: bool) -> str:
    groups = settings.get("criticality_groups") or {}
    if is_critical:
        return str(groups.get("critical", groups.get("default", "standard")))
    return str(groups.get("non_critical", groups.get("default", "standard")))


def validate_submission_against_settings(submission: IncidentSubmission, settings: dict) -> None:
    categories = settings.get("categories") or []
    if categories and submission.category.strip() not in categories:
        raise ValidationError("category is not in configured categories")
    label_groups = settings.get("label_groups") or {}
    if submission.labels and label_groups:
        allowed: set[str] = set()
        for group_labels in label_groups.values():
            if isinstance(group_labels, list):
                allowed.update(str(label) for label in group_labels)
        if allowed:
            unknown = [label for label in submission.labels if label not in allowed]
            if unknown:
                raise ValidationError("labels are not in configured label_groups")
