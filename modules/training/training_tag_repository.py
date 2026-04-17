"""Repository for document tags and user tags."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from ._db import connect
from .contracts import DocumentTagSet, UserTagSet


class TrainingTagRepository:
    def __init__(self, db_path: Path, schema_path: Path) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # --- Document Tags ---

    def get_document_tags(self, document_id: str) -> DocumentTagSet:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT tag FROM training_document_tags WHERE document_id = ? ORDER BY tag",
                (document_id,),
            ).fetchall()
        return DocumentTagSet(document_id=document_id, tags=frozenset(r["tag"] for r in rows))

    def set_document_tags(self, document_id: str, tags: list[str]) -> DocumentTagSet:
        normalized = sorted({tag.strip() for tag in tags if tag and tag.strip()})
        with connect(self._db_path) as conn:
            conn.execute("DELETE FROM training_document_tags WHERE document_id = ?", (document_id,))
            for tag in normalized:
                conn.execute(
                    "INSERT INTO training_document_tags (document_id, tag) VALUES (?, ?)",
                    (document_id, tag),
                )
            self._upsert_tag_pool(conn, normalized)
            conn.commit()
        return DocumentTagSet(document_id=document_id, tags=frozenset(normalized))

    def list_all_document_tags(self) -> list[DocumentTagSet]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT document_id, tag FROM training_document_tags ORDER BY document_id, tag"
            ).fetchall()
        result: dict[str, set[str]] = {}
        for r in rows:
            result.setdefault(str(r["document_id"]), set()).add(str(r["tag"]))
        return [DocumentTagSet(document_id=did, tags=frozenset(t)) for did, t in result.items()]

    # --- User Tags ---

    def get_user_tags(self, user_id: str) -> UserTagSet:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT tag FROM training_user_tags WHERE user_id = ? ORDER BY tag",
                (user_id,),
            ).fetchall()
        return UserTagSet(user_id=user_id, tags=frozenset(r["tag"] for r in rows))

    def set_user_tags(self, user_id: str, tags: list[str]) -> UserTagSet:
        normalized = sorted({tag.strip() for tag in tags if tag and tag.strip()})
        with connect(self._db_path) as conn:
            conn.execute("DELETE FROM training_user_tags WHERE user_id = ?", (user_id,))
            for tag in normalized:
                conn.execute(
                    "INSERT INTO training_user_tags (user_id, tag) VALUES (?, ?)",
                    (user_id, tag),
                )
            self._upsert_tag_pool(conn, normalized)
            conn.commit()
        return UserTagSet(user_id=user_id, tags=frozenset(normalized))

    def list_all_user_tags(self) -> list[UserTagSet]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT user_id, tag FROM training_user_tags ORDER BY user_id, tag"
            ).fetchall()
        result: dict[str, set[str]] = {}
        for r in rows:
            result.setdefault(str(r["user_id"]), set()).add(str(r["tag"]))
        return [UserTagSet(user_id=uid, tags=frozenset(t)) for uid, t in result.items()]

    def list_tag_pool(self) -> list[str]:
        with connect(self._db_path) as conn:
            rows = conn.execute("SELECT tag FROM training_tag_pool ORDER BY tag").fetchall()
        return [str(r["tag"]) for r in rows]

    # --- infra ---

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with connect(self._db_path) as conn:
            conn.executescript(sql)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS training_tag_pool (
                    tag TEXT PRIMARY KEY,
                    first_seen_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO training_tag_pool (tag, first_seen_at)
                SELECT DISTINCT tag, ? FROM training_document_tags
                """,
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO training_tag_pool (tag, first_seen_at)
                SELECT DISTINCT tag, ? FROM training_user_tags
                """,
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()

    def _upsert_tag_pool(self, conn, tags: list[str]) -> None:
        if not tags:
            return
        now = datetime.now(timezone.utc).isoformat()
        for tag in tags:
            conn.execute(
                "INSERT OR IGNORE INTO training_tag_pool (tag, first_seen_at) VALUES (?, ?)",
                (tag, now),
            )


