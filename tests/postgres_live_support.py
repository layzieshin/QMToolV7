"""Central fixtures/helpers for destructive PostgreSQL live tests (J04-M0 M3).

All DROP SCHEMA / DROP ROLE / DROP OWNED / DROP DATABASE paths must call the
destructive guard first and connect only with the guard-approved admin DSN.
Product modules must not import this file.
"""
from __future__ import annotations

import os
import secrets
import string
from dataclasses import dataclass

import psycopg
import pytest

from modules.usermanagement import postgres_schema as pgs
from tests.postgres_destructive_guard import (
    EXPECTED_DATABASE,
    DestructivePostgresGuardError,
    require_approved_admin_dsn,
)

MIGRATOR_LOGIN = "qmtool_j04_mig_login"
RUNTIME_LOGIN = "qmtool_j04_rt_login"
# Create/drop allowlist aligned to the AP-028 product drill prefix contract.
# Broader than the exact product prefix so negative-name fixtures can still be
# created safely inside the isolated cluster.
RESTORE_DB_PREFIX = "qmtool_um_restore_"
RESTORE_DB = "qmtool_um_restore_drill"
WRONG_RESTORE_DB = "qmtool_um_restore_wrong_target"


@dataclass(frozen=True)
class LivePostgresEnv:
    admin_dsn: str
    migrator_dsn: str
    runtime_dsn: str
    migrator_password: str
    runtime_password: str

    def __repr__(self) -> str:  # noqa: D105
        return (
            "LivePostgresEnv(admin_dsn=<redacted>, migrator_dsn=<redacted>, "
            "runtime_dsn=<redacted>, migrator_password=<redacted>, "
            "runtime_password=<redacted>)"
        )


def _password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "J04" + "".join(secrets.choice(alphabet) for _ in range(24))


def _dsn_with_user(dsn: str, user: str, password: str) -> str:
    conninfo = psycopg.conninfo.conninfo_to_dict(dsn)
    conninfo["user"] = user
    conninfo["password"] = password
    return psycopg.conninfo.make_conninfo(**conninfo)


def _dsn_with_db(dsn: str, database_name: str) -> str:
    conninfo = psycopg.conninfo.conninfo_to_dict(dsn)
    conninfo["dbname"] = database_name
    return psycopg.conninfo.make_conninfo(**conninfo)


def os_environ_required() -> bool:
    return os.environ.get("QMTOOL_PG_REQUIRED", "").strip() == "1"


def require_test_admin_dsn() -> str:
    """Resolve the isolated test admin DSN or skip/fail. Never uses QMTOOL_PG_DSN."""
    try:
        return require_approved_admin_dsn()
    except DestructivePostgresGuardError as exc:
        if os_environ_required():
            pytest.fail(str(exc))
        pytest.skip(str(exc))


def _drop_role_if_exists(conn: psycopg.Connection, role: str) -> None:
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
    if not exists:
        return
    conn.execute(
        psycopg.sql.SQL("DROP OWNED BY {} CASCADE").format(psycopg.sql.Identifier(role))
    )
    conn.execute(psycopg.sql.SQL("DROP ROLE {}").format(psycopg.sql.Identifier(role)))


def cleanup_live_environment(*, admin_dsn: str | None = None) -> None:
    approved = require_approved_admin_dsn(candidate=admin_dsn)
    with psycopg.connect(approved, autocommit=True) as conn:
        current = conn.execute("SELECT current_database()").fetchone()[0]
        if str(current) != EXPECTED_DATABASE:
            raise DestructivePostgresGuardError("refusing cleanup outside isolated test database")
        conn.execute("DROP SCHEMA IF EXISTS usermanagement CASCADE")
        for role in (MIGRATOR_LOGIN, RUNTIME_LOGIN, "qmtool_runtime", "qmtool_migrator"):
            _drop_role_if_exists(conn, role)


def prepare_live_environment(*, admin_dsn: str | None = None) -> LivePostgresEnv:
    approved_dsn = require_approved_admin_dsn(candidate=admin_dsn)
    cleanup_live_environment(admin_dsn=approved_dsn)
    migrator_password = _password()
    runtime_password = _password()
    pgs.provision_usermanagement_roles(approved_dsn)
    with psycopg.connect(approved_dsn, autocommit=True) as admin:
        dbname = admin.execute("SELECT current_database()").fetchone()[0]
        if str(dbname) != EXPECTED_DATABASE:
            raise DestructivePostgresGuardError("refusing provision outside isolated test database")
        admin.execute(
            psycopg.sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} IN ROLE {}").format(
                psycopg.sql.Identifier(MIGRATOR_LOGIN),
                psycopg.sql.Literal(migrator_password),
                psycopg.sql.Identifier(pgs.MIGRATOR_ROLE),
            )
        )
        admin.execute(
            psycopg.sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} IN ROLE {}").format(
                psycopg.sql.Identifier(RUNTIME_LOGIN),
                psycopg.sql.Literal(runtime_password),
                psycopg.sql.Identifier(pgs.RUNTIME_ROLE),
            )
        )
        admin.execute(
            psycopg.sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                psycopg.sql.Identifier(str(dbname)),
                psycopg.sql.Identifier(MIGRATOR_LOGIN),
            )
        )
        admin.execute(
            psycopg.sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                psycopg.sql.Identifier(str(dbname)),
                psycopg.sql.Identifier(RUNTIME_LOGIN),
            )
        )
    return LivePostgresEnv(
        admin_dsn=approved_dsn,
        migrator_dsn=_dsn_with_user(approved_dsn, MIGRATOR_LOGIN, migrator_password),
        runtime_dsn=_dsn_with_user(approved_dsn, RUNTIME_LOGIN, runtime_password),
        migrator_password=migrator_password,
        runtime_password=runtime_password,
    )


def drop_restore_database(database_name: str, *, admin_dsn: str | None = None) -> None:
    approved = require_approved_admin_dsn(candidate=admin_dsn)
    if not database_name.startswith(RESTORE_DB_PREFIX):
        raise DestructivePostgresGuardError("restore database name missing required test prefix")
    with psycopg.connect(approved, autocommit=True) as admin:
        admin.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (database_name,),
        )
        admin.execute(
            psycopg.sql.SQL("DROP DATABASE IF EXISTS {}").format(
                psycopg.sql.Identifier(database_name)
            )
        )


def prepare_restore_database(
    database_name: str,
    *,
    migrator_password: str,
    admin_dsn: str | None = None,
) -> str:
    approved = require_approved_admin_dsn(candidate=admin_dsn)
    if not database_name.startswith(RESTORE_DB_PREFIX):
        raise DestructivePostgresGuardError("restore database name missing required test prefix")
    drop_restore_database(database_name, admin_dsn=approved)
    with psycopg.connect(approved, autocommit=True) as admin:
        database = psycopg.sql.Identifier(database_name)
        admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(database))
        admin.execute(
            psycopg.sql.SQL("GRANT CONNECT, CREATE ON DATABASE {} TO {}").format(
                database,
                psycopg.sql.Identifier(MIGRATOR_LOGIN),
            )
        )
        admin.execute(
            psycopg.sql.SQL("GRANT CONNECT, CREATE ON DATABASE {} TO {}").format(
                database,
                psycopg.sql.Identifier(pgs.MIGRATOR_ROLE),
            )
        )
    return _dsn_with_db(
        _dsn_with_user(approved, MIGRATOR_LOGIN, migrator_password),
        database_name,
    )


def guarded_drop_usermanagement_schema(*, admin_dsn: str | None = None) -> None:
    """DROP SCHEMA usermanagement after guard approval (in-test mutations)."""
    approved = require_approved_admin_dsn(candidate=admin_dsn)
    with psycopg.connect(approved, autocommit=True) as conn:
        current = conn.execute("SELECT current_database()").fetchone()[0]
        if str(current) != EXPECTED_DATABASE:
            raise DestructivePostgresGuardError("refusing DROP SCHEMA outside isolated test database")
        conn.execute("DROP SCHEMA IF EXISTS usermanagement CASCADE")


@pytest.fixture
def live_postgres_env() -> LivePostgresEnv:
    try:
        env = prepare_live_environment()
    except DestructivePostgresGuardError as exc:
        if os_environ_required():
            pytest.fail(str(exc))
        pytest.skip(str(exc))
    yield env
    cleanup_live_environment(admin_dsn=env.admin_dsn)
