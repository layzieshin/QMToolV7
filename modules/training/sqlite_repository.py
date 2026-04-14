from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .contracts import (
    QuizResult,
    QuizSession,
    TrainingAssignment,
    TrainingAssignmentStatus,
    TrainingCategory,
    TrainingComment,
)


class SQLiteTrainingRepository:
    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_dt(raw: str | None) -> datetime | None:
        if raw is None or not str(raw).strip():
            return None
        value = datetime.fromisoformat(str(raw))
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def __init__(self, db_path: Path, schema_path: Path) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert_category(self, category: TrainingCategory) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO training_categories (category_id, name, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (category.category_id, category.name, category.description, category.created_at.isoformat()),
            )
            conn.commit()

    def assign_document_to_category(self, category_id: str, document_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO training_category_documents (category_id, document_id) VALUES (?, ?)",
                (category_id, document_id),
            )
            conn.commit()

    def assign_user_to_category(self, category_id: str, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO training_user_categories (category_id, user_id) VALUES (?, ?)",
                (category_id, user_id),
            )
            conn.commit()

    def list_user_ids_by_category(self, category_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id FROM training_user_categories WHERE category_id = ? ORDER BY user_id ASC",
                (category_id,),
            ).fetchall()
        return [str(r["user_id"]) for r in rows]

    def list_document_ids_by_category(self, category_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT document_id FROM training_category_documents WHERE category_id = ? ORDER BY document_id ASC",
                (category_id,),
            ).fetchall()
        return [str(r["document_id"]) for r in rows]

    def list_categories(self) -> list[TrainingCategory]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT category_id, name, description, created_at FROM training_categories ORDER BY category_id ASC"
            ).fetchall()
        return [
            TrainingCategory(
                category_id=str(r["category_id"]),
                name=str(r["name"]),
                description=r["description"],
                created_at=self._parse_dt(str(r["created_at"])) or datetime.now(timezone.utc),
            )
            for r in rows
        ]

    def upsert_assignment(self, assignment: TrainingAssignment) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO training_assignments (
                    assignment_id, user_id, document_id, version, category_id, status, active,
                    read_confirmed_at, quiz_passed_at, last_score, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assignment.assignment_id,
                    assignment.user_id,
                    assignment.document_id,
                    assignment.version,
                    assignment.category_id,
                    assignment.status.value,
                    1 if assignment.active else 0,
                    assignment.read_confirmed_at.isoformat() if assignment.read_confirmed_at else None,
                    assignment.quiz_passed_at.isoformat() if assignment.quiz_passed_at else None,
                    assignment.last_score,
                    assignment.created_at.isoformat(),
                    assignment.updated_at.isoformat(),
                ),
            )
            conn.commit()

    def list_assignments_by_user(self, user_id: str) -> list[TrainingAssignment]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM training_assignments
                WHERE user_id = ?
                ORDER BY active DESC, document_id ASC, version DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._row_to_assignment(r) for r in rows]

    def get_assignment(self, user_id: str, document_id: str, version: int) -> TrainingAssignment | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM training_assignments
                WHERE user_id = ? AND document_id = ? AND version = ? AND active = 1
                ORDER BY updated_at DESC LIMIT 1
                """,
                (user_id, document_id, version),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_assignment(row)

    def list_active_assignments_for_user_document(self, user_id: str, document_id: str) -> list[TrainingAssignment]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM training_assignments
                WHERE user_id = ? AND document_id = ? AND active = 1
                ORDER BY version DESC
                """,
                (user_id, document_id),
            ).fetchall()
        return [self._row_to_assignment(r) for r in rows]

    def list_assignments_matrix(self) -> list[TrainingAssignment]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM training_assignments ORDER BY user_id, document_id, version DESC").fetchall()
        return [self._row_to_assignment(r) for r in rows]

    def upsert_quiz_set(self, document_id: str, version: int, storage_key: str, sha256: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO training_quiz_sets(document_id, version, storage_key, sha256, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (document_id, version, storage_key, sha256, self._utcnow_iso()),
            )
            conn.commit()

    def get_quiz_set(self, document_id: str, version: int) -> tuple[str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT storage_key, sha256 FROM training_quiz_sets WHERE document_id = ? AND version = ?",
                (document_id, version),
            ).fetchone()
        if row is None:
            return None
        return str(row["storage_key"]), str(row["sha256"])

    def create_quiz_session(self, session: QuizSession) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO training_quiz_attempts(
                    session_id, user_id, document_id, version, selected_question_ids_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.user_id,
                    session.document_id,
                    session.version,
                    json.dumps(list(session.selected_question_ids), ensure_ascii=True),
                    session.created_at.isoformat(),
                ),
            )
            conn.commit()

    def get_quiz_session(self, session_id: str) -> QuizSession | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM training_quiz_attempts WHERE session_id = ?",
                (session_id,),
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
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE training_quiz_attempts
                SET answers_json = ?, score = ?, total = ?, passed = ?, completed_at = ?
                WHERE session_id = ?
                """,
                (
                    json.dumps(answers, ensure_ascii=True),
                    result.score,
                    result.total,
                    1 if result.passed else 0,
                    result.completed_at.isoformat(),
                    result.session_id,
                ),
            )
            conn.commit()

    def add_comment(self, comment: TrainingComment) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO training_comments(comment_id, user_id, document_id, version, comment_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    comment.comment_id,
                    comment.user_id,
                    comment.document_id,
                    comment.version,
                    comment.comment_text,
                    comment.created_at.isoformat(),
                ),
            )
            conn.commit()

    def _row_to_assignment(self, row: sqlite3.Row) -> TrainingAssignment:
        return TrainingAssignment(
            assignment_id=str(row["assignment_id"]),
            user_id=str(row["user_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            category_id=str(row["category_id"]),
            status=TrainingAssignmentStatus(str(row["status"])),
            active=bool(row["active"]),
            read_confirmed_at=self._parse_dt(str(row["read_confirmed_at"])) if row["read_confirmed_at"] else None,
            quiz_passed_at=self._parse_dt(str(row["quiz_passed_at"])) if row["quiz_passed_at"] else None,
            last_score=int(row["last_score"]) if row["last_score"] is not None else None,
            created_at=self._parse_dt(str(row["created_at"])) or datetime.now(timezone.utc),
            updated_at=self._parse_dt(str(row["updated_at"])) or datetime.now(timezone.utc),
        )

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
