from __future__ import annotations

import json
from pathlib import Path

from qm_platform.logging.log_backup_service import LogBackupService


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=True) for r in rows) + "\n", encoding="utf-8")


def test_backup_moves_current_lines_to_zip_and_clears_logs(tmp_path: Path) -> None:
    platform_log = tmp_path / "platform.log"
    audit_log = tmp_path / "audit.log"
    _write_jsonl(
        platform_log,
        [{"timestamp_utc": "2026-04-10T10:00:00+00:00", "message": "p1"}],
    )
    _write_jsonl(
        audit_log,
        [{"timestamp_utc": "2026-04-10T10:00:00+00:00", "action": "a1"}],
    )
    service = LogBackupService(
        platform_log_file=platform_log,
        audit_log_file=audit_log,
        backup_dir=tmp_path / "backups",
        state_file=tmp_path / "backups" / "_state.json",
    )
    result = service.create_backup()
    assert result.audit_lines == 1
    assert result.platform_lines == 1
    assert result.zip_path.exists()
    assert audit_log.read_text(encoding="utf-8") == ""
    assert platform_log.read_text(encoding="utf-8") == ""
    assert service.get_last_backup_utc() is not None
