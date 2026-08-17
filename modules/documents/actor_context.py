"""Map confirmed UserContext to documents workflow actor identity."""

from __future__ import annotations

from modules.usermanagement.api import UserContext, is_effective_qmb, normalize_base_role, require_confirmed_user_context

from .contracts import SystemRole
from .errors import PermissionDeniedError


def actor_user_and_role(actor: UserContext) -> tuple[str, SystemRole]:
    try:
        context = require_confirmed_user_context(actor)
    except Exception as exc:
        raise PermissionDeniedError("confirmed UserContext is required") from exc
    normalized_roles = {
        normalize_base_role(str(raw_role)).strip().upper()
        for raw_role in context.global_roles
        if str(raw_role).strip()
    }
    # Role precedence is explicit and independent of set/frozenset iteration.
    if is_effective_qmb(context):
        role = SystemRole.QMB
    elif "ADMIN" in normalized_roles:
        role = SystemRole.ADMIN
    elif "QMB" in normalized_roles:
        role = SystemRole.QMB
    else:
        role = SystemRole.USER
    user_id = str(context.user_id).strip()
    if not user_id:
        raise PermissionDeniedError("user_id is required")
    return user_id, role
