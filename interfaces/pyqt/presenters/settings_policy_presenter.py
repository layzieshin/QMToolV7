from __future__ import annotations


class SettingsPolicyPresenter:
    @staticmethod
    def is_privileged(role: str | None) -> bool:
        normalized = str(role or "").strip().upper()
        return normalized in {"ADMIN", "QMB"}

    @staticmethod
    def summarize_governance_ack(*, acknowledged: bool) -> str:
        return "Governance-Ack gesetzt" if acknowledged else "Governance-Ack fehlt"
