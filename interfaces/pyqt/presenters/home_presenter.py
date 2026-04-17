from __future__ import annotations


class HomeDashboardPresenter:
    CARD_TARGETS = {
        "tasks": "documents.workflow",
        "reviews": "documents.workflow",
        "training": "training.workspace",
        "recent": "documents.pool",
        "admin_backup": "platform.audit_logs",
        "admin_pending_registrations": "platform.settings_admin",
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

    @staticmethod
    def backup_rows(days_since: int | None, *, overdue: bool) -> list[str]:
        if not overdue:
            return ["Letztes Backup liegt innerhalb des erlaubten Intervalls."]
        if days_since is None:
            return ["Noch kein Logs-Backup vorhanden."]
        return [f"Letztes Backup vor {days_since} Tagen."]

    @staticmethod
    def pending_registration_rows(users: list[object]) -> list[str]:
        return [f"@{getattr(user, 'username', '')}" for user in list(users[:20])]
