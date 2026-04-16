"""Repository for quiz imports, bindings, replacement history and attempts."""
from __future__ import annotations

import sqlite3

import json
from datetime import datetime, timezone
from pathlib import Path

from ._db import connect

from .contracts import (
    PendingQuizMapping,
    QuizBinding,
    QuizImportResult,
    QuizResult,
    QuizSession,
)


class TrainingQuizRepository:
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

    # --- Quiz Imports ---

    def create_quiz_import(self, qir: QuizImportResult, storage_key: str, sha256: str) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO training_quiz_imports
                (import_id, document_id, document_version, storage_key, sha256, question_count, auto_bound, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (qir.import_id, qir.document_id, qir.document_version,
                 storage_key, sha256, qir.question_count,
                 1 if qir.auto_bound else 0, qir.created_at.isoformat()),
            )
            conn.commit()

    def get_quiz_import(self, import_id: str) -> QuizImportResult | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM training_quiz_imports WHERE import_id = ?", (import_id,)
            ).fetchone()
        if row is None:
            return None
        return QuizImportResult(
            import_id=str(row["import_id"]),
            document_id=str(row["document_id"]),
            document_version=int(row["document_version"]),
            question_count=int(row["question_count"]),
            auto_bound=bool(row["auto_bound"]),
            created_at=self._parse_dt(str(row["created_at"])) or datetime.now(timezone.utc),
        )

    def get_import_storage_key(self, import_id: str) -> tuple[str, str] | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT storage_key, sha256 FROM training_quiz_imports WHERE import_id = ?",
                (import_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["storage_key"]), str(row["sha256"])

    # --- Quiz Bindings ---

    def create_binding(self, b: QuizBinding) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO training_quiz_bindings
                (binding_id, document_id, version, import_id, active, created_at, replaced_at, replaced_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (b.binding_id, b.document_id, b.version, b.import_id,
                 1 if b.active else 0, b.created_at.isoformat(),
                 b.replaced_at.isoformat() if b.replaced_at else None,
                 b.replaced_by),
            )
            conn.commit()

    def get_active_binding(self, document_id: str, version: int) -> QuizBinding | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM training_quiz_bindings WHERE document_id=? AND version=? AND active=1",
                (document_id, version),
            ).fetchone()
        return self._row_to_binding(row) if row else None

    def deactivate_binding(self, binding_id: str, replaced_at: datetime, replaced_by: str) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                "UPDATE training_quiz_bindings SET active=0, replaced_at=?, replaced_by=? WHERE binding_id=?",
                (replaced_at.isoformat(), replaced_by, binding_id),
            )
            conn.commit()

    def list_bindings(self) -> list[QuizBinding]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_quiz_bindings ORDER BY document_id, version, created_at DESC"
            ).fetchall()
        return [self._row_to_binding(r) for r in rows]

    def list_pending_mappings(self) -> list[PendingQuizMapping]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT qi.* FROM training_quiz_imports qi
                LEFT JOIN training_quiz_bindings qb ON qi.import_id = qb.import_id
                WHERE qb.import_id IS NULL
                ORDER BY qi.created_at""",
            ).fetchall()
        return [
            PendingQuizMapping(
                import_id=str(r["import_id"]),
                document_id=str(r["document_id"]),
                document_version=int(r["document_version"]),
                created_at=self._parse_dt(str(r["created_at"])) or datetime.now(timezone.utc),
            )
            for r in rows
        ]

    def create_replacement_history(self, history_id: str, old_binding_id: str,
                                    new_binding_id: str, confirmed_by: str, confirmed_at: datetime) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO training_quiz_replacement_history
                (history_id, old_binding_id, new_binding_id, confirmed_by, confirmed_at)
                VALUES (?, ?, ?, ?, ?)""",
                (history_id, old_binding_id, new_binding_id, confirmed_by, confirmed_at.isoformat()),
            )
            conn.commit()

    def _row_to_binding(self, r: sqlite3.Row) -> QuizBinding:
        return QuizBinding(
            binding_id=str(r["binding_id"]),
            document_id=str(r["document_id"]),
            version=int(r["version"]),
            import_id=str(r["import_id"]),
            active=bool(r["active"]),
            created_at=self._parse_dt(str(r["created_at"])) or datetime.now(timezone.utc),
            replaced_at=self._parse_dt(r["replaced_at"]) if r["replaced_at"] else None,
            replaced_by=str(r["replaced_by"]) if r["replaced_by"] else None,
        )

    # --- Quiz Attempts ---

    def create_quiz_session(self, session: QuizSession) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO training_quiz_attempts
                (session_id, user_id, document_id, version, selected_question_ids_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (session.session_id, session.user_id, session.document_id, session.version,
                 json.dumps(list(session.selected_question_ids), ensure_ascii=True),
                 session.created_at.isoformat()),
            )
            conn.commit()

    def get_quiz_session(self, session_id: str) -> QuizSession | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM training_quiz_attempts WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return QuizSession(
            session_id=str(row["session_id"]),
            user_id=str(row["user_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            selected_question_ids=tuple(json.loads(str(row["selected_question_ids_json"]))),
            created_at=self._parse_dt(str(row["created_at"])) or datetime.now(timezone.utc),
        )

    def complete_quiz_session(self, result: QuizResult, answers: list[int]) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """UPDATE training_quiz_attempts
                SET answers_json=?, score=?, total=?, passed=?, completed_at=?
                WHERE session_id=?""",
                (json.dumps(answers, ensure_ascii=True), result.score, result.total,
                 1 if result.passed else 0, result.completed_at.isoformat(), result.session_id),
            )
            conn.commit()

    def count_attempts_for_user_doc(self, user_id: str, document_id: str, version: int) -> int:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM training_quiz_attempts WHERE user_id=? AND document_id=? AND version=? AND completed_at IS NOT NULL",
                (user_id, document_id, version),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def list_attempts_for_user(self, user_id: str) -> list[dict[str, object]]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_quiz_attempts WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- infra ---

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with connect(self._db_path) as conn:
            conn.executescript(sql)
            conn.commit()

