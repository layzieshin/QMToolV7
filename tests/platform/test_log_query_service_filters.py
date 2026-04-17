from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from qm_platform.logging.log_query_service import LogQueryService


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=True) for r in rows) + "\n", encoding="utf-8")


def test_query_filters_by_utc_date_range(tmp_path: Path) -> None:
    log_file = tmp_path / "platform.log"
    audit_file = tmp_path / "audit.log"
    rows = [
        {"timestamp_utc": "2026-04-01T10:00:00+00:00", "level": "INFO", "message": "old"},
        {"timestamp_utc": "2026-04-10T10:00:00+00:00", "level": "INFO", "message": "keep"},
        {"timestamp_utc": "2026-04-20T10:00:00+00:00", "level": "INFO", "message": "new"},
    ]
    _write_jsonl(log_file, rows)
    _write_jsonl(audit_file, rows)
    service = LogQueryService(platform_log_file=log_file, audit_log_file=audit_file)
    from_dt = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
    to_dt = datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc)
    filtered = service.query_technical_logs(date_from=from_dt, date_to=to_dt, limit=100)
    assert [row["message"] for row in filtered] == ["keep"]
