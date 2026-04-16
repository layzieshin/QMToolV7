"""Repository for document tags and user tags."""
from __future__ import annotations

from pathlib import Path

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
        with connect(self._db_path) as conn:
            conn.execute("DELETE FROM training_document_tags WHERE document_id = ?", (document_id,))
            for tag in sorted(set(tags)):
                conn.execute(
                    "INSERT INTO training_document_tags (document_id, tag) VALUES (?, ?)",
                    (document_id, tag),
                )
            conn.commit()
        return DocumentTagSet(document_id=document_id, tags=frozenset(tags))

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
        with connect(self._db_path) as conn:
            conn.execute("DELETE FROM training_user_tags WHERE user_id = ?", (user_id,))
            for tag in sorted(set(tags)):
                conn.execute(
                    "INSERT INTO training_user_tags (user_id, tag) VALUES (?, ?)",
                    (user_id, tag),
                )
            conn.commit()
        return UserTagSet(user_id=user_id, tags=frozenset(tags))

    def list_all_user_tags(self) -> list[UserTagSet]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT user_id, tag FROM training_user_tags ORDER BY user_id, tag"
            ).fetchall()
        result: dict[str, set[str]] = {}
        for r in rows:
            result.setdefault(str(r["user_id"]), set()).add(str(r["tag"]))
        return [UserTagSet(user_id=uid, tags=frozenset(t)) for uid, t in result.items()]

    # --- infra ---

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with connect(self._db_path) as conn:
            conn.executescript(sql)
            conn.commit()


