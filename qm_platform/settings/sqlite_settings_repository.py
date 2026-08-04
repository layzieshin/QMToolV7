"""SQLite repository for platform_settings (storage-agnostic SettingsService backend)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


@dataclass
class SqliteSettingsRepository:
    """module_global settings only: scope_kind=MODULE, scope_id=module_id."""

    db_path: Path

    def load_module_technical(self, module_id: str) -> dict[str, Any]:
        if not self.db_path.is_file():
            return {}
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT setting_key, value_json
                FROM platform_settings
                WHERE scope_kind = 'MODULE' AND scope_id = ? AND module_id = ?
                ORDER BY setting_key
                """,
                (module_id, module_id),
            ).fetchall()
        out: dict[str, Any] = {}
        for key, raw in rows:
            out[str(key)] = json.loads(str(raw))
        return out

    def list_all_technical_keys(self) -> set[tuple[str, str]]:
        if not self.db_path.is_file():
            return set()
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT module_id, setting_key
                FROM platform_settings
                WHERE scope_kind = 'MODULE'
                """
            ).fetchall()
        return {(str(module_id), str(key)) for module_id, key in rows}

    def replace_module_technical(
        self,
        module_id: str,
        values: dict[str, Any],
        *,
        actor: str,
        schema_version: int,
        reason: str | None = None,
    ) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        with closing(sqlite3.connect(self.db_path)) as conn:
            existing = {
                str(row[0]): (str(row[1]), int(row[2]))
                for row in conn.execute(
                    """
                    SELECT setting_key, value_json, revision
                    FROM platform_settings
                    WHERE scope_kind = 'MODULE' AND scope_id = ? AND module_id = ?
                    """,
                    (module_id, module_id),
                ).fetchall()
            }
            incoming_keys = set(values)
            for key in sorted(set(existing) - incoming_keys):
                conn.execute(
                    """
                    DELETE FROM platform_settings
                    WHERE scope_kind = 'MODULE' AND scope_id = ? AND module_id = ?
                      AND setting_key = ?
                    """,
                    (module_id, module_id, key),
                )
            for key, value in values.items():
                payload = json.dumps(value, ensure_ascii=True, sort_keys=True)
                old = existing.get(key)
                if old is not None and old[0] == payload:
                    continue
                revision = 1 if old is None else old[1] + 1
                old_json = None if old is None else old[0]
                conn.execute(
                    """
                    INSERT INTO platform_settings (
                        scope_kind, scope_id, module_id, setting_key,
                        value_type, value_json, schema_version, revision,
                        updated_at, updated_by_user_id
                    ) VALUES ('MODULE', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(scope_kind, scope_id, module_id, setting_key) DO UPDATE SET
                        value_type = excluded.value_type,
                        value_json = excluded.value_json,
                        schema_version = excluded.schema_version,
                        revision = excluded.revision,
                        updated_at = excluded.updated_at,
                        updated_by_user_id = excluded.updated_by_user_id
                    """,
                    (
                        module_id,
                        module_id,
                        key,
                        _value_type(value),
                        payload,
                        int(schema_version),
                        revision,
                        now,
                        actor,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO platform_setting_revisions (
                        revision_id, scope_kind, scope_id, module_id, setting_key,
                        revision_no, old_value_json, new_value_json,
                        changed_at, changed_by_user_id, reason
                    ) VALUES (?, 'MODULE', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        module_id,
                        module_id,
                        key,
                        revision,
                        old_json,
                        payload,
                        now,
                        actor,
                        reason,
                    ),
                )
            conn.commit()

    INTEGRITY_RESIDUAL_SHA256 = "residual_archive_sha256"
    INTEGRITY_CUTOVER_STATUS = "cutover_status"

    def get_integrity(self, key: str) -> str | None:
        if not self.db_path.is_file():
            return None
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT integrity_value
                FROM platform_settings_integrity
                WHERE integrity_key = ?
                """,
                (key,),
            ).fetchone()
        return None if row is None else str(row[0])

    def set_integrity(self, key: str, value: str, *, actor: str) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO platform_settings_integrity (
                    integrity_key, integrity_value, updated_at, updated_by
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(integrity_key) DO UPDATE SET
                    integrity_value = excluded.integrity_value,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (key, value, now, actor),
            )
            conn.commit()

    def clear_integrity(self, key: str) -> None:
        if not self.db_path.is_file():
            return
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "DELETE FROM platform_settings_integrity WHERE integrity_key = ?",
                (key,),
            )
            conn.commit()
