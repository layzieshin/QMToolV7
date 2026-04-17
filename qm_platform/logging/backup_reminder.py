from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from qm_platform.logging.log_backup_service import LogBackupService


@dataclass(frozen=True)
class BackupReminderStatus:
    last_backup_utc: datetime | None
    days_since_last_backup: int | None
    threshold_days: int
    is_overdue: bool


class BackupReminderService:
    def __init__(self, backup_service: LogBackupService, *, threshold_days: int = 30) -> None:
        self._backup_service = backup_service
        self._threshold_days = max(int(threshold_days), 1)

    def status(self) -> BackupReminderStatus:
        last_backup = self._backup_service.get_last_backup_utc()
        if last_backup is None:
            return BackupReminderStatus(
                last_backup_utc=None,
                days_since_last_backup=None,
                threshold_days=self._threshold_days,
                is_overdue=True,
            )
        now = datetime.now(timezone.utc)
        days = max((now - last_backup).days, 0)
        return BackupReminderStatus(
            last_backup_utc=last_backup,
            days_since_last_backup=days,
            threshold_days=self._threshold_days,
            is_overdue=days >= self._threshold_days,
        )
