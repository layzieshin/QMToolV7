from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .contracts import UserContext


def normalize_base_role(role: str | None) -> str:
    raw = (role or "").strip().upper()
    if raw == "ADMIN":
        return "ADMIN"
    if raw == "QMB":
        return "QMB"
    if raw == "USER":
        return "USER"
    return raw


def is_effective_qmb(user: object) -> bool:
    role = normalize_base_role(getattr(user, "role", None))
    return role == "QMB" or bool(getattr(user, "is_qmb", False))


def can_administer_users(actor: UserContext) -> bool:
    """Return True only for a server-confirmed actor with Admin global role."""
    if not actor.is_confirmed:
        return False
    return "ADMIN" in actor.global_roles

