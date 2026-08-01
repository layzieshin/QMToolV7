"""Runtime PostgreSQL connections for the Usermanagement repositories."""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row

RUNTIME_ROLE = "qmtool_runtime"
MIGRATOR_ROLE = "qmtool_migrator"


class PostgresRepositoryError(RuntimeError):
    """Raised when a repository connection violates the runtime contract."""


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
        raise PostgresRepositoryError("could not validate PostgreSQL runtime identity")

    if isinstance(row, dict):
        current_user = row["current_user"]
        session_user = row["session_user"]
        runtime_member = row["runtime_member"]
        runtime_set = row["runtime_set"]
        migrator_member = row["migrator_member"]
        migrator_set = row["migrator_set"]
    else:
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
        raise PostgresRepositoryError(
            "PostgreSQL repository requires a LOGIN member of qmtool_runtime "
            "without qmtool_migrator membership"
        )


@contextmanager
def runtime_connection(dsn: str) -> Iterator[psycopg.Connection]:
    """Open one transaction-scoped connection as the application runtime role."""
    if not str(dsn).strip():
        raise ValueError("PostgreSQL DSN is required")
    with psycopg.connect(str(dsn), row_factory=dict_row) as conn:
        _validate_runtime_identity(conn)
        yield conn


@contextmanager
def runtime_connection_for_schema(dsn: str) -> Iterator[psycopg.Connection]:
    """Runtime LOGIN with default tuple rows for schema/history introspection."""
    if not str(dsn).strip():
        raise ValueError("PostgreSQL DSN is required")
    with psycopg.connect(str(dsn)) as conn:
        _validate_runtime_identity(conn)
        yield conn
