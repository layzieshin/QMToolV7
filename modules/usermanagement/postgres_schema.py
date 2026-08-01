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


def _schema_relations(conn: psycopg.Connection) -> list[tuple[object, ...]]:
    return conn.execute(
        """
        SELECT rel.relname,
               rel.relkind,
               owner.rolname,
               rel.relpersistence,
               COALESCE((
                   SELECT json_agg(rel_option.value ORDER BY rel_option.value)::text
                   FROM unnest(COALESCE(rel.reloptions, ARRAY[]::text[])) rel_option(value)
               ), ''),
               CASE
                   WHEN rel.relkind IN ('v', 'm') THEN pg_get_viewdef(rel.oid, true)
                   ELSE ''
               END,
               COALESCE(pg_get_partkeydef(rel.oid), ''),
               CASE
                   WHEN rel.relispartition THEN pg_get_expr(rel.relpartbound, rel.oid, true)
                   ELSE ''
               END,
               CASE
                   WHEN rel.relkind = 'S' THEN format_type(seq.seqtypid, -1)
                   ELSE ''
               END,
               seq.seqstart,
               seq.seqincrement,
               seq.seqmax,
               seq.seqmin,
               seq.seqcache,
               seq.seqcycle,
               foreign_server.srvname,
               COALESCE((
                   SELECT json_agg(ft_option.value ORDER BY ft_option.value)::text
                   FROM unnest(
                       COALESCE(foreign_table.ftoptions, ARRAY[]::text[])
                   ) ft_option(value)
               ), '')
        FROM pg_class rel
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        JOIN pg_roles owner ON owner.oid = rel.relowner
        LEFT JOIN pg_sequence seq ON seq.seqrelid = rel.oid
        LEFT JOIN pg_foreign_table foreign_table ON foreign_table.ftrelid = rel.oid
        LEFT JOIN pg_foreign_server foreign_server
          ON foreign_server.oid = foreign_table.ftserver
        WHERE ns.nspname = %s
          AND rel.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
        ORDER BY rel.relname, rel.relkind
        """,
        (SCHEMA_NAME,),
    ).fetchall()


def _schema_functions(conn: psycopg.Connection) -> list[tuple[object, ...]]:
    return conn.execute(
        """
        SELECT proc.proname,
               pg_get_function_identity_arguments(proc.oid),
               pg_get_function_result(proc.oid),
               proc.prokind,
               proc.provolatile,
               proc.proparallel,
               proc.prosecdef,
               proc.proleakproof,
               pg_get_functiondef(proc.oid)
        FROM pg_proc proc
        JOIN pg_namespace ns ON ns.oid = proc.pronamespace
        WHERE ns.nspname = %s
        ORDER BY proc.proname,
                 pg_get_function_identity_arguments(proc.oid)
        """,
        (SCHEMA_NAME,),
    ).fetchall()


def _schema_types(conn: psycopg.Connection) -> list[tuple[object, ...]]:
    return conn.execute(
        """
        SELECT typ.typname,
               typ.typtype,
               typ.typcategory,
               typ.typispreferred,
               CASE
                   WHEN typ.typbasetype = 0 THEN NULL
                   ELSE format_type(typ.typbasetype, typ.typtypmod)
               END,
               typ.typnotnull,
               typ.typdefault,
               collation_ns.nspname,
               coll.collname,
               COALESCE((
                   SELECT json_agg(enum_value.enumlabel ORDER BY enum_value.enumsortorder)::text
                   FROM pg_enum enum_value
                   WHERE enum_value.enumtypid = typ.oid
               ), ''),
               COALESCE((
                   SELECT json_agg(
                       json_build_array(
                           attribute.attname,
                           format_type(attribute.atttypid, attribute.atttypmod),
                           attribute.attnotnull
                       ) ORDER BY attribute.attnum
                   )::text
                   FROM pg_attribute attribute
                   WHERE attribute.attrelid = typ.typrelid
                     AND attribute.attnum > 0
                     AND NOT attribute.attisdropped
               ), ''),
               CASE
                   WHEN range_contract.rngsubtype = 0 THEN NULL
                   ELSE format_type(range_contract.rngsubtype, -1)
               END,
               operator_ns.nspname,
               operator_class.opcname,
               CASE
                   WHEN range_contract.rngcanonical = 0 THEN NULL
                   ELSE range_contract.rngcanonical::regprocedure::text
               END,
               CASE
                   WHEN range_contract.rngsubdiff = 0 THEN NULL
                   ELSE range_contract.rngsubdiff::regprocedure::text
               END
        FROM pg_type typ
        JOIN pg_namespace ns ON ns.oid = typ.typnamespace
        LEFT JOIN pg_class rel ON rel.oid = typ.typrelid
        LEFT JOIN pg_collation coll ON coll.oid = typ.typcollation
        LEFT JOIN pg_namespace collation_ns
          ON collation_ns.oid = coll.collnamespace
        LEFT JOIN pg_range range_contract
          ON range_contract.rngtypid = typ.oid
          OR range_contract.rngmultitypid = typ.oid
        LEFT JOIN pg_opclass operator_class
          ON operator_class.oid = range_contract.rngsubopc
        LEFT JOIN pg_namespace operator_ns
          ON operator_ns.oid = operator_class.opcnamespace
        WHERE ns.nspname = %s
          AND typ.typtype IN ('c', 'd', 'e', 'r', 'm')
          AND (typ.typrelid = 0 OR rel.relkind = 'c')
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
    relations = _schema_relations(conn)
    functions = _schema_functions(conn)
    types = _schema_types(conn)
    if relations or functions or types:
        raise PostgresSchemaError(
            "populated unversioned schema usermanagement refused; "
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
        SELECT COALESCE(rel.relname, ''),
               COALESCE(typ.typname, ''),
               con.conname,
               con.contype,
               con.condeferrable,
               con.condeferred,
               con.convalidated,
               pg_get_constraintdef(con.oid, true)
        FROM pg_constraint con
        JOIN pg_namespace ns ON ns.oid = con.connamespace
        LEFT JOIN pg_class rel ON rel.oid = con.conrelid
        LEFT JOIN pg_type typ ON typ.oid = con.contypid
        WHERE ns.nspname = %s
        ORDER BY rel.relname NULLS FIRST,
                 typ.typname NULLS FIRST,
                 con.conname,
                 con.contype
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
    relations = _schema_relations(conn)
    functions = _schema_functions(conn)
    types = _schema_types(conn)
    payload = {
        "relations": [
            {
                "name": name,
                "kind": kind,
                "owner": owner,
                "persistence": persistence,
                "options": options,
                "view_definition": view_definition,
                "partition_key": partition_key,
                "partition_bound": partition_bound,
                "sequence_type": sequence_type,
                "sequence_start": sequence_start,
                "sequence_increment": sequence_increment,
                "sequence_max": sequence_max,
                "sequence_min": sequence_min,
                "sequence_cache": sequence_cache,
                "sequence_cycle": sequence_cycle,
                "foreign_server": foreign_server,
                "foreign_options": foreign_options,
            }
            for (
                name,
                kind,
                owner,
                persistence,
                options,
                view_definition,
                partition_key,
                partition_bound,
                sequence_type,
                sequence_start,
                sequence_increment,
                sequence_max,
                sequence_min,
                sequence_cache,
                sequence_cycle,
                foreign_server,
                foreign_options,
            ) in relations
        ],
        "columns": [
            {
                "table": table,
                "column": column,
                "type": data_type,
                "nullable": nullable,
                "default": default,
                "position": position,
                "udt_schema": udt_schema,
                "udt_name": udt_name,
                "identity": identity,
                "identity_generation": identity_generation,
                "generated": generated,
                "generation_expression": generation_expression,
            }
            for (
                table,
                column,
                data_type,
                nullable,
                default,
                position,
                udt_schema,
                udt_name,
                identity,
                identity_generation,
                generated,
                generation_expression,
            ) in columns
        ],
        "constraints": [
            {
                "table": table,
                "domain": domain,
                "name": name,
                "type": constraint_type,
                "deferrable": deferrable,
                "deferred": deferred,
                "validated": validated,
                "definition": definition,
            }
            for (
                table,
                domain,
                name,
                constraint_type,
                deferrable,
                deferred,
                validated,
                definition,
            ) in constraints
        ],
        "indexes": [
            {"table": table, "name": name, "def": indexdef}
            for table, name, indexdef in indexes
        ],
        "functions": [
            {
                "name": name,
                "arguments": arguments,
                "result": result,
                "kind": kind,
                "volatility": volatility,
                "parallel": parallel,
                "security_definer": security_definer,
                "leakproof": leakproof,
                "definition": definition,
            }
            for (
                name,
                arguments,
                result,
                kind,
                volatility,
                parallel,
                security_definer,
                leakproof,
                definition,
            ) in functions
        ],
        "types": [
            {
                "name": name,
                "kind": kind,
                "category": category,
                "preferred": preferred,
                "base_type": base_type,
                "not_null": not_null,
                "default": default,
                "collation_schema": collation_schema,
                "collation_name": collation_name,
                "enum_values": enum_values,
                "attributes": attributes,
                "range_subtype": range_subtype,
                "range_operator_schema": range_operator_schema,
                "range_operator_class": range_operator_class,
                "range_canonical": range_canonical,
                "range_subdiff": range_subdiff,
            }
            for (
                name,
                kind,
                category,
                preferred,
                base_type,
                not_null,
                default,
                collation_schema,
                collation_name,
                enum_values,
                attributes,
                range_subtype,
                range_operator_schema,
                range_operator_class,
                range_canonical,
                range_subdiff,
            ) in types
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _query_privilege(
    conn: psycopg.Connection,
    query: str,
    params: tuple[str, ...],
) -> bool:
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise PostgresSchemaError("PostgreSQL privilege query returned no result")
    return bool(row[0])


def _validate_role_contract(
    conn: psycopg.Connection,
    *,
    require_history_select: bool = True,
) -> None:
    role_rows = conn.execute(
        """
        SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
               rolreplication, rolbypassrls
        FROM pg_roles
        WHERE rolname IN (%s, %s)
        ORDER BY rolname
        """,
        (MIGRATOR_ROLE, RUNTIME_ROLE),
    ).fetchall()
    roles = {str(row[0]): row for row in role_rows}
    missing_roles = {MIGRATOR_ROLE, RUNTIME_ROLE} - set(roles)
    if missing_roles:
        raise PostgresSchemaError(
            f"missing PostgreSQL privilege roles: {sorted(missing_roles)}"
        )
    for role_name, row in roles.items():
        if any(bool(value) for value in row[1:]):
            raise PostgresSchemaError(
                f"role {role_name} must be NOLOGIN without elevated attributes"
            )

    inherited_roles = conn.execute(
        """
        SELECT member_role.rolname, granted_role.rolname
        FROM pg_auth_members membership
        JOIN pg_roles member_role ON member_role.oid = membership.member
        JOIN pg_roles granted_role ON granted_role.oid = membership.roleid
        WHERE member_role.rolname IN (%s, %s)
        ORDER BY member_role.rolname, granted_role.rolname
        """,
        (MIGRATOR_ROLE, RUNTIME_ROLE),
    ).fetchall()
    if inherited_roles:
        raise PostgresSchemaError(
            "qmtool privilege roles must not inherit other roles: "
            f"{[(str(member), str(granted)) for member, granted in inherited_roles]}"
        )

    membership = conn.execute(
        """
        SELECT pg_has_role(%s, %s, 'MEMBER'),
               pg_has_role(%s, %s, 'SET')
        """,
        (RUNTIME_ROLE, MIGRATOR_ROLE, RUNTIME_ROLE, MIGRATOR_ROLE),
    ).fetchone()
    if membership is None or bool(membership[0]) or bool(membership[1]):
        raise PostgresSchemaError(
            "qmtool_runtime must not inherit or SET ROLE to qmtool_migrator"
        )

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
        raise PostgresSchemaError(
            "PUBLIC must not have USAGE or CREATE on schema usermanagement"
        )

    required_dml = ("SELECT", "INSERT", "UPDATE", "DELETE")
    forbidden_table_privileges = ("TRUNCATE", "REFERENCES", "TRIGGER")
    for table in ("users", "sessions"):
        qualified = f"{SCHEMA_NAME}.{table}"
        for privilege in required_dml:
            if not _query_privilege(
                conn,
                "SELECT has_table_privilege(%s, %s, %s)",
                (RUNTIME_ROLE, qualified, privilege),
            ):
                raise PostgresSchemaError(
                    f"qmtool_runtime missing {privilege} on {qualified}"
                )
        for privilege in forbidden_table_privileges:
            if _query_privilege(
                conn,
                "SELECT has_table_privilege(%s, %s, %s)",
                (RUNTIME_ROLE, qualified, privilege),
            ):
                raise PostgresSchemaError(
                    f"qmtool_runtime must not have {privilege} on {qualified}"
                )

    history = f"{SCHEMA_NAME}.{MIGRATIONS_TABLE}"
    if require_history_select:
        if not _query_privilege(
            conn,
            "SELECT has_table_privilege(%s, %s, %s)",
            (RUNTIME_ROLE, history, "SELECT"),
        ):
            raise PostgresSchemaError(f"qmtool_runtime missing SELECT on {history}")
    else:
        if _query_privilege(
            conn,
            "SELECT has_table_privilege(%s, %s, %s)",
            (RUNTIME_ROLE, history, "SELECT"),
        ):
            raise PostgresSchemaError(
                f"qmtool_runtime must not have SELECT on {history}"
            )
    for privilege in ("INSERT", "UPDATE", "DELETE") + forbidden_table_privileges:
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
    require_history_select: bool = True,
) -> None:
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
    _validate_role_contract(conn, require_history_select=require_history_select)


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
                    _validate_schema_contracts(
                        conn,
                        require_history_select=step.version >= 2,
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
                require_history_select=target >= 2,
            )
            return target
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))


def assert_runtime_schema_ready(dsn: str, *, migrations_dir: Path | None = None) -> int:
    """Fail-closed readiness check for the runtime LOGIN (no migration apply).

    Requires SELECT on the history table (migration 0002+) and that the highest
    applied version equals the registered migration target.
    """
    from .postgres_connection import runtime_connection

    steps = discover_migrations(migrations_dir)
    target = steps[-1].version
    with runtime_connection(dsn) as conn:
        if not _history_table_exists(conn):
            raise PostgresSchemaError("usermanagement schema history is missing")
        row = conn.execute(
            f"""
            SELECT COALESCE(MAX(version), 0)
            FROM {SCHEMA_NAME}.{MIGRATIONS_TABLE}
            """
        ).fetchone()
        applied = int(row[0]) if row is not None else 0
        if applied != target:
            raise PostgresSchemaError(
                f"usermanagement schema not ready: applied version {applied}, "
                f"expected {target}"
            )
        return applied
