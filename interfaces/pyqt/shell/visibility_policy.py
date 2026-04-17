from __future__ import annotations

from interfaces.pyqt.contributions.common import normalize_role
from interfaces.pyqt.registry.contribution import QtModuleContribution
from modules.usermanagement.role_policies import is_effective_qmb


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
        if "QMB" in allowed and is_effective_qmb(user):
            return True
        return normalized_user_role in allowed
