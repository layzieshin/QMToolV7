"""PostgreSQL schema applicator for Usermanagement only (AP-028 Milestone 3).

Parallel to AP-027 SQLite Database Evolution — deliberately separate.
Not part of the public ``modules.usermanagement.api`` surface.

Deployment order:
1. Administrative ``provision_roles.sql`` (NOLOGIN roles + empty schema)
2. ``migrate_usermanagement_schema`` as a LOGIN member of ``qmtool_migrator``
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.pq import ExecStatus

SCHEMA_NAME = "usermanagement"
MIGRATIONS_TABLE = "_qm_schema_migrations"
MIGRATOR_ROLE = "qmtool_migrator"
RUNTIME_ROLE = "qmtool_runtime"
# Stable advisory-lock key dedicated to UM schema migration.
ADVISORY_LOCK_KEY = 0x5154_4D5F_554D_4D47  # "QTM_UMMG"
POSTGRES_ROOT = Path(__file__).resolve().parent / "postgres"
MIGRATIONS_DIR = POSTGRES_ROOT / "migrations"
PROVISION_ROLES_PATH = POSTGRES_ROOT / "provision_roles.sql"

_MIGRATION_NAME_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

EXPECTED_TABLES = frozenset({"users", "sessions", MIGRATIONS_TABLE})
EXPECTED_USERS_COLUMNS = frozenset(
    {
        "user_id",
        "username",
        "password_hash",
        "role",
        "first_name",
        "last_name",
        "display_name",
        "email",
        "department",
        "scope",
        "organization_unit",
        "is_active",
        "deactivated_at",
        "is_qmb",
        "must_change_password",
        "created_at",
        "updated_at",
    }
)
EXPECTED_SESSIONS_COLUMNS = frozenset(
    {
        "session_id",
        "token_hash",
        "user_id",
        "created_at",
        "last_seen_at",
        "expires_at",
        "revoked_at",
        "client_type",
        "authentication_level",
    }
)
EXPECTED_HISTORY_COLUMNS = frozenset(
    {"version", "name", "checksum", "schema_fingerprint", "applied_at"}
)
EXPECTED_CHECK_CONSTRAINTS = frozenset(
    {
        "users_active_requires_null_deactivated_at",
        "sessions_expires_after_created",
        "sessions_last_seen_after_created",
        "sessions_revoked_after_created",
    }
)


class PostgresSchemaError(RuntimeError):
    """Raised when Usermanagement PostgreSQL schema migration cannot proceed safely."""


@dataclass(frozen=True)
class PostgresMigrationStep:
    version: int
    name: str
    sql_path: Path

    @property
    def checksum(self) -> str:
        # Normalize newlines so Windows/Linux checkouts share the same fingerprint.
        normalized = (
            self.sql_path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
        )
        return hashlib.sha256(normalized).hexdigest()


@dataclass(frozen=True)
class AppliedMigration:
    version: int
    name: str
    checksum: str
    schema_fingerprint: str


def discover_migrations(migrations_dir: Path | None = None) -> tuple[PostgresMigrationStep, ...]:
    root = migrations_dir if migrations_dir is not None else MIGRATIONS_DIR
    if not root.is_dir():
        raise PostgresSchemaError(f"migrations directory missing: {root}")

    steps: list[PostgresMigrationStep] = []
    for path in sorted(root.glob("*.sql")):
        match = _MIGRATION_NAME_RE.match(path.name)
        if match is None:
            raise PostgresSchemaError(f"invalid migration filename: {path.name}")
        steps.append(
            PostgresMigrationStep(
                version=int(match.group(1)),
                name=match.group(2),
                sql_path=path,
            )
        )

    if not steps:
        raise PostgresSchemaError(f"no migrations found in {root}")

    versions = [step.version for step in steps]
    names = [step.name for step in steps]
    if len(versions) != len(set(versions)):
        raise PostgresSchemaError("migration versions must be unique")
    if len(names) != len(set(names)):
        raise PostgresSchemaError("migration names must be unique")
    expected = list(range(1, len(versions) + 1))
    if versions != expected:
        raise PostgresSchemaError(
            f"migration versions must be contiguous from 1; got {versions}"
        )
    return tuple(steps)


def _execute_script(conn: psycopg.Connection, script: str) -> None:
    """Execute a SQL file as a whole via libpq PQexec (no client-side statement split)."""
    result = conn.pgconn.exec_(script.encode("utf-8"))
    status = result.status
    if status not in (ExecStatus.COMMAND_OK, ExecStatus.TUPLES_OK, ExecStatus.EMPTY_QUERY):
        message = result.error_message
        text = message.decode("utf-8", errors="replace") if message else "unknown SQL error"
        raise PostgresSchemaError(f"migration script failed: {text}")


def provision_usermanagement_roles(admin_dsn: str) -> None:
    """Apply ``provision_roles.sql`` as an administrative connection."""
    script = PROVISION_ROLES_PATH.read_text(encoding="utf-8")
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        _execute_script(conn, script)


def _schema_exists(conn: psycopg.Connection) -> bool:
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)",
        (SCHEMA_NAME,),
    ).fetchone()
    return bool(row and row[0])


def _table_names(conn: psycopg.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            """,
            (SCHEMA_NAME,),
        ).fetchall()
    }


def _history_table_exists(conn: psycopg.Connection) -> bool:
    return MIGRATIONS_TABLE in _table_names(conn)


def _fetch_applied(conn: psycopg.Connection) -> tuple[AppliedMigration, ...]:
    if not _history_table_exists(conn):
        return ()
    rows = conn.execute(
        f"""
        SELECT version, name, checksum, schema_fingerprint
        FROM {SCHEMA_NAME}.{MIGRATIONS_TABLE}
        ORDER BY version
        """
    ).fetchall()
    return tuple(
        AppliedMigration(
            version=int(version),
            name=str(name),
            checksum=str(checksum),
            schema_fingerprint=str(fingerprint),
        )
        for version, name, checksum, fingerprint in rows
    )


def _validate_history_prefix(
    applied: tuple[AppliedMigration, ...],
    steps: tuple[PostgresMigrationStep, ...],
) -> None:
    if applied:
        versions = [row.version for row in applied]
        if versions != list(range(1, len(versions) + 1)):
            raise PostgresSchemaError(
                f"applied migration versions must be a contiguous prefix from 1; got {versions}"
            )
    if len(applied) > len(steps):
        raise PostgresSchemaError(
            f"database schema version {applied[-1].version} is newer than "
            f"registered target {steps[-1].version}"
        )
    for index, row in enumerate(applied):
        step = steps[index]
        if row.version != step.version:
            raise PostgresSchemaError(
                f"history version mismatch at position {index + 1}: "
                f"db={row.version} registered={step.version}"
            )
        if row.name != step.name:
            raise PostgresSchemaError(
                f"history name mismatch for version {row.version}: "
                f"db={row.name!r} registered={step.name!r}"
            )
        if row.checksum != step.checksum:
            raise PostgresSchemaError(
                f"checksum mismatch for applied migration {row.version}: "
                "migrations are immutable"
            )


def _require_bootstrap_or_history(conn: psycopg.Connection, applied: tuple[AppliedMigration, ...]) -> None:
    if applied:
        return
    if not _schema_exists(conn):
        raise PostgresSchemaError(
            "schema usermanagement is missing; run provision_roles.sql before migrate"
        )
    owner = conn.execute(
        """
        SELECT r.rolname
        FROM pg_namespace n
        JOIN pg_roles r ON r.oid = n.nspowner
        WHERE n.nspname = %s
        """,
        (SCHEMA_NAME,),
    ).fetchone()
    if owner is None or owner[0] != MIGRATOR_ROLE:
        raise PostgresSchemaError(
            "bootstrap schema usermanagement must be owned by qmtool_migrator"
        )
    tables = _table_names(conn)
    if tables:
        raise PostgresSchemaError(
            "populated unversioned schema usermanagement refused; "
            f"tables present: {sorted(tables)}"
        )


def _compute_schema_fingerprint(conn: psycopg.Connection) -> str:
    tables = sorted(_table_names(conn))
    columns = conn.execute(
        """
        SELECT table_name, column_name, data_type, is_nullable,
               column_default, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = %s
        ORDER BY table_name, ordinal_position, column_name
        """,
        (SCHEMA_NAME,),
    ).fetchall()
    constraints = conn.execute(
        """
        SELECT tc.table_name, tc.constraint_type, tc.constraint_name,
               cc.check_clause, rc.delete_rule, rc.update_rule
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.check_constraints cc
          ON cc.constraint_schema = tc.constraint_schema
         AND cc.constraint_name = tc.constraint_name
        LEFT JOIN information_schema.referential_constraints rc
          ON rc.constraint_schema = tc.constraint_schema
         AND rc.constraint_name = tc.constraint_name
        WHERE tc.table_schema = %s
        ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name
        """,
        (SCHEMA_NAME,),
    ).fetchall()
    indexes = conn.execute(
        """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = %s
        ORDER BY tablename, indexname
        """,
        (SCHEMA_NAME,),
    ).fetchall()
    payload = {
        "tables": tables,
        "columns": [
            {
                "table": table,
                "column": column,
                "type": data_type,
                "nullable": nullable,
                "default": default,
                "position": position,
            }
            for table, column, data_type, nullable, default, position in columns
        ],
        "constraints": [
            {
                "table": table,
                "type": ctype,
                "name": name,
                "check": check_clause,
                "delete_rule": delete_rule,
                "update_rule": update_rule,
            }
            for table, ctype, name, check_clause, delete_rule, update_rule in constraints
        ],
        "indexes": [
            {"table": table, "name": name, "def": indexdef}
            for table, name, indexdef in indexes
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_schema_contracts(conn: psycopg.Connection) -> None:
    tables = _table_names(conn)
    missing_tables = EXPECTED_TABLES - tables
    if missing_tables:
        raise PostgresSchemaError(f"missing tables after migrate: {sorted(missing_tables)}")

    def columns_for(table: str) -> set[str]:
        return {
            str(row[0])
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                """,
                (SCHEMA_NAME, table),
            ).fetchall()
        }

    missing_users = EXPECTED_USERS_COLUMNS - columns_for("users")
    if missing_users:
        raise PostgresSchemaError(f"users missing columns: {sorted(missing_users)}")
    missing_sessions = EXPECTED_SESSIONS_COLUMNS - columns_for("sessions")
    if missing_sessions:
        raise PostgresSchemaError(f"sessions missing columns: {sorted(missing_sessions)}")
    missing_history = EXPECTED_HISTORY_COLUMNS - columns_for(MIGRATIONS_TABLE)
    if missing_history:
        raise PostgresSchemaError(
            f"{MIGRATIONS_TABLE} missing columns: {sorted(missing_history)}"
        )

    checks = {
        str(row[0])
        for row in conn.execute(
            """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_schema = %s AND constraint_type = 'CHECK'
            """,
            (SCHEMA_NAME,),
        ).fetchall()
    }
    missing_checks = EXPECTED_CHECK_CONSTRAINTS - checks
    if missing_checks:
        raise PostgresSchemaError(f"missing check constraints: {sorted(missing_checks)}")

    fk = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc
          ON rc.constraint_schema = tc.constraint_schema
         AND rc.constraint_name = tc.constraint_name
        WHERE tc.table_schema = %s
          AND tc.table_name = 'sessions'
          AND rc.delete_rule = 'RESTRICT'
        """,
        (SCHEMA_NAME,),
    ).fetchone()
    if fk is None or int(fk[0]) < 1:
        raise PostgresSchemaError("sessions.user_id FK ON DELETE RESTRICT missing")

    for table in ("users", "sessions", MIGRATIONS_TABLE):
        owner = conn.execute(
            """
            SELECT tableowner
            FROM pg_tables
            WHERE schemaname = %s AND tablename = %s
            """,
            (SCHEMA_NAME, table),
        ).fetchone()
        if owner is None or owner[0] != MIGRATOR_ROLE:
            raise PostgresSchemaError(
                f"table {table} owner is {None if owner is None else owner[0]!r}, "
                f"expected {MIGRATOR_ROLE}"
            )


def _activate_migrator_role(conn: psycopg.Connection) -> None:
    conn.execute(f"SET ROLE {MIGRATOR_ROLE}")
    current = conn.execute("SELECT current_user").fetchone()
    if current is None or current[0] != MIGRATOR_ROLE:
        raise PostgresSchemaError(
            f"SET ROLE {MIGRATOR_ROLE} failed; effective user is "
            f"{None if current is None else current[0]!r}"
        )


def migrate_usermanagement_schema(
    dsn: str,
    *,
    migrations_dir: Path | None = None,
) -> int:
    """Apply pending Usermanagement PostgreSQL migrations. Returns resulting schema version."""
    steps = discover_migrations(migrations_dir)
    target = steps[-1].version

    with psycopg.connect(dsn, autocommit=True) as conn:
        locked = conn.execute(
            "SELECT pg_try_advisory_lock(%s)",
            (ADVISORY_LOCK_KEY,),
        ).fetchone()
        if locked is None or not locked[0]:
            raise PostgresSchemaError(
                "usermanagement schema migration already in progress "
                "(advisory lock held)"
            )
        try:
            _activate_migrator_role(conn)
            applied = _fetch_applied(conn)
            _validate_history_prefix(applied, steps)
            _require_bootstrap_or_history(conn, applied)

            if applied:
                current_fp = _compute_schema_fingerprint(conn)
                if current_fp != applied[-1].schema_fingerprint:
                    raise PostgresSchemaError(
                        "schema fingerprint drift detected against last applied migration"
                    )

            pending = steps[len(applied) :]
            for step in pending:
                script = step.sql_path.read_text(encoding="utf-8")
                with conn.transaction():
                    _execute_script(conn, script)
                    _validate_schema_contracts(conn)
                    fingerprint = _compute_schema_fingerprint(conn)
                    conn.execute(
                        f"""
                        INSERT INTO {SCHEMA_NAME}.{MIGRATIONS_TABLE}
                            (version, name, checksum, schema_fingerprint)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (step.version, step.name, step.checksum, fingerprint),
                    )

            applied_after = _fetch_applied(conn)
            _validate_history_prefix(applied_after, steps)
            if not applied_after or applied_after[-1].version != target:
                raise PostgresSchemaError(
                    f"schema validation left unexpected version set: "
                    f"{[row.version for row in applied_after]}"
                )
            final_fp = _compute_schema_fingerprint(conn)
            if final_fp != applied_after[-1].schema_fingerprint:
                raise PostgresSchemaError(
                    "schema fingerprint mismatch after migration commit"
                )
            _validate_schema_contracts(conn)
            return target
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
