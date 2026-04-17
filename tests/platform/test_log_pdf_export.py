from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from qm_platform.logging.log_query_service import LogQueryService


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=True) for r in rows) + "\n", encoding="utf-8")


def test_pdf_export_writes_real_pdf(tmp_path: Path) -> None:
    log_file = tmp_path / "platform.log"
    audit_file = tmp_path / "audit.log"
    rows = [
        {
            "timestamp_utc": "2026-04-10T10:00:00+00:00",
            "action": "documents.start",
            "actor": "admin",
            "target": "DOC-1:v1",
            "result": "ok",
            "reason": "",
        }
    ]
    _write_jsonl(log_file, rows)
    _write_jsonl(audit_file, rows)
    service = LogQueryService(platform_log_file=log_file, audit_log_file=audit_file)
    out = tmp_path / "audit.pdf"
    service.export_audit_pdf(
        out,
        date_from=datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc),
        date_to=datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc),
    )
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
