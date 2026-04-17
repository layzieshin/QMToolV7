from __future__ import annotations

from interfaces.pyqt.contributions.common import normalize_role
from modules.usermanagement.role_policies import is_effective_qmb

class SettingsPolicyPresenter:
    @staticmethod
    def is_privileged(user_or_role: object | None) -> bool:
        if user_or_role is None:
            return False
        if not isinstance(user_or_role, str) and is_effective_qmb(user_or_role):
            return True
        normalized = normalize_role(user_or_role if isinstance(user_or_role, str) else getattr(user_or_role, "role", None))
        return normalized in {"ADMIN", "QMB"}

    @staticmethod
    def summarize_governance_ack(*, acknowledged: bool) -> str:
        return "Governance-Ack gesetzt" if acknowledged else "Governance-Ack fehlt"
