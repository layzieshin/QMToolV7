from __future__ import annotations


class HomeDashboardPresenter:
    CARD_TARGETS = {
        "tasks": "documents.workflow",
        "reviews": "documents.workflow",
        "training": "training.workspace",
        "recent": "documents.pool",
    }

    @staticmethod
    def tasks_rows(tasks: list[object]) -> list[str]:
        return [f"{row.document_id} v{row.version} - {row.status.value} - {row.title}" for row in list(tasks[:20])]

    @staticmethod
    def review_rows(items: list[object]) -> list[str]:
        return [f"{row.document_id} v{row.version} - {row.action_required}" for row in list(items[:20])]

    @staticmethod
    def training_rows(items: list[object]) -> list[str]:
        return [f"{row.document_id} v{row.version} - {getattr(row, 'status', '-')}" for row in list(items[:20])]

    @staticmethod
    def recent_rows(items: list[object]) -> list[str]:
        return [f"{row.document_id} v{row.version} - {row.status.value} - {row.title}" for row in list(items[:20])]
