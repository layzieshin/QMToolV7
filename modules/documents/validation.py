"""Validation helpers for documents module.

Internal module — extracted from service.py (Phase 4A).
"""
from __future__ import annotations

import re
from pathlib import Path

from .contracts import (
    ControlClass,
    DocumentStatus,
    DocumentVersionState,
    SystemRole,
    WorkflowProfile,
)
from .errors import InvalidTransitionError, PermissionDeniedError, ValidationError


_FORBIDDEN_CUSTOM_FIELD_KEYS = {
    "status", "released_at", "approval_completed_at", "approval_completed_by",
    "review_completed_at", "review_completed_by", "document_id", "version",
    "archive", "assignments", "workflow_profile", "workflow_profile_id",
    "doc_type", "control_class", "register_state", "active_version",
}
_FORBIDDEN_CUSTOM_FIELD_PREFIXES = ("status.", "assignments.", "workflow.", "registry.")
_ALLOWED_CUSTOM_FIELD_KEY_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")


def assert_custom_fields_safe(custom_fields: dict[str, object]) -> None:
    overlap = _FORBIDDEN_CUSTOM_FIELD_KEYS.intersection(custom_fields.keys())
    if overlap:
        raise ValidationError(f"custom fields must not override steering fields: {sorted(overlap)}")
    for key, value in custom_fields.items():
        if not _ALLOWED_CUSTOM_FIELD_KEY_RE.match(key):
            raise ValidationError(f"custom field key '{key}' is invalid")
        if any(key.startswith(prefix) for prefix in _FORBIDDEN_CUSTOM_FIELD_PREFIXES):
            raise ValidationError(f"custom field key '{key}' uses forbidden steering prefix")
        _assert_custom_field_value_safe(value, key)


def _assert_custom_field_value_safe(value: object, key: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for item in value:
            _assert_custom_field_value_safe(item, key)
        return
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            if not isinstance(nested_key, str):
                raise ValidationError(f"custom field '{key}' contains non-string nested key")
            _assert_custom_field_value_safe(nested_value, key)
        return
    raise ValidationError(f"custom field '{key}' contains unsupported value type '{type(value).__name__}'")


def assert_state_invariants(state: DocumentVersionState) -> None:
    if state.extension_count < 0 or state.extension_count > 3:
        raise ValidationError("extension_count must be between 0 and 3")
    if state.status not in (DocumentStatus.APPROVED, DocumentStatus.ARCHIVED) and state.extension_count != 0:
        raise ValidationError("extension_count may only be > 0 for APPROVED or ARCHIVED status")
    if state.review_completed_at is not None and state.review_completed_by is None:
        raise ValidationError("review_completed_by must be set when review_completed_at is set")
    if state.approval_completed_at is not None and state.approval_completed_by is None:
        raise ValidationError("approval_completed_by must be set when approval_completed_at is set")
    if state.released_at is not None and state.approval_completed_at is None:
        raise ValidationError("released_at requires approval_completed_at")
    if state.archived_at is not None and state.status != DocumentStatus.ARCHIVED:
        raise ValidationError("archived_at may only be set for ARCHIVED status")
    if state.status != DocumentStatus.ARCHIVED and state.archived_by is not None:
        raise ValidationError("archived_by may only be set for ARCHIVED status")
    if state.valid_from and state.valid_until and state.valid_until < state.valid_from:
        raise ValidationError("valid_until must be greater than or equal to valid_from")
    if state.valid_from and state.next_review_at and state.next_review_at < state.valid_from:
        raise ValidationError("next_review_at must be greater than or equal to valid_from")


def assert_profile(profile: WorkflowProfile) -> None:
    if not profile.phases:
        raise ValidationError("workflow profile requires at least one phase")
    if profile.phases[0] != DocumentStatus.IN_PROGRESS:
        raise ValidationError("workflow profile must start with IN_PROGRESS")
    if profile.phases[-1] != DocumentStatus.APPROVED:
        raise ValidationError("workflow profile must end with APPROVED")


def assert_rejection_reason(reason: object) -> None:
    if not reason.is_valid():
        raise ValidationError("rejection reason requires template text and/or free text")


def assert_active_profile(state: DocumentVersionState) -> None:
    if not state.workflow_active:
        raise InvalidTransitionError("workflow is not active")
    if state.workflow_profile is None:
        raise ValidationError("workflow profile is missing")


def assert_assignments_for_profile(state: DocumentVersionState, profile: WorkflowProfile) -> None:
    if profile.requires_editors and not state.assignments.editors:
        raise ValidationError("workflow-start requires at least one editor for this profile")
    if profile.requires_reviewers and not state.assignments.reviewers:
        raise ValidationError("workflow-start requires at least one reviewer for this profile")
    if profile.requires_approvers and not state.assignments.approvers:
        raise ValidationError("workflow-start requires at least one approver for this profile")
    if state.control_class == ControlClass.EXTERNAL and (
        state.assignments.editors or state.assignments.reviewers or state.assignments.approvers
    ):
        raise ValidationError("external documents must not have internal workflow assignments")


def ensure_owner_or_privileged(state: DocumentVersionState, actor_user_id: str, actor_role: SystemRole) -> None:
    if actor_role in (SystemRole.ADMIN, SystemRole.QMB):
        return
    if state.owner_user_id == actor_user_id:
        return
    raise PermissionDeniedError("only owner, QMB, or ADMIN may execute this action")


def ensure_editor_or_owner_or_privileged(state: DocumentVersionState, actor_user_id: str, actor_role: SystemRole) -> None:
    if actor_role in (SystemRole.ADMIN, SystemRole.QMB):
        return
    if state.owner_user_id == actor_user_id:
        return
    if actor_user_id in state.assignments.editors:
        return
    raise PermissionDeniedError("only assigned editors, owner, QMB, or ADMIN may complete editing")


def ensure_assignment_update_allowed(
    state: DocumentVersionState,
    actor_user_id: str,
    actor_role: SystemRole,
    *,
    new_editors: frozenset[str],
    new_reviewers: frozenset[str],
    new_approvers: frozenset[str],
) -> None:
    if actor_role == SystemRole.ADMIN:
        return
    if actor_role == SystemRole.USER:
        if state.owner_user_id != actor_user_id:
            raise PermissionDeniedError("owner required for role updates")
        if state.edit_signature_done:
            raise PermissionDeniedError("owner cannot update roles after first edit signature")
        return
    if actor_role == SystemRole.QMB:
        if state.status in (DocumentStatus.IN_REVIEW, DocumentStatus.IN_APPROVAL, DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
            if new_editors != state.assignments.editors:
                raise PermissionDeniedError("QMB cannot change editor roles after review phase started")
        if state.status in (DocumentStatus.IN_APPROVAL, DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
            if new_reviewers != state.assignments.reviewers:
                raise PermissionDeniedError("QMB cannot change reviewer roles after approval phase started")
        if state.status in (DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
            if new_approvers != state.assignments.approvers:
                raise PermissionDeniedError("QMB cannot change approver roles after approval completed")
        return
    raise PermissionDeniedError("unsupported role for role updates")


def validate_source_file(source_path: Path, *, allowed_suffixes: set[str]) -> None:
    if not source_path.exists():
        raise ValidationError(f"source file not found: {source_path}")
    suffix = source_path.suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValidationError(f"invalid source file extension '{suffix}', allowed: {sorted(allowed_suffixes)}")


def next_status_from_profile(profile: WorkflowProfile | None, current: DocumentStatus) -> DocumentStatus:
    if profile is None:
        raise ValidationError("workflow profile is required")
    try:
        idx = profile.phases.index(current)
    except ValueError as exc:
        raise ValidationError(f"profile does not contain current status {current.value}") from exc
    if idx >= len(profile.phases) - 1:
        raise InvalidTransitionError("current status is already terminal in profile")
    return profile.phases[idx + 1]


def validate_change_request_input(change_id: str, reason: str, impact_refs: list[str] | tuple[str, ...]) -> tuple[str, str, tuple[str, ...]]:
    normalized_change_id = change_id.strip()
    if not normalized_change_id:
        raise ValidationError("change_id is required")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError("reason is required")
    normalized_refs = tuple(sorted({value.strip() for value in impact_refs if str(value).strip()}))
    return normalized_change_id, normalized_reason, normalized_refs

