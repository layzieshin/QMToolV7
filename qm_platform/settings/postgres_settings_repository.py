"""PostgreSQL repository for platform settings behind SettingsService.

Opens one connection per call and closes it before returning. Does not create
schema, keep a connection, or fall back to SQLite.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg

from qm_platform.persistence.postgres_schema import PostgresSchemaError, _validate_runtime_identity


class SettingsPersistenceUnavailable(RuntimeError):
    """PostgreSQL platform settings cannot be used. SQLite is not a fallback."""


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


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _unavailable(exc: psycopg.Error) -> SettingsPersistenceUnavailable:
    if getattr(exc, "sqlstate", None) == "42P01":
        return SettingsPersistenceUnavailable(
            "platform settings schema is not applied; runtime DDL is forbidden"
        )
    return SettingsPersistenceUnavailable("platform settings PostgreSQL is unavailable")


class PostgresSettingsRepository:
    """module_global settings only: scope_kind=MODULE, scope_id=module_id."""

    INTEGRITY_RESIDUAL_SHA256 = "residual_archive_sha256"
    INTEGRITY_CUTOVER_STATUS = "cutover_status"

    def __init__(self, dsn: str) -> None:
        if not str(dsn).strip():
            raise SettingsPersistenceUnavailable("platform settings PostgreSQL DSN is empty")
        self._dsn = str(dsn)

    @contextmanager
    def _open(self) -> Iterator[psycopg.Connection]:
        try:
            conn = psycopg.connect(self._dsn, connect_timeout=5)
        except psycopg.Error as exc:
            raise _unavailable(exc) from exc
        try:
            try:
                _validate_runtime_identity(conn)
            except PostgresSchemaError as exc:
                raise SettingsPersistenceUnavailable(
                    "platform settings PostgreSQL runtime identity rejected"
                ) from exc
            yield conn
            conn.commit()
        except SettingsPersistenceUnavailable:
            conn.rollback()
            raise
        except psycopg.Error as exc:
            conn.rollback()
            raise _unavailable(exc) from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def assert_schema_ready(self) -> None:
        """Read-only proof that the operator-applied settings tables exist."""
        with self._open() as conn:
            conn.execute("SELECT 1 FROM platform.platform_settings LIMIT 0")
            conn.execute("SELECT 1 FROM platform.platform_settings_integrity LIMIT 0")
            conn.execute("SELECT 1 FROM platform.platform_setting_revisions LIMIT 0")

    def load_module_technical(self, module_id: str) -> dict[str, Any]:
        with self._open() as conn:
            rows = conn.execute(
                """
                SELECT setting_key, value_json
                FROM platform.platform_settings
                WHERE scope_kind = 'MODULE' AND scope_id = %s AND module_id = %s
                ORDER BY setting_key
                """,
                (module_id, module_id),
            ).fetchall()
        out: dict[str, Any] = {}
        for key, raw in rows:
            out[str(key)] = json.loads(str(raw))
        return out

    def list_all_technical_keys(self) -> set[tuple[str, str]]:
        with self._open() as conn:
            rows = conn.execute(
                """
                SELECT module_id, setting_key
                FROM platform.platform_settings
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
        now = _utc_now()
        with self._open() as conn:
            existing = {
                str(row[0]): (str(row[1]), int(row[2]))
                for row in conn.execute(
                    """
                    SELECT setting_key, value_json, revision
                    FROM platform.platform_settings
                    WHERE scope_kind = 'MODULE' AND scope_id = %s AND module_id = %s
                    FOR UPDATE
                    """,
                    (module_id, module_id),
                ).fetchall()
            }
            incoming_keys = set(values)
            for key in sorted(set(existing) - incoming_keys):
                conn.execute(
                    """
                    DELETE FROM platform.platform_settings
                    WHERE scope_kind = 'MODULE' AND scope_id = %s AND module_id = %s
                      AND setting_key = %s
                    """,
                    (module_id, module_id, key),
                )
            for key, value in values.items():
                payload = _json(value)
                old = existing.get(key)
                if old is not None and old[0] == payload:
                    continue
                revision = 1 if old is None else old[1] + 1
                old_json = None if old is None else old[0]
                conn.execute(
                    """
                    INSERT INTO platform.platform_settings (
                        scope_kind, scope_id, module_id, setting_key,
                        value_type, value_json, schema_version, revision,
                        updated_at, updated_by_user_id
                    ) VALUES ('MODULE', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (scope_kind, scope_id, module_id, setting_key) DO UPDATE SET
                        value_type = EXCLUDED.value_type,
                        value_json = EXCLUDED.value_json,
                        schema_version = EXCLUDED.schema_version,
                        revision = EXCLUDED.revision,
                        updated_at = EXCLUDED.updated_at,
                        updated_by_user_id = EXCLUDED.updated_by_user_id
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
                    INSERT INTO platform.platform_setting_revisions (
                        revision_id, scope_kind, scope_id, module_id, setting_key,
                        revision_no, old_value_json, new_value_json,
                        changed_at, changed_by_user_id, reason
                    ) VALUES (%s, 'MODULE', %s, %s, %s, %s, %s, %s, %s, %s, %s)
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

    def get_integrity(self, key: str) -> str | None:
        with self._open() as conn:
            row = conn.execute(
                """
                SELECT integrity_value
                FROM platform.platform_settings_integrity
                WHERE integrity_key = %s
                """,
                (key,),
            ).fetchone()
        return None if row is None else str(row[0])

    def set_integrity(self, key: str, value: str, *, actor: str) -> None:
        now = _utc_now()
        with self._open() as conn:
            conn.execute(
                """
                INSERT INTO platform.platform_settings_integrity (
                    integrity_key, integrity_value, updated_at, updated_by
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (integrity_key) DO UPDATE SET
                    integrity_value = EXCLUDED.integrity_value,
                    updated_at = EXCLUDED.updated_at,
                    updated_by = EXCLUDED.updated_by
                """,
                (key, value, now, actor),
            )

    def clear_integrity(self, key: str) -> None:
        with self._open() as conn:
            conn.execute(
                """
                DELETE FROM platform.platform_settings_integrity
                WHERE integrity_key = %s
                """,
                (key,),
            )

    def import_preserved_snapshot(
        self,
        *,
        settings_rows: list[tuple[Any, ...]],
        revision_rows: list[tuple[Any, ...]],
        integrity_rows: list[tuple[Any, ...]],
    ) -> None:
        """Insert a read-only legacy snapshot. Refuses a non-empty target and non-MODULE rows."""
        for row in settings_rows:
            scope_kind, scope_id, module_id = str(row[0]), str(row[1]), str(row[2])
            if scope_kind != "MODULE" or scope_id != module_id:
                raise SettingsPersistenceUnavailable(
                    "legacy settings import rejected a non-module scope"
                )
        for row in revision_rows:
            scope_kind, scope_id, module_id = str(row[1]), str(row[2]), str(row[3])
            if scope_kind != "MODULE" or scope_id != module_id:
                raise SettingsPersistenceUnavailable(
                    "legacy settings import rejected a non-module revision scope"
                )
        with self._open() as conn:
            counts = [
                int(conn.execute(sql).fetchone()[0])
                for sql in (
                    "SELECT COUNT(*) FROM platform.platform_settings",
                    "SELECT COUNT(*) FROM platform.platform_setting_revisions",
                    "SELECT COUNT(*) FROM platform.platform_settings_integrity",
                )
            ]
            if any(count > 0 for count in counts):
                raise SettingsPersistenceUnavailable(
                    "legacy settings import refused because PostgreSQL settings already exist"
                )
            for row in settings_rows:
                conn.execute(
                    """
                    INSERT INTO platform.platform_settings (
                        scope_kind, scope_id, module_id, setting_key,
                        value_type, value_json, schema_version, revision,
                        updated_at, updated_by_user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    tuple(row),
                )
            for row in revision_rows:
                conn.execute(
                    """
                    INSERT INTO platform.platform_setting_revisions (
                        revision_id, scope_kind, scope_id, module_id, setting_key,
                        revision_no, old_value_json, new_value_json,
                        changed_at, changed_by_user_id, reason
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    tuple(row),
                )
            for row in integrity_rows:
                conn.execute(
                    """
                    INSERT INTO platform.platform_settings_integrity (
                        integrity_key, integrity_value, updated_at, updated_by
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    tuple(row),
                )
