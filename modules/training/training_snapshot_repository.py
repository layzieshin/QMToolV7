"""Repository for snapshots and training progress."""
from __future__ import annotations

import sqlite3

from datetime import datetime, timezone
from pathlib import Path

from ._db import connect

from .contracts import AssignmentSource, TrainingAssignmentSnapshot, TrainingProgress


class TrainingSnapshotRepository:
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

    # --- Snapshots ---

    def upsert_snapshot(self, snap: TrainingAssignmentSnapshot) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO training_assignment_snapshots
                (snapshot_id, user_id, document_id, version, source, exempted, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (snap.snapshot_id, snap.user_id, snap.document_id, snap.version,
                 snap.source.value, 1 if snap.exempted else 0,
                 snap.created_at.isoformat(), snap.updated_at.isoformat()),
            )
            conn.commit()

    def delete_all_snapshots(self) -> None:
        with connect(self._db_path) as conn:
            conn.execute("DELETE FROM training_assignment_snapshots")
            conn.commit()

    def list_snapshots(self) -> list[TrainingAssignmentSnapshot]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_assignment_snapshots ORDER BY user_id, document_id, version"
            ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def list_snapshots_for_user(self, user_id: str) -> list[TrainingAssignmentSnapshot]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_assignment_snapshots WHERE user_id = ? ORDER BY document_id, version",
                (user_id,),
            ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def get_snapshot(self, user_id: str, document_id: str, version: int) -> TrainingAssignmentSnapshot | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM training_assignment_snapshots WHERE user_id=? AND document_id=? AND version=?",
                (user_id, document_id, version),
            ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def _row_to_snapshot(self, r: sqlite3.Row) -> TrainingAssignmentSnapshot:
        return TrainingAssignmentSnapshot(
            snapshot_id=str(r["snapshot_id"]),
            user_id=str(r["user_id"]),
            document_id=str(r["document_id"]),
            version=int(r["version"]),
            source=AssignmentSource(str(r["source"])),
            exempted=bool(r["exempted"]),
            created_at=self._parse_dt(str(r["created_at"])) or datetime.now(timezone.utc),
            updated_at=self._parse_dt(str(r["updated_at"])) or datetime.now(timezone.utc),
        )

    # --- Progress ---

    def upsert_progress(self, p: TrainingProgress) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO training_progress
                (user_id, document_id, version, read_confirmed_at, quiz_passed_at, last_failed_at, last_score, quiz_attempts_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (p.user_id, p.document_id, p.version,
                 p.read_confirmed_at.isoformat() if p.read_confirmed_at else None,
                 p.quiz_passed_at.isoformat() if p.quiz_passed_at else None,
                 p.last_failed_at.isoformat() if p.last_failed_at else None,
                 p.last_score, p.quiz_attempts_count),
            )
            conn.commit()

    def get_progress(self, user_id: str, document_id: str, version: int) -> TrainingProgress | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM training_progress WHERE user_id=? AND document_id=? AND version=?",
                (user_id, document_id, version),
            ).fetchone()
        if row is None:
            return None
        return TrainingProgress(
            user_id=str(row["user_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            read_confirmed_at=self._parse_dt(row["read_confirmed_at"]) if row["read_confirmed_at"] else None,
            quiz_passed_at=self._parse_dt(row["quiz_passed_at"]) if row["quiz_passed_at"] else None,
            last_failed_at=self._parse_dt(row["last_failed_at"]) if row["last_failed_at"] else None,
            last_score=int(row["last_score"]) if row["last_score"] is not None else None,
            quiz_attempts_count=int(row["quiz_attempts_count"]),
        )

    def list_all_progress(self) -> list[TrainingProgress]:
        with connect(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM training_progress ORDER BY user_id, document_id, version").fetchall()
        return [
            TrainingProgress(
                user_id=str(r["user_id"]),
                document_id=str(r["document_id"]),
                version=int(r["version"]),
                read_confirmed_at=self._parse_dt(r["read_confirmed_at"]) if r["read_confirmed_at"] else None,
                quiz_passed_at=self._parse_dt(r["quiz_passed_at"]) if r["quiz_passed_at"] else None,
                last_failed_at=self._parse_dt(r["last_failed_at"]) if r["last_failed_at"] else None,
                last_score=int(r["last_score"]) if r["last_score"] is not None else None,
                quiz_attempts_count=int(r["quiz_attempts_count"]),
            )
            for r in rows
        ]

    # --- infra ---

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with connect(self._db_path) as conn:
            conn.executescript(sql)
            cols = {
                str(r["name"])
                for r in conn.execute("PRAGMA table_info(training_progress)").fetchall()
            }
            if "last_failed_at" not in cols:
                conn.execute("ALTER TABLE training_progress ADD COLUMN last_failed_at TEXT")
            conn.commit()

