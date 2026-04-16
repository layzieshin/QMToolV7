"""Repository for manual assignments and exemptions."""
from __future__ import annotations

import sqlite3

from datetime import datetime, timezone
from pathlib import Path

from ._db import connect

from .contracts import ManualAssignment, TrainingExemption


class TrainingOverrideRepository:
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

    # --- Manual Assignments ---

    def create_manual_assignment(self, ma: ManualAssignment) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO training_manual_assignments
                (assignment_id, user_id, document_id, reason, granted_by, granted_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ma.assignment_id, ma.user_id, ma.document_id, ma.reason,
                 ma.granted_by, ma.granted_at.isoformat(), None),
            )
            conn.commit()

    def revoke_manual_assignment(self, assignment_id: str, revoked_at: datetime) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                "UPDATE training_manual_assignments SET revoked_at = ? WHERE assignment_id = ?",
                (revoked_at.isoformat(), assignment_id),
            )
            conn.commit()

    def list_active_manual_assignments(self) -> list[ManualAssignment]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_manual_assignments WHERE revoked_at IS NULL ORDER BY granted_at"
            ).fetchall()
        return [self._row_to_manual(r) for r in rows]

    def list_manual_assignments_for_user(self, user_id: str) -> list[ManualAssignment]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_manual_assignments WHERE user_id = ? AND revoked_at IS NULL",
                (user_id,),
            ).fetchall()
        return [self._row_to_manual(r) for r in rows]

    def _row_to_manual(self, r: sqlite3.Row) -> ManualAssignment:
        return ManualAssignment(
            assignment_id=str(r["assignment_id"]),
            user_id=str(r["user_id"]),
            document_id=str(r["document_id"]),
            reason=str(r["reason"]),
            granted_by=str(r["granted_by"]),
            granted_at=self._parse_dt(str(r["granted_at"])) or datetime.now(timezone.utc),
            revoked_at=self._parse_dt(r["revoked_at"]) if r["revoked_at"] else None,
        )

    # --- Exemptions ---

    def create_exemption(self, ex: TrainingExemption) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO training_exemptions
                (exemption_id, user_id, document_id, version, reason, granted_by, granted_at, valid_until, revoked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ex.exemption_id, ex.user_id, ex.document_id, ex.version, ex.reason,
                 ex.granted_by, ex.granted_at.isoformat(),
                 ex.valid_until.isoformat() if ex.valid_until else None, None),
            )
            conn.commit()

    def revoke_exemption(self, exemption_id: str, revoked_at: datetime) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                "UPDATE training_exemptions SET revoked_at = ? WHERE exemption_id = ?",
                (revoked_at.isoformat(), exemption_id),
            )
            conn.commit()

    def list_active_exemptions(self) -> list[TrainingExemption]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_exemptions WHERE revoked_at IS NULL ORDER BY granted_at"
            ).fetchall()
        return [self._row_to_exemption(r) for r in rows]

    def list_exemptions_for_user_doc(self, user_id: str, document_id: str, version: int) -> list[TrainingExemption]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM training_exemptions
                WHERE user_id = ? AND document_id = ? AND version = ? AND revoked_at IS NULL""",
                (user_id, document_id, version),
            ).fetchall()
        return [self._row_to_exemption(r) for r in rows]

    def _row_to_exemption(self, r: sqlite3.Row) -> TrainingExemption:
        return TrainingExemption(
            exemption_id=str(r["exemption_id"]),
            user_id=str(r["user_id"]),
            document_id=str(r["document_id"]),
            version=int(r["version"]),
            reason=str(r["reason"]),
            granted_by=str(r["granted_by"]),
            granted_at=self._parse_dt(str(r["granted_at"])) or datetime.now(timezone.utc),
            valid_until=self._parse_dt(r["valid_until"]) if r["valid_until"] else None,
            revoked_at=self._parse_dt(r["revoked_at"]) if r["revoked_at"] else None,
        )

    # --- infra ---

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with connect(self._db_path) as conn:
            conn.executescript(sql)
            conn.commit()

