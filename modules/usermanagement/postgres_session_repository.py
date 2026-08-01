"""PostgreSQL SessionRepository implementation for AP-028 M4."""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

from .contracts import SessionRecord
from .postgres_connection import runtime_connection
from .session_repository import SessionRepository


_SESSION_COLUMNS = """
    session_id::text AS session_id,
    token_hash,
    user_id::text AS user_id,
    created_at,
    last_seen_at,
    expires_at,
    client_type,
    authentication_level,
    revoked_at
"""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


def _session_from_row(row: dict[str, object]) -> SessionRecord:
    return SessionRecord(
        session_id=str(row["session_id"]),
        token_hash=str(row["token_hash"]),
        user_id=str(row["user_id"]),
        created_at=_as_utc(row["created_at"]),
        last_seen_at=_as_utc(row["last_seen_at"]),
        expires_at=_as_utc(row["expires_at"]),
        client_type=str(row["client_type"]),
        authentication_level=str(row["authentication_level"]),
        revoked_at=None if row["revoked_at"] is None else _as_utc(row["revoked_at"]),
    )


class PostgresSessionRepository(SessionRepository):
    """Opaque session persistence through the M3 runtime privilege contract."""

    def __init__(self, dsn: str) -> None:
        self._dsn = str(dsn)

    @staticmethod
    def _get_on_connection(
        conn: psycopg.Connection,
        session_id: str,
    ) -> SessionRecord | None:
        row = conn.execute(
            f"""
            SELECT {_SESSION_COLUMNS}
            FROM usermanagement.sessions
            WHERE session_id = %s::uuid
            """,
            (session_id,),
        ).fetchone()
        return None if row is None else _session_from_row(row)

    def add(self, session: SessionRecord) -> None:
        try:
            with runtime_connection(self._dsn) as conn:
                conn.execute(
                    """
                    INSERT INTO usermanagement.sessions (
                        session_id, token_hash, user_id, created_at, last_seen_at,
                        expires_at, client_type, authentication_level, revoked_at
                    )
                    VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session.session_id,
                        session.token_hash,
                        session.user_id,
                        _as_utc(session.created_at),
                        _as_utc(session.last_seen_at),
                        _as_utc(session.expires_at),
                        session.client_type,
                        session.authentication_level,
                        None if session.revoked_at is None else _as_utc(session.revoked_at),
                    ),
                )
        except UniqueViolation as exc:
            raise ValueError("session_id or token_hash already exists") from exc
        except ForeignKeyViolation as exc:
            raise ValueError("session user does not exist") from exc
        except CheckViolation as exc:
            raise ValueError("session violates PostgreSQL constraints") from exc

    def get_by_token_hash(self, token_hash: str) -> SessionRecord | None:
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                f"""
                SELECT {_SESSION_COLUMNS}
                FROM usermanagement.sessions
                WHERE token_hash = %s
                """,
                (token_hash,),
            ).fetchone()
        return None if row is None else _session_from_row(row)

    def get_by_session_id(self, session_id: str) -> SessionRecord | None:
        with runtime_connection(self._dsn) as conn:
            return self._get_on_connection(conn, session_id)

    def list_for_user(self, user_id: str) -> list[SessionRecord]:
        with runtime_connection(self._dsn) as conn:
            rows = conn.execute(
                f"""
                SELECT {_SESSION_COLUMNS}
                FROM usermanagement.sessions
                WHERE user_id = %s::uuid
                ORDER BY created_at, session_id
                """,
                (user_id,),
            ).fetchall()
        return [_session_from_row(row) for row in rows]

    def touch(self, session_id: str, last_seen_at: datetime) -> SessionRecord | None:
        moment = _as_utc(last_seen_at)
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                f"""
                UPDATE usermanagement.sessions
                SET last_seen_at = GREATEST(last_seen_at, %s)
                WHERE session_id = %s::uuid
                  AND revoked_at IS NULL
                RETURNING {_SESSION_COLUMNS}
                """,
                (moment, session_id),
            ).fetchone()
            if row is not None:
                return _session_from_row(row)
            return self._get_on_connection(conn, session_id)

    def revoke(self, session_id: str, revoked_at: datetime) -> SessionRecord | None:
        moment = _as_utc(revoked_at)
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                f"""
                UPDATE usermanagement.sessions
                SET revoked_at = %s
                WHERE session_id = %s::uuid
                  AND revoked_at IS NULL
                RETURNING {_SESSION_COLUMNS}
                """,
                (moment, session_id),
            ).fetchone()
            if row is not None:
                return _session_from_row(row)
            return self._get_on_connection(conn, session_id)

    def revoke_all_for_user(self, user_id: str, revoked_at: datetime) -> list[SessionRecord]:
        moment = _as_utc(revoked_at)
        with runtime_connection(self._dsn) as conn:
            return self.revoke_all_for_user_on_connection(conn, user_id, moment)

    def revoke_other_sessions_for_user(
        self,
        user_id: str,
        keep_session_id: str,
        revoked_at: datetime,
    ) -> list[SessionRecord]:
        moment = _as_utc(revoked_at)
        with runtime_connection(self._dsn) as conn:
            return self.revoke_other_sessions_for_user_on_connection(
                conn, user_id, keep_session_id, moment
            )

    @staticmethod
    def revoke_all_for_user_on_connection(
        conn: psycopg.Connection,
        user_id: str,
        revoked_at: datetime,
    ) -> list[SessionRecord]:
        moment = _as_utc(revoked_at)
        rows = conn.execute(
            f"""
            UPDATE usermanagement.sessions
            SET revoked_at = %s
            WHERE user_id = %s::uuid
              AND revoked_at IS NULL
            RETURNING {_SESSION_COLUMNS}
            """,
            (moment, user_id),
        ).fetchall()
        return sorted(
            (_session_from_row(row) for row in rows),
            key=lambda session: (session.created_at, session.session_id),
        )

    @staticmethod
    def revoke_other_sessions_for_user_on_connection(
        conn: psycopg.Connection,
        user_id: str,
        keep_session_id: str,
        revoked_at: datetime,
    ) -> list[SessionRecord]:
        moment = _as_utc(revoked_at)
        rows = conn.execute(
            f"""
            UPDATE usermanagement.sessions
            SET revoked_at = %s
            WHERE user_id = %s::uuid
              AND revoked_at IS NULL
              AND session_id <> %s::uuid
            RETURNING {_SESSION_COLUMNS}
            """,
            (moment, user_id, keep_session_id),
        ).fetchall()
        return sorted(
            (_session_from_row(row) for row in rows),
            key=lambda session: (session.created_at, session.session_id),
        )

    def delete(self, session_id: str) -> None:
        with runtime_connection(self._dsn) as conn:
            conn.execute(
                "DELETE FROM usermanagement.sessions WHERE session_id = %s::uuid",
                (session_id,),
            )
