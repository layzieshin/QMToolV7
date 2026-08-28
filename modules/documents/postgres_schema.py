"""PostgreSQL schema applicator for Documents only (AP-029 PG01-A).

Parallel to AP-028 Usermanagement PostgreSQL and AP-029 PG00 platform — deliberately separate.
Not part of the public module API surface.

Deployment order:
1. Administrative ``modules/usermanagement/postgres/provision_roles.sql`` (shared roles)
2. Administrative ``provision_documents_schema.sql`` (empty documents schema)
3. ``migrate_documents_schema`` as a LOGIN member of ``qmtool_migrator``
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.pq import ExecStatus

SCHEMA_NAME = "documents"
MIGRATIONS_TABLE = "_qm_schema_migrations"
MIGRATOR_ROLE = "qmtool_migrator"
RUNTIME_ROLE = "qmtool_runtime"
ADVISORY_LOCK_KEY = 0x5154_4D5F_444F_4353  # "QTM_DOCS"
POSTGRES_ROOT = Path(__file__).resolve().parent / "postgres"
MIGRATIONS_DIR = POSTGRES_ROOT / "migrations"
PROVISION_DOCUMENTS_SCHEMA_PATH = POSTGRES_ROOT / "provision_documents_schema.sql"

_MIGRATION_NAME_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

EXPECTED_TABLES = frozenset({'_qm_schema_migrations', 'document_artifacts', 'document_headers', 'document_pdf_read_page_progress', 'document_pdf_read_sessions', 'document_read_receipts', 'document_versions', 'document_workflow_comments'})
EXPECTED_TABLES_FULL = frozenset({'_qm_schema_migrations', 'document_artifacts', 'document_headers', 'document_pdf_read_page_progress', 'document_pdf_read_sessions', 'document_read_receipts', 'document_type_definitions', 'document_versions', 'document_workflow_comments', 'workflow_profile_definitions', 'workflow_profile_imports', 'workflow_profile_transitions', 'workflow_profile_versions'})
EXPECTED_HISTORY_COLUMNS = frozenset(
    {"version", "name", "checksum", "schema_fingerprint", "applied_at"}
)
EXPECTED_DOCUMENT_HEADERS_COLUMNS = frozenset(
    {
'control_class', 'created_at', 'department', 'distribution_departments_json', 'distribution_roles_json', 'distribution_sites_json', 'doc_type', 'document_id', 'register_binding', 'regulatory_scope', 'site', 'updated_at', 'workflow_profile_id'
    })

EXPECTED_DOCUMENT_VERSIONS_COLUMNS = frozenset(
    {
'approval_completed_at', 'approval_completed_by', 'approved_by_json', 'approvers_json', 'archived_at', 'archived_by', 'control_class', 'created_at', 'created_by', 'custom_fields_json', 'description', 'doc_type', 'document_id', 'edit_signature_done', 'editors_json', 'extension_count', 'last_actor_user_id', 'last_event_at', 'last_event_id', 'last_extended_at', 'last_extended_by', 'last_extension_reason', 'last_extension_review_outcome', 'next_review_at', 'owner_user_id', 'released_at', 'review_completed_at', 'review_completed_by', 'reviewed_by_json', 'reviewers_json', 'status', 'superseded_by_version', 'title', 'updated_at', 'valid_from', 'valid_until', 'version', 'workflow_active', 'workflow_profile_id', 'workflow_profile_json'
    })

EXPECTED_WORKFLOW_PROFILE_DEFINITIONS_COLUMNS = frozenset(
    {
'active_version', 'control_class', 'created_at', 'created_by', 'is_active', 'label', 'profile_code', 'updated_at', 'updated_by'
    })
EXPECTED_CHECK_CONSTRAINTS = frozenset({'workflow_profile_imports_classification_known', 'workflow_profile_transitions_deadline_positive', 'workflow_profile_transitions_decision_policy_known', 'workflow_profile_transitions_from_status_known', 'workflow_profile_transitions_required_role_known', 'workflow_profile_transitions_revoke_if_changed_bool', 'workflow_profile_transitions_to_status_known', 'workflow_profile_transitions_transition_no_positive', 'workflow_profile_versions_source_kind_known', 'workflow_profile_versions_version_no_positive'})


class PostgresSchemaError(RuntimeError):
    """Raised when Documents PostgreSQL schema migration cannot proceed safely."""


@dataclass(frozen=True)
class PostgresMigrationStep:
    version: int
    name: str
    sql_path: Path

    @property
    def checksum(self) -> str:
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
    result = conn.pgconn.exec_(script.encode("utf-8"))
    status = result.status
    if status not in (ExecStatus.COMMAND_OK, ExecStatus.TUPLES_OK, ExecStatus.EMPTY_QUERY):
        message = result.error_message
        text = message.decode("utf-8", errors="replace") if message else "unknown SQL error"
        raise PostgresSchemaError(f"migration script failed: {text}")


def provision_documents_schema(admin_dsn: str) -> None:
    script = PROVISION_DOCUMENTS_SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        _execute_script(conn, script)


def _validate_runtime_identity(conn: psycopg.Connection) -> None:
    row = conn.execute(
        """
        SELECT current_user,
               session_user,
               pg_has_role(current_user, %s, 'MEMBER') AS runtime_member,
               pg_has_role(current_user, %s, 'SET') AS runtime_set,
               pg_has_role(current_user, %s, 'MEMBER') AS migrator_member,
               pg_has_role(current_user, %s, 'SET') AS migrator_set
        """,
        (RUNTIME_ROLE, RUNTIME_ROLE, MIGRATOR_ROLE, MIGRATOR_ROLE),
    ).fetchone()
    if row is None:
        raise PostgresSchemaError("could not validate PostgreSQL runtime identity")
    (
        current_user,
        session_user,
        runtime_member,
        runtime_set,
        migrator_member,
        migrator_set,
    ) = row
    if (
        current_user != session_user
        or not bool(runtime_member)
        or not bool(runtime_set)
        or bool(migrator_member)
        or bool(migrator_set)
    ):
        raise PostgresSchemaError(
            "documents readiness requires a LOGIN member of qmtool_runtime "
            "without qmtool_migrator membership"
        )


@contextmanager
def _runtime_connection_for_schema(dsn: str) -> Iterator[psycopg.Connection]:
    if not str(dsn).strip():
        raise ValueError("PostgreSQL DSN is required")
    with psycopg.connect(str(dsn)) as conn:
        _validate_runtime_identity(conn)
        yield conn


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


def _schema_relations(conn: psycopg.Connection) -> list[tuple[object, ...]]:
    return conn.execute(
        """
        SELECT rel.relname, rel.relkind
        FROM pg_class rel
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        WHERE ns.nspname = %s
          AND rel.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
        ORDER BY rel.relname, rel.relkind
        """,
        (SCHEMA_NAME,),
    ).fetchall()


def _schema_functions(conn: psycopg.Connection) -> list[tuple[object, ...]]:
    return conn.execute(
        """
        SELECT proc.proname, pg_get_function_identity_arguments(proc.oid)
        FROM pg_proc proc
        JOIN pg_namespace ns ON ns.oid = proc.pronamespace
        WHERE ns.nspname = %s
        ORDER BY proc.proname, pg_get_function_identity_arguments(proc.oid)
        """,
        (SCHEMA_NAME,),
    ).fetchall()


def _schema_types(conn: psycopg.Connection) -> list[tuple[object, ...]]:
    return conn.execute(
        """
        SELECT typ.typname, typ.typtype
        FROM pg_type typ
        JOIN pg_namespace ns ON ns.oid = typ.typnamespace
        WHERE ns.nspname = %s
          AND typ.typtype IN ('c', 'd', 'e', 'r', 'm')
        ORDER BY typ.typname, typ.typtype
        """,
        (SCHEMA_NAME,),
    ).fetchall()


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
    applied: list[AppliedMigration] = []
    for row in rows:
        version, name, checksum, fingerprint = row
        applied.append(
            AppliedMigration(
                version=int(version),
                name=str(name),
                checksum=str(checksum),
                schema_fingerprint=str(fingerprint),
            )
        )
    return tuple(applied)


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
        if row.version != step.version or row.name != step.name or row.checksum != step.checksum:
            raise PostgresSchemaError(
                f"history mismatch for migration {row.version}; migrations are immutable"
            )


def _require_bootstrap_or_history(conn: psycopg.Connection, applied: tuple[AppliedMigration, ...]) -> None:
    if applied:
        return
    if not _schema_exists(conn):
        raise PostgresSchemaError("schema documents is missing; run provision_documents_schema.sql before migrate")
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
        raise PostgresSchemaError("bootstrap schema documents must be owned by qmtool_migrator")
    relations = _schema_relations(conn)
    functions = _schema_functions(conn)
    types = _schema_types(conn)
    if relations or functions or types:
        raise PostgresSchemaError(
            "populated unversioned schema documents refused; "
            f"relations={[(row[0], row[1]) for row in relations]}, "
            f"functions={[(row[0], row[1]) for row in functions]}, "
            f"types={[(row[0], row[1]) for row in types]}"
        )


def _compute_schema_fingerprint(conn: psycopg.Connection) -> str:
    columns = conn.execute(
        """
        SELECT table_name, column_name, data_type, is_nullable,
               column_default, ordinal_position, udt_schema, udt_name,
               is_identity, identity_generation, is_generated,
               generation_expression
        FROM information_schema.columns
        WHERE table_schema = %s
        ORDER BY table_name, ordinal_position, column_name
        """,
        (SCHEMA_NAME,),
    ).fetchall()
    constraints = conn.execute(
        """
        SELECT COALESCE(rel.relname, ''), COALESCE(typ.typname, ''), con.conname,
               con.contype, con.condeferrable, con.condeferred, con.convalidated,
               pg_get_constraintdef(con.oid, true)
        FROM pg_constraint con
        JOIN pg_namespace ns ON ns.oid = con.connamespace
        LEFT JOIN pg_class rel ON rel.oid = con.conrelid
        LEFT JOIN pg_type typ ON typ.oid = con.contypid
        WHERE ns.nspname = %s
        ORDER BY rel.relname NULLS FIRST, typ.typname NULLS FIRST, con.conname, con.contype
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
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "relations": _schema_relations(conn),
        "functions": _schema_functions(conn),
        "types": _schema_types(conn),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def schema_fingerprint(conn: psycopg.Connection) -> str:
    return _compute_schema_fingerprint(conn)


def _query_privilege(conn: psycopg.Connection, query: str, params: tuple[str, ...]) -> bool:
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise PostgresSchemaError("PostgreSQL privilege query returned no result")
    return bool(row[0])


def _validate_runtime_table_privileges(conn: psycopg.Connection, table: str) -> None:
    qualified = f"{SCHEMA_NAME}.{table}"
    required_dml = ("SELECT", "INSERT", "UPDATE", "DELETE")
    forbidden = ("TRUNCATE", "REFERENCES", "TRIGGER")
    for privilege in required_dml:
        if not _query_privilege(
            conn,
            "SELECT has_table_privilege(%s, %s, %s)",
            (RUNTIME_ROLE, qualified, privilege),
        ):
            raise PostgresSchemaError(f"qmtool_runtime missing {privilege} on {qualified}")
    for privilege in forbidden:
        if _query_privilege(
            conn,
            "SELECT has_table_privilege(%s, %s, %s)",
            (RUNTIME_ROLE, qualified, privilege),
        ):
            raise PostgresSchemaError(
                f"qmtool_runtime must not have {privilege} on {qualified}"
            )


def _validate_role_contract(
    conn: psycopg.Connection,
    *,
    require_history_select: bool,
    runtime_tables: tuple[str, ...],
) -> None:
    runtime_has_usage = _query_privilege(
        conn,
        "SELECT has_schema_privilege(%s, %s, %s)",
        (RUNTIME_ROLE, SCHEMA_NAME, "USAGE"),
    )
    runtime_has_create = _query_privilege(
        conn,
        "SELECT has_schema_privilege(%s, %s, %s)",
        (RUNTIME_ROLE, SCHEMA_NAME, "CREATE"),
    )
    if not runtime_has_usage or runtime_has_create:
        raise PostgresSchemaError(
            "qmtool_runtime must have schema USAGE and must not have schema CREATE"
        )

    public_schema_access = _query_privilege(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_namespace ns
            CROSS JOIN LATERAL aclexplode(
                COALESCE(ns.nspacl, acldefault('n', ns.nspowner))
            ) acl
            WHERE ns.nspname = %s
              AND acl.grantee = 0
              AND acl.privilege_type IN ('USAGE', 'CREATE')
        )
        """,
        (SCHEMA_NAME,),
    )
    if public_schema_access:
        raise PostgresSchemaError("PUBLIC must not have USAGE or CREATE on schema documents")

    for table in runtime_tables:
        _validate_runtime_table_privileges(conn, table)

    history = f"{SCHEMA_NAME}.{MIGRATIONS_TABLE}"
    if require_history_select:
        if not _query_privilege(
            conn,
            "SELECT has_table_privilege(%s, %s, %s)",
            (RUNTIME_ROLE, history, "SELECT"),
        ):
            raise PostgresSchemaError(f"qmtool_runtime missing SELECT on {history}")
    elif _query_privilege(
        conn,
        "SELECT has_table_privilege(%s, %s, %s)",
        (RUNTIME_ROLE, history, "SELECT"),
    ):
        raise PostgresSchemaError(f"qmtool_runtime must not have SELECT on {history}")
    for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
        if _query_privilege(
            conn,
            "SELECT has_table_privilege(%s, %s, %s)",
            (RUNTIME_ROLE, history, privilege),
        ):
            raise PostgresSchemaError(
                f"qmtool_runtime must not have {privilege} on {history}"
            )


def _validate_schema_contracts(
    conn: psycopg.Connection,
    *,
    require_history_select: bool,
    require_full: bool,
) -> None:
    expected_tables = EXPECTED_TABLES_FULL if require_full else EXPECTED_TABLES
    tables = _table_names(conn)
    missing_tables = expected_tables - tables
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

    missing_document_headers = EXPECTED_DOCUMENT_HEADERS_COLUMNS - columns_for("document_headers")
    if missing_document_headers:
        raise PostgresSchemaError(f"document_headers missing columns: {sorted(missing_document_headers)}")

    missing_document_versions = EXPECTED_DOCUMENT_VERSIONS_COLUMNS - columns_for("document_versions")
    if missing_document_versions:
        raise PostgresSchemaError(f"document_versions missing columns: {sorted(missing_document_versions)}")

    if require_full:
        missing_workflow_profile_definitions = (
            EXPECTED_WORKFLOW_PROFILE_DEFINITIONS_COLUMNS
            - columns_for("workflow_profile_definitions")
        )
        if missing_workflow_profile_definitions:
            raise PostgresSchemaError(
                f"workflow_profile_definitions missing columns: "
                f"{sorted(missing_workflow_profile_definitions)}"
            )

    missing_history = EXPECTED_HISTORY_COLUMNS - columns_for(MIGRATIONS_TABLE)
    if missing_history:
        raise PostgresSchemaError(
            f"{MIGRATIONS_TABLE} missing columns: {sorted(missing_history)}"
        )

    if require_full and EXPECTED_CHECK_CONSTRAINTS:
        checks = {
            str(row[0])
            for row in conn.execute(
                """
                SELECT con.conname
                FROM pg_constraint con
                JOIN pg_namespace ns ON ns.oid = con.connamespace
                JOIN pg_class rel ON rel.oid = con.conrelid
                WHERE ns.nspname = %s AND con.contype = 'c'
                """,
                (SCHEMA_NAME,),
            ).fetchall()
        }
        missing_checks = EXPECTED_CHECK_CONSTRAINTS - checks
        if missing_checks:
            raise PostgresSchemaError(f"missing check constraints: {sorted(missing_checks)}")

    owned_tables = tuple(sorted(expected_tables))
    for table in owned_tables:
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

    runtime_tables = ('document_headers', 'document_versions', 'document_artifacts', 'document_read_receipts', 'document_workflow_comments', 'document_pdf_read_sessions', 'document_pdf_read_page_progress', 'workflow_profile_definitions', 'workflow_profile_versions', 'workflow_profile_transitions', 'document_type_definitions', 'workflow_profile_imports') if require_full else ('document_headers', 'document_versions', 'document_artifacts', 'document_read_receipts', 'document_workflow_comments', 'document_pdf_read_sessions', 'document_pdf_read_page_progress')
    _validate_role_contract(
        conn,
        require_history_select=require_history_select,
        runtime_tables=runtime_tables,
    )


def _activate_migrator_role(conn: psycopg.Connection) -> None:
    conn.execute(f"SET ROLE {MIGRATOR_ROLE}")
    current = conn.execute("SELECT current_user").fetchone()
    if current is None or current[0] != MIGRATOR_ROLE:
        raise PostgresSchemaError(
            f"SET ROLE {MIGRATOR_ROLE} failed; effective user is "
            f"{None if current is None else current[0]!r}"
        )


def migrate_documents_schema(
    dsn: str,
    *,
    migrations_dir: Path | None = None,
) -> int:
    steps = discover_migrations(migrations_dir)
    target = steps[-1].version

    with psycopg.connect(dsn, autocommit=True) as conn:
        locked = conn.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_KEY,)).fetchone()
        if locked is None or not locked[0]:
            raise PostgresSchemaError("documents schema migration already in progress (advisory lock held)")
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
                    _validate_schema_contracts(
                        conn,
                        require_history_select=step.version >= 3,
                        require_full=step.version >= 2,
                    )
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
            _validate_schema_contracts(
                conn,
                require_history_select=target >= 3,
                require_full=target >= 2,
            )
            return target
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))


def assert_runtime_schema_ready(dsn: str, *, migrations_dir: Path | None = None) -> int:
    steps = discover_migrations(migrations_dir)
    target = steps[-1].version
    with _runtime_connection_for_schema(dsn) as conn:
        if not _history_table_exists(conn):
            raise PostgresSchemaError("documents schema history is missing")
        applied = _fetch_applied(conn)
        if not applied:
            raise PostgresSchemaError("documents schema history is empty")
        _validate_history_prefix(applied, steps)
        if applied[-1].version != target:
            raise PostgresSchemaError(
                f"documents schema not ready: applied version "
                f"{applied[-1].version}, expected {target}"
            )
        current_fp = _compute_schema_fingerprint(conn)
        if current_fp != applied[-1].schema_fingerprint:
            raise PostgresSchemaError(
                "schema fingerprint drift detected against last applied migration"
            )
        _validate_schema_contracts(
            conn,
            require_history_select=True,
            require_full=target >= 2,
        )
        return target
