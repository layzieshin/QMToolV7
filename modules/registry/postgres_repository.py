"""PostgreSQL RegistryRepository implementation for AP-029 PG01-B."""
from __future__ import annotations

from datetime import datetime, timezone

from .contracts import RegistryEntry, RegisterState, ReleaseEvidenceMode
from .postgres_connection import runtime_connection
from .repository import RegistryRepository


def _coerce_timestamp(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class PostgresRegistryRepository(RegistryRepository):
    """Registry persistence through the PG01 runtime privilege contract."""

    def __init__(self, dsn: str) -> None:
        self._dsn = str(dsn)

    def upsert(self, entry: RegistryEntry) -> None:
        with runtime_connection(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO registry.document_registry (
                    document_id, active_version, release_note, release_evidence_mode,
                    register_state, is_findable, valid_from, valid_until,
                    last_update_event_id, last_update_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id) DO UPDATE SET
                    active_version = EXCLUDED.active_version,
                    release_note = EXCLUDED.release_note,
                    release_evidence_mode = EXCLUDED.release_evidence_mode,
                    register_state = EXCLUDED.register_state,
                    is_findable = EXCLUDED.is_findable,
                    valid_from = EXCLUDED.valid_from,
                    valid_until = EXCLUDED.valid_until,
                    last_update_event_id = EXCLUDED.last_update_event_id,
                    last_update_at = EXCLUDED.last_update_at
                """,
                (
                    entry.document_id,
                    entry.active_version,
                    entry.release_note,
                    entry.release_evidence_mode.value,
                    entry.register_state.value,
                    entry.is_findable,
                    entry.valid_from,
                    entry.valid_until,
                    entry.last_update_event_id,
                    entry.last_update_at,
                ),
            )
            conn.commit()

    def get(self, document_id: str) -> RegistryEntry | None:
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                """
                SELECT document_id, active_version, release_note, release_evidence_mode,
                       register_state, is_findable, valid_from, valid_until,
                       last_update_event_id, last_update_at
                FROM registry.document_registry
                WHERE document_id = %s
                """,
                (document_id,),
            ).fetchone()
        return _row_to_entry(row) if row else None

    def list_entries(self) -> list[RegistryEntry]:
        with runtime_connection(self._dsn) as conn:
            rows = conn.execute(
                """
                SELECT document_id, active_version, release_note, release_evidence_mode,
                       register_state, is_findable, valid_from, valid_until,
                       last_update_event_id, last_update_at
                FROM registry.document_registry
                ORDER BY document_id ASC
                """,
            ).fetchall()
        return [_row_to_entry(row) for row in rows]


def _row_to_entry(row: dict[str, object]) -> RegistryEntry:
    return RegistryEntry(
        document_id=str(row["document_id"]),
        active_version=int(row["active_version"]) if row["active_version"] is not None else None,
        release_note=str(row["release_note"]) if row["release_note"] else None,
        release_evidence_mode=ReleaseEvidenceMode(str(row["release_evidence_mode"])),
        register_state=RegisterState(str(row["register_state"])),
        is_findable=bool(row["is_findable"]),
        valid_from=_coerce_timestamp(row["valid_from"]),
        valid_until=_coerce_timestamp(row["valid_until"]),
        last_update_event_id=str(row["last_update_event_id"]),
        last_update_at=_coerce_timestamp(row["last_update_at"]) or datetime.now(timezone.utc),
    )
