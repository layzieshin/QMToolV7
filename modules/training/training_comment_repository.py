"""Repository for training comments with status model."""
from __future__ import annotations

import sqlite3

from datetime import datetime, timezone
from pathlib import Path

from ._db import connect

from .contracts import CommentStatus, TrainingCommentListItem, TrainingCommentRecord


class TrainingCommentRepository:
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

    def create_comment(self, c: TrainingCommentRecord) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO training_comments
                (comment_id, document_id, version, document_title_snapshot, user_id, username_snapshot,
                 comment_text, page_number, anchor_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (c.comment_id, c.document_id, c.version, c.document_title_snapshot,
                 c.user_id, c.username_snapshot, c.comment_text, c.page_number, c.anchor_json, c.status.value,
                 c.created_at.isoformat(), c.updated_at.isoformat()),
            )
            conn.commit()

    def get_comment(self, comment_id: str) -> TrainingCommentRecord | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM training_comments WHERE comment_id = ?", (comment_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def update_comment(self, c: TrainingCommentRecord) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """UPDATE training_comments SET
                status=?, updated_at=?, resolved_by=?, resolved_at=?, resolution_note=?,
                inactive_by=?, inactive_at=?, inactive_note=?
                WHERE comment_id=?""",
                (c.status.value, c.updated_at.isoformat(),
                 c.resolved_by, c.resolved_at.isoformat() if c.resolved_at else None, c.resolution_note,
                 c.inactive_by, c.inactive_at.isoformat() if c.inactive_at else None, c.inactive_note,
                 c.comment_id),
            )
            conn.commit()

    def list_active_comments(self) -> list[TrainingCommentListItem]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_comments WHERE status = 'ACTIVE' ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_list_item(r) for r in rows]

    def list_comments_for_document(self, document_id: str, version: int) -> list[TrainingCommentListItem]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM training_comments WHERE document_id=? AND version=? ORDER BY created_at DESC",
                (document_id, version),
            ).fetchall()
        return [self._row_to_list_item(r) for r in rows]

    def list_comments_for_user(self, user_id: str, document_id: str, version: int) -> list[TrainingCommentListItem]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM training_comments
                WHERE user_id=? AND document_id=? AND version=?
                ORDER BY created_at DESC
                """,
                (user_id, document_id, version),
            ).fetchall()
        return [self._row_to_list_item(r) for r in rows]

    def _row_to_record(self, r: sqlite3.Row) -> TrainingCommentRecord:
        return TrainingCommentRecord(
            comment_id=str(r["comment_id"]),
            document_id=str(r["document_id"]),
            version=int(r["version"]),
            document_title_snapshot=str(r["document_title_snapshot"]),
            user_id=str(r["user_id"]),
            username_snapshot=str(r["username_snapshot"]),
            comment_text=str(r["comment_text"]),
            page_number=int(r["page_number"]) if r["page_number"] is not None else None,
            anchor_json=str(r["anchor_json"]) if r["anchor_json"] else None,
            status=CommentStatus(str(r["status"])),
            created_at=self._parse_dt(str(r["created_at"])) or datetime.now(timezone.utc),
            updated_at=self._parse_dt(str(r["updated_at"])) or datetime.now(timezone.utc),
            resolved_by=str(r["resolved_by"]) if r["resolved_by"] else None,
            resolved_at=self._parse_dt(r["resolved_at"]) if r["resolved_at"] else None,
            resolution_note=str(r["resolution_note"]) if r["resolution_note"] else None,
            inactive_by=str(r["inactive_by"]) if r["inactive_by"] else None,
            inactive_at=self._parse_dt(r["inactive_at"]) if r["inactive_at"] else None,
            inactive_note=str(r["inactive_note"]) if r["inactive_note"] else None,
        )

    def _row_to_list_item(self, r: sqlite3.Row) -> TrainingCommentListItem:
        return TrainingCommentListItem(
            comment_id=str(r["comment_id"]),
            document_id=str(r["document_id"]),
            version=int(r["version"]),
            document_title_snapshot=str(r["document_title_snapshot"]),
            user_id=str(r["user_id"]),
            username_snapshot=str(r["username_snapshot"]),
            comment_text=str(r["comment_text"]),
            page_number=int(r["page_number"]) if r["page_number"] is not None else None,
            anchor_json=str(r["anchor_json"]) if r["anchor_json"] else None,
            status=CommentStatus(str(r["status"])),
            created_at=self._parse_dt(str(r["created_at"])) or datetime.now(timezone.utc),
        )

    # --- infra ---

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with connect(self._db_path) as conn:
            conn.executescript(sql)
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(training_comments)").fetchall()}
            if "page_number" not in cols:
                conn.execute("ALTER TABLE training_comments ADD COLUMN page_number INTEGER")
            if "anchor_json" not in cols:
                conn.execute("ALTER TABLE training_comments ADD COLUMN anchor_json TEXT")
            conn.commit()

