"""Repository for training audit log and reporting queries."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ._db import connect

from .contracts import TrainingAuditLogItem


class TrainingReportRepository:
    def __init__(self, db_path: Path, schema_path: Path) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @staticmethod
    def _parse_dt(raw: str | None) -> datetime | None:
        if raw is None or not str(raw).strip():
            return None
        v = datetime.fromisoformat(str(raw))
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)

    def add_audit_entry(self, item: TrainingAuditLogItem) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO training_audit_log (log_id, action, actor_user_id, timestamp, details_json)
                VALUES (?, ?, ?, ?, ?)""",
                (item.log_id, item.action, item.actor_user_id,
                 item.timestamp.isoformat(), json.dumps(item.details, default=str, ensure_ascii=True)),
            )
            conn.commit()

    def list_audit_log(self, limit: int = 200) -> list[TrainingAuditLogItem]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            TrainingAuditLogItem(
                log_id=str(r["log_id"]),
                action=str(r["action"]),
                actor_user_id=str(r["actor_user_id"]),
                timestamp=self._parse_dt(str(r["timestamp"])) or datetime.now(timezone.utc),
                details=json.loads(str(r["details_json"])),
            )
            for r in rows
        ]

    def count_snapshots_by_status(self) -> dict[str, int]:
        """Return counts grouped by progress status for statistics."""
        with connect(self._db_path) as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM training_assignment_snapshots WHERE exempted=0").fetchone()
            completed = conn.execute(
                "SELECT COUNT(*) as c FROM training_progress WHERE quiz_passed_at IS NOT NULL"
            ).fetchone()
            read_only = conn.execute(
                "SELECT COUNT(*) as c FROM training_progress WHERE read_confirmed_at IS NOT NULL AND quiz_passed_at IS NULL"
            ).fetchone()
        return {
            "total": int(total["c"]) if total else 0,
            "completed": int(completed["c"]) if completed else 0,
            "read_only": int(read_only["c"]) if read_only else 0,
        }

    def export_matrix_rows(self) -> list[dict[str, object]]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT s.user_id, s.document_id, s.version, s.source, s.exempted,
                          p.read_confirmed_at, p.quiz_passed_at, p.last_score, p.quiz_attempts_count
                   FROM training_assignment_snapshots s
                   LEFT JOIN training_progress p
                     ON s.user_id = p.user_id AND s.document_id = p.document_id AND s.version = p.version
                   ORDER BY s.user_id, s.document_id, s.version"""
            ).fetchall()
        return [dict(r) for r in rows]

    # --- infra ---

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with connect(self._db_path) as conn:
            conn.executescript(sql)
            conn.commit()

