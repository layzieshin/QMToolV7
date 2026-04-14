from __future__ import annotations

from interfaces.pyqt.registry.contribution import QtModuleContribution


def normalize_role(role: str | None) -> str:
    if role is None:
        return ""
    raw = str(role).strip().upper()
    if raw in {"ADMIN", "QMB", "USER"}:
        return raw
    return raw


class ContributionVisibilityPolicy:
    @staticmethod
    def is_visible_for_user(contribution: QtModuleContribution, user: object | None) -> bool:
        if contribution.requires_login and user is None:
            return False
        if contribution.allowed_roles is None:
            return True
        if user is None:
            return False
        normalized_user_role = normalize_role(getattr(user, "role", None))
        allowed = {normalize_role(v) for v in contribution.allowed_roles}
        return normalized_user_role in allowed
