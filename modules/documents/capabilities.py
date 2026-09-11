"""Authoritative documents action capabilities.

The HTTP host serializes these results but does not decide workflow permissions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from modules.usermanagement.api import UserContext, is_effective_qmb

from .actor_context import actor_user_and_role
from .contracts import DocumentVersionState, SystemRole
from .docx_to_pdf import docx_conversion_available
from .service import DocumentsService
from .workflow_policy import ACTION_IDS, available_workflow_actions, evaluate_workflow_action

_ARTIFACT_ACCESS_CODES = frozenset({"preview", "download"})

Severity = Literal["info", "warning", "danger"]


@dataclass(frozen=True)
class ActionDescriptor:
    code: str
    label_key: str
    enabled: bool
    disabled_reason: str | None
    requires_reason: bool
    requires_confirmation: bool
    destructive: bool
    severity: Severity


_ACTION_DESCRIPTOR_METADATA: dict[str, dict[str, bool | Severity]] = {
    "review_reject": {
        "requires_reason": True,
        "requires_confirmation": False,
        "destructive": False,
        "severity": "warning",
    },
    "approval_reject": {
        "requires_reason": True,
        "requires_confirmation": False,
        "destructive": False,
        "severity": "warning",
    },
    "abort": {
        "requires_reason": False,
        "requires_confirmation": True,
        "destructive": True,
        "severity": "danger",
    },
    "archive": {
        "requires_reason": False,
        "requires_confirmation": True,
        "destructive": True,
        "severity": "danger",
    },
    "change_requests": {
        "requires_reason": True,
        "requires_confirmation": False,
        "destructive": False,
        "severity": "warning",
    },
    "extend_validity": {
        "requires_reason": True,
        "requires_confirmation": False,
        "destructive": False,
        "severity": "warning",
    },
}

_DEFAULT_DESCRIPTOR_METADATA: dict[str, bool | Severity] = {
    "requires_reason": False,
    "requires_confirmation": False,
    "destructive": False,
    "severity": "info",
}


def _descriptor_metadata(action: str) -> dict[str, bool | Severity]:
    return {**_DEFAULT_DESCRIPTOR_METADATA, **_ACTION_DESCRIPTOR_METADATA.get(action, {})}


def _artifact_access_enabled(
    state: DocumentVersionState,
    *,
    user_id: str,
    role: SystemRole,
) -> bool:
    return DocumentsService._has_read_access(state, actor_user_id=user_id, actor_role=role)


def _artifact_access_descriptors(
    state: DocumentVersionState,
    *,
    user_id: str,
    role: SystemRole,
) -> list[ActionDescriptor]:
    enabled = _artifact_access_enabled(state, user_id=user_id, role=role)
    disabled_reason = None if enabled else "document is not visible to the current actor"
    descriptors: list[ActionDescriptor] = []
    for code in sorted(_ARTIFACT_ACCESS_CODES):
        descriptors.append(
            ActionDescriptor(
                code=code,
                label_key=f"documents.action.{code}",
                enabled=enabled,
                disabled_reason=disabled_reason,
                requires_reason=False,
                requires_confirmation=False,
                destructive=False,
                severity="info",
            )
        )
    return descriptors


def action_descriptors_for_actor(
    state: DocumentVersionState,
    actor: UserContext,
) -> list[ActionDescriptor]:
    """Return Action-Bar descriptors for workflow and artifact access actions."""
    user_id, role = actor_user_and_role(actor)
    descriptors: list[ActionDescriptor] = []
    for action in sorted(ACTION_IDS):
        decision = evaluate_workflow_action(state, user_id=user_id, role=role, action=action)
        meta = _descriptor_metadata(action)
        descriptors.append(
            ActionDescriptor(
                code=action,
                label_key=f"documents.action.{action}",
                enabled=decision.allowed,
                disabled_reason=None if decision.allowed else decision.reason,
                requires_reason=bool(meta["requires_reason"]),
                requires_confirmation=bool(meta["requires_confirmation"]),
                destructive=bool(meta["destructive"]),
                severity=meta["severity"],  # type: ignore[arg-type]
            )
        )
    descriptors.extend(_artifact_access_descriptors(state, user_id=user_id, role=role))
    return sorted(descriptors, key=lambda item: item.code)


def compute_available_actions(
    state: DocumentVersionState,
    *,
    user_id: str,
    role: SystemRole,
    is_qmb: bool = False,
    is_admin: bool = False,
) -> frozenset[str]:
    """Return Action-Bar IDs currently available to one confirmed actor.

    """
    normalized_user_id = str(user_id).strip()
    if not normalized_user_id:
        return frozenset()

    del is_qmb, is_admin
    return available_workflow_actions(
        state,
        user_id=normalized_user_id,
        role=role,
    )


def available_actions_for_actor(
    state: DocumentVersionState,
    actor: UserContext,
) -> frozenset[str]:
    user_id, role = actor_user_and_role(actor)
    actions = set(
        compute_available_actions(
            state,
            user_id=user_id,
            role=role,
            is_qmb=role == SystemRole.QMB,
            is_admin=role == SystemRole.ADMIN,
        )
    )
    if _artifact_access_enabled(state, user_id=user_id, role=role):
        actions.update(_ARTIFACT_ACCESS_CODES)
    return frozenset(actions)


def compute_global_capabilities(
    actor: UserContext,
    *,
    delegated_create_allowed: bool,
) -> dict[str, bool]:
    """Compute global documents capabilities from confirmed server identity."""
    user_id, role = actor_user_and_role(actor)
    del user_id
    return {
        "can_create_new_documents": role == SystemRole.QMB or bool(delegated_create_allowed),
        "can_administer_workflow_profiles": bool(is_effective_qmb(actor)),
        "can_import_docx": docx_conversion_available(),
    }
