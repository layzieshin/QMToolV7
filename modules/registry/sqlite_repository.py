from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .contracts import RegistryEntry, RegisterState, ReleaseEvidenceMode
from .repository import RegistryRepository


class SQLiteRegistryRepository(RegistryRepository):
    def __init__(self, db_path: Path, schema_path: Path) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert(self, entry: RegistryEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO document_registry (
                    document_id, active_version, release_note, release_evidence_mode,
                    register_state, is_findable, valid_from, valid_until,
                    last_update_event_id, last_update_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    active_version = excluded.active_version,
                    release_note = excluded.release_note,
                    release_evidence_mode = excluded.release_evidence_mode,
                    register_state = excluded.register_state,
                    is_findable = excluded.is_findable,
                    valid_from = excluded.valid_from,
                    valid_until = excluded.valid_until,
                    last_update_event_id = excluded.last_update_event_id,
                    last_update_at = excluded.last_update_at
                """,
                (
                    entry.document_id,
                    entry.active_version,
                    entry.release_note,
                    entry.release_evidence_mode.value,
                    entry.register_state.value,
                    1 if entry.is_findable else 0,
                    entry.valid_from.isoformat() if entry.valid_from else None,
                    entry.valid_until.isoformat() if entry.valid_until else None,
                    entry.last_update_event_id,
                    entry.last_update_at.isoformat(),
                ),
            )
            conn.commit()

    def get(self, document_id: str) -> RegistryEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM document_registry WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def list_entries(self) -> list[RegistryEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM document_registry ORDER BY document_id ASC",
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            conn.commit()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> RegistryEntry:
        return RegistryEntry(
            document_id=str(row["document_id"]),
            active_version=int(row["active_version"]) if row["active_version"] is not None else None,
            release_note=str(row["release_note"]) if row["release_note"] else None,
            release_evidence_mode=ReleaseEvidenceMode(str(row["release_evidence_mode"])),
            register_state=RegisterState(str(row["register_state"])),
            is_findable=bool(row["is_findable"]),
            valid_from=datetime.fromisoformat(row["valid_from"]) if row["valid_from"] else None,
            valid_until=datetime.fromisoformat(row["valid_until"]) if row["valid_until"] else None,
            last_update_event_id=str(row["last_update_event_id"]),
            last_update_at=datetime.fromisoformat(str(row["last_update_at"])),
        )
