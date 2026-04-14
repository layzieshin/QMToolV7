from __future__ import annotations


class TrainingPresenter:
    @staticmethod
    def filter_rows(payload: list[object], *, open_only: bool) -> list[object]:
        if not open_only:
            return payload
        return [item for item in payload if not item.read_confirmed or not item.quiz_passed]

    @staticmethod
    def status_line(*, rows: int, open_only: bool) -> str:
        return f"Schulungen geladen: {rows} (nur offene: {'ja' if open_only else 'nein'})"
