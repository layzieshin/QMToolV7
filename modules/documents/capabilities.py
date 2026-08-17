"""Authoritative documents action capabilities.

The HTTP host serializes these results but does not decide workflow permissions.
"""

from __future__ import annotations

from modules.usermanagement.api import UserContext, is_effective_qmb

from .actor_context import actor_user_and_role
from .contracts import DocumentVersionState, SystemRole
from .docx_to_pdf import docx_conversion_available
from .workflow_policy import ACTION_IDS, available_workflow_actions


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
    return compute_available_actions(
        state,
        user_id=user_id,
        role=role,
        is_qmb=role == SystemRole.QMB,
        is_admin=role == SystemRole.ADMIN,
    )


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
