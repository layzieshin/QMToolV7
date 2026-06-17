"""Authorization helpers for incident_management."""
from __future__ import annotations

from .contracts import AuthorizationError, ModuleInternalRole


SYSTEM_ROLES = frozenset({"Admin", "QMB", "User"})


def normalize_system_role(role: str | None) -> str | None:
    if role is None:
        return None
    mapping = {"admin": "Admin", "qmb": "QMB", "user": "User"}
    return mapping.get(role.lower(), role)


def require_authenticated(user: object | None) -> object:
    if user is None:
        raise AuthorizationError("login required")
    return user


def user_id(user: object) -> str:
    return str(getattr(user, "user_id"))


def user_role(user: object) -> str:
    return normalize_system_role(getattr(user, "role", None)) or ""


def is_admin(user: object) -> bool:
    return user_role(user) == "Admin"


def is_qmb(user: object) -> bool:
    role = user_role(user)
    if role == "QMB":
        return True
    if role == "Admin":
        return True
    is_qmb_flag = getattr(user, "is_qmb", False)
    return bool(is_qmb_flag) and role == "User"


def require_admin(user: object) -> None:
    if not is_admin(user):
        raise AuthorizationError("Admin role required")


def require_any_role(user: object, *roles: str) -> None:
    role = user_role(user)
    if role not in roles:
        raise AuthorizationError(f"role {role!r} not allowed; requires {roles!r}")


def require_qmb(user: object) -> None:
    if not is_qmb(user):
        raise AuthorizationError("QMB role required")


def require_admin_or_qmb(user: object) -> None:
    if not (is_admin(user) or is_qmb(user)):
        raise AuthorizationError("Admin or QMB role required")


def require_module_role(
    user: object,
    role: ModuleInternalRole,
    *,
    assignments: list[object],
) -> None:
    uid = user_id(user)
    for item in assignments:
        if getattr(item, "user_id", None) == uid and getattr(item, "role_name", None) == role:
            return
    raise AuthorizationError(f"module role {role.value!r} required")


def has_module_role(user: object, role: ModuleInternalRole, *, assignments: list[object]) -> bool:
    try:
        require_module_role(user, role, assignments=assignments)
    except AuthorizationError:
        return False
    return True


def can_read_incident(user: object, case: object) -> bool:
    """All authenticated users may read any incident (product visibility rule)."""
    try:
        require_authenticated(user)
    except AuthorizationError:
        return False
    _ = case
    return True


def require_can_read_incident(user: object, case: object) -> None:
    require_authenticated(user)
    _ = case


def require_can_answer_inquiry(user: object, case: object, inquiry: object) -> None:
    """Reporter (or future addressed recipient) may answer an open inquiry."""
    require_authenticated(user)
    uid = user_id(user)
    if uid == getattr(case, "reporter_user_id", None):
        return
    _ = inquiry
    raise AuthorizationError("only incident reporter may answer inquiry")


def require_leadership_recipient(user: object, ack: object) -> None:
    require_authenticated(user)
    if getattr(ack, "leadership_user_id", None) != user_id(user):
        raise AuthorizationError("incident not assigned to this leadership user")


def can_manage_module_roles(user: object) -> bool:
    return is_admin(user) or is_qmb(user)


def require_manage_module_roles(user: object) -> None:
    require_admin_or_qmb(user)
