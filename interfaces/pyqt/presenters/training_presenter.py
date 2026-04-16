"""Training presenter – thin UI logic layer (no business logic)."""
from __future__ import annotations

from modules.training.contracts import TrainingInboxItem


class TrainingPresenter:
    @staticmethod
    def filter_rows(payload: list[TrainingInboxItem], *, open_only: bool) -> list[TrainingInboxItem]:
        if not open_only:
            return list(payload)
        return [item for item in payload if not item.quiz_passed]

    @staticmethod
    def status_line(*, rows: int, open_only: bool) -> str:
        return f"Schulungen geladen: {rows} (nur offene: {'ja' if open_only else 'nein'})"

    @staticmethod
    def is_read_enabled(item: TrainingInboxItem | None) -> bool:
        if item is None:
            return False
        return not item.read_confirmed

    @staticmethod
    def is_quiz_start_enabled(item: TrainingInboxItem | None) -> bool:
        if item is None:
            return False
        return item.read_confirmed and item.quiz_available and not item.quiz_passed

    @staticmethod
    def is_comment_enabled(item: TrainingInboxItem | None, *, quiz_attempted: bool) -> bool:
        if item is None:
            return False
        return quiz_attempted

    @staticmethod
    def is_admin(role: str) -> bool:
        return role.strip().upper() in ("ADMIN", "QMB")
