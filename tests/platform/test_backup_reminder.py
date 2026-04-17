from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qm_platform.logging.backup_reminder import BackupReminderService
from qm_platform.logging.log_backup_service import LogBackupService


def test_reminder_is_overdue_after_threshold(tmp_path: Path) -> None:
    state_file = tmp_path / "_state.json"
    old = datetime.now(timezone.utc) - timedelta(days=31)
    state_file.write_text(json.dumps({"last_backup_utc": old.isoformat()}, ensure_ascii=True), encoding="utf-8")
    backup_service = LogBackupService(
        platform_log_file=tmp_path / "platform.log",
        audit_log_file=tmp_path / "audit.log",
        backup_dir=tmp_path / "backups",
        state_file=state_file,
    )
    reminder = BackupReminderService(backup_service, threshold_days=30)
    status = reminder.status()
    assert status.is_overdue is True
    assert status.days_since_last_backup is not None
