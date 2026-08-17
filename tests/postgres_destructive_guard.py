"""Fail-closed guard for destructive PostgreSQL live fixtures (J04-M0 M3).

Test-only. Product code must not import this module.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import psycopg

EXPECTED_DATABASE = "qmtool_j04_destructive_test"
EXPECTED_CLUSTER_MARKER = "j04_m0_destructive_pg16"
RESET_OPT_IN_VALUE = "I_UNDERSTAND_THIS_IS_DESTRUCTIVE"
TEST_ADMIN_DSN_ENV = "QMTOOL_PG_TEST_ADMIN_DSN"
TEST_RESET_ENV = "QMTOOL_PG_TEST_RESET"
TEST_EXPECTED_DATABASE_ENV = "QMTOOL_PG_TEST_EXPECTED_DATABASE"
TEST_EXPECTED_MAJOR_ENV = "QMTOOL_PG_TEST_EXPECTED_MAJOR"
DEFAULT_EXPECTED_MAJOR = 16
MINIMUM_MAJOR = 16
MARKER_TABLE = "public.qmtool_j04_test_cluster_marker"
MARKER_KEY = "cluster_id"

_FORBIDDEN_DATABASE_NAMES = frozenset(
    {
        "postgres",
        "template0",
        "template1",
        "qmtool",
        "qmtool_app",
    }
)

_SECRET_KEYS = frozenset({"password", "passfile", "sslpassword"})
_SECRET_PATTERN = re.compile(r"(password|pwd)=([^\s]+)", re.IGNORECASE)


class DestructivePostgresGuardError(RuntimeError):
    """Raised when destructive PostgreSQL tests must not proceed."""

    def __str__(self) -> str:  # noqa: D105
        return _redact_secrets(super().__str__())

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}(<redacted>)"


@dataclass(frozen=True)
class ApprovedDestructiveTarget:
    """Opaque approved identity for destructive fixtures."""

    database: str
    major_version: int
    cluster_marker: str
    host: str
    port: str

    def __repr__(self) -> str:  # noqa: D105
        return (
            "ApprovedDestructiveTarget("
            f"database={self.database!r}, major_version={self.major_version}, "
            f"cluster_marker={self.cluster_marker!r}, host=<redacted>, port={self.port!r})"
        )


def _redact_secrets(message: str) -> str:
    return _SECRET_PATTERN.sub(r"\1=<redacted>", message)


def _parse_conninfo(dsn: str) -> dict[str, Any]:
    try:
        return psycopg.conninfo.conninfo_to_dict(dsn)
    except Exception as exc:  # noqa: BLE001
        raise DestructivePostgresGuardError("invalid PostgreSQL test DSN") from None


def _normalize_host(host: str | None) -> str:
    value = (host or "").strip().lower()
    if value in {"localhost", "127.0.0.1", "::1"}:
        return "127.0.0.1"
    return value


def _endpoint(conninfo: dict[str, Any]) -> tuple[str, str]:
    host = _normalize_host(str(conninfo.get("host") or ""))
    port = str(conninfo.get("port") or "5432").strip() or "5432"
    return host, port


def _admin_target_identity(dsn: str) -> tuple[str, str, str, str]:
    """Cluster + login identity without passwords (guard boundary)."""
    info = _parse_conninfo(dsn)
    host, port = _endpoint(info)
    return (
        host,
        port,
        str(info.get("dbname") or "").strip(),
        str(info.get("user") or "").strip(),
    )


def same_approved_admin_target(candidate_dsn: str, approved_dsn: str) -> bool:
    """True when candidate targets the same admin identity as the approved DSN."""
    return _admin_target_identity(candidate_dsn) == _admin_target_identity(approved_dsn)


def _runtime_conninfo() -> dict[str, Any] | None:
    dsn = os.environ.get("QMTOOL_PG_DSN", "").strip()
    if dsn:
        return _parse_conninfo(dsn)
    host = os.environ.get("QMTOOL_PG_HOST", "").strip()
    database = os.environ.get("QMTOOL_PG_DATABASE", "").strip()
    user = os.environ.get("QMTOOL_PG_USER", "").strip()
    password = os.environ.get("QMTOOL_PG_PASSWORD", "")
    if not (host and database and user and password):
        return None
    port = os.environ.get("QMTOOL_PG_PORT", "5432").strip() or "5432"
    return {
        "host": host,
        "port": port,
        "dbname": database,
        "user": user,
        "password": password,
    }


def _forbidden_databases() -> set[str]:
    names = set(_FORBIDDEN_DATABASE_NAMES)
    runtime = _runtime_conninfo()
    if runtime is not None:
        dbname = str(runtime.get("dbname") or "").strip()
        # Temporary in-test QMTOOL_PG_DSN pointing at the isolated DB is not lab.
        if dbname and dbname != EXPECTED_DATABASE:
            names.add(dbname)
    configured = os.environ.get("QMTOOL_PG_DATABASE", "").strip()
    if configured and configured != EXPECTED_DATABASE:
        names.add(configured)
    return names


def _expected_major() -> int:
    """Parse Slot-2 expected major. Unset defaults to 16; invalid values fail closed."""
    raw = os.environ.get(TEST_EXPECTED_MAJOR_ENV, "").strip()
    if not raw:
        return DEFAULT_EXPECTED_MAJOR
    if not raw.isdigit() or raw != str(int(raw)):
        raise DestructivePostgresGuardError(
            f"{TEST_EXPECTED_MAJOR_ENV} must be an integer major version"
        )
    value = int(raw)
    if value < MINIMUM_MAJOR:
        raise DestructivePostgresGuardError(
            f"{TEST_EXPECTED_MAJOR_ENV} must be at least {MINIMUM_MAJOR}"
        )
    return value


def _assert_major(major: int, expected: int) -> None:
    if major < MINIMUM_MAJOR:
        raise DestructivePostgresGuardError(
            f"PostgreSQL major version must be at least {MINIMUM_MAJOR}"
        )
    if major != expected:
        raise DestructivePostgresGuardError(
            "PostgreSQL major version must match QMTOOL_PG_TEST_EXPECTED_MAJOR"
        )


def _assert_admin_privileges(conn: psycopg.Connection) -> None:
    """Fail-closed admin/ownership probe for the destructive test login."""
    role = conn.execute(
        """
        SELECT rolsuper, rolcreaterole, rolcreatedb
        FROM pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()
    if role is None:
        raise DestructivePostgresGuardError("admin login role is not visible in pg_roles")
    rolsuper, rolcreaterole, rolcreatedb = (bool(role[0]), bool(role[1]), bool(role[2]))

    owner_row = conn.execute(
        """
        SELECT pg_catalog.pg_get_userbyid(datdba) = current_user
        FROM pg_database
        WHERE datname = current_database()
        """
    ).fetchone()
    if owner_row is None:
        raise DestructivePostgresGuardError("unable to resolve test database ownership")
    is_owner = bool(owner_row[0])

    if rolsuper:
        return
    if not is_owner:
        raise DestructivePostgresGuardError(
            "admin login must own the isolated test database or be a superuser"
        )
    if not rolcreaterole:
        raise DestructivePostgresGuardError("admin login lacks CREATEROLE")
    if not rolcreatedb:
        raise DestructivePostgresGuardError("admin login lacks CREATEDB")


def require_destructive_postgres_target(
    *,
    connect: bool = True,
    require_opt_in: bool = True,
) -> ApprovedDestructiveTarget:
    """Validate identity. Destructive paths must pass ``require_opt_in=True``."""
    test_dsn = os.environ.get(TEST_ADMIN_DSN_ENV, "").strip()
    if not test_dsn:
        raise DestructivePostgresGuardError(
            f"{TEST_ADMIN_DSN_ENV} is required for destructive PostgreSQL tests"
        )

    if require_opt_in:
        reset = os.environ.get(TEST_RESET_ENV, "").strip()
        if reset != RESET_OPT_IN_VALUE:
            raise DestructivePostgresGuardError(
                f"{TEST_RESET_ENV} must equal the documented destructive opt-in value"
            )

    # Hard ban: never treat runtime DSN env as the destructive target.
    if test_dsn == os.environ.get("QMTOOL_PG_DSN", "").strip():
        raise DestructivePostgresGuardError("test DSN must not equal QMTOOL_PG_DSN")

    test_info = _parse_conninfo(test_dsn)
    for key in _SECRET_KEYS:
        # Keep secrets out of accidental formatting by ensuring we never return raw DSN.
        test_info.get(key)

    expected_db = (
        os.environ.get(TEST_EXPECTED_DATABASE_ENV, "").strip() or EXPECTED_DATABASE
    )
    if expected_db != EXPECTED_DATABASE:
        raise DestructivePostgresGuardError("unexpected QMTOOL_PG_TEST_EXPECTED_DATABASE")

    dbname = str(test_info.get("dbname") or "").strip()
    if dbname != expected_db:
        raise DestructivePostgresGuardError("test DSN database name is not the isolated test database")
    if dbname in _forbidden_databases():
        raise DestructivePostgresGuardError("test DSN targets a forbidden database name")

    runtime = _runtime_conninfo()
    if runtime is not None:
        runtime_db = str(runtime.get("dbname") or "").strip()
        # In-process live fixtures temporarily point QMTOOL_PG_DSN at the
        # isolated test-cluster runtime login. That is not a lab identity.
        runtime_is_external = bool(runtime_db) and runtime_db != expected_db
        if runtime_is_external and _endpoint(test_info) == _endpoint(runtime):
            raise DestructivePostgresGuardError("test endpoint matches runtime/lab endpoint")
        if runtime_is_external and runtime_db == dbname:
            raise DestructivePostgresGuardError("test database name collides with runtime database")

    expected_major = _expected_major()

    if not connect:
        host, port = _endpoint(test_info)
        return ApprovedDestructiveTarget(
            database=dbname,
            major_version=expected_major,
            cluster_marker=EXPECTED_CLUSTER_MARKER,
            host=host,
            port=port,
        )

    try:
        with psycopg.connect(test_dsn) as conn:
            current_db = conn.execute("SELECT current_database()").fetchone()[0]
            if str(current_db) != expected_db:
                raise DestructivePostgresGuardError("connected database is not the isolated test database")
            version_row = conn.execute("SHOW server_version_num").fetchone()
            major = int(str(version_row[0])) // 10000
            _assert_major(major, expected_major)
            marker = conn.execute(
                f"""
                SELECT marker_value
                FROM {MARKER_TABLE}
                WHERE marker_key = %s
                """,
                (MARKER_KEY,),
            ).fetchone()
            if marker is None or str(marker[0]) != EXPECTED_CLUSTER_MARKER:
                raise DestructivePostgresGuardError("missing or incorrect test cluster marker")
            _assert_admin_privileges(conn)
            host, port = _endpoint(test_info)
            return ApprovedDestructiveTarget(
                database=expected_db,
                major_version=major,
                cluster_marker=EXPECTED_CLUSTER_MARKER,
                host=host,
                port=port,
            )
    except DestructivePostgresGuardError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DestructivePostgresGuardError(
            f"destructive PostgreSQL identity check failed: {type(exc).__name__}"
        ) from None


def preflight_isolated_postgres_target() -> ApprovedDestructiveTarget:
    """Read-only identity checks. Does not require destructive opt-in."""
    return require_destructive_postgres_target(connect=True, require_opt_in=False)


def require_approved_admin_dsn(*, candidate: str | None = None) -> str:
    """Return the validated test admin DSN after guard checks (never log it).

    Destructive helpers must connect only with this return value. A freely
    supplied ``candidate`` may not bypass the guard: it is accepted only when it
    targets the same admin identity as ``QMTOOL_PG_TEST_ADMIN_DSN``.
    """
    require_destructive_postgres_target(connect=True)
    approved = os.environ[TEST_ADMIN_DSN_ENV].strip()
    if candidate is not None and not same_approved_admin_target(candidate, approved):
        raise DestructivePostgresGuardError(
            "admin DSN does not match the guard-approved destructive test target"
        )
    return approved
