"""Internal PostgreSQL audit evidence writer (AP-028 M7).

Not part of the public ``modules.usermanagement.api`` surface.
Runtime may INSERT only; callers must never SELECT through the runtime role.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

import psycopg
from psycopg.errors import UniqueViolation

from .errors import AuditUnavailableError

SYSTEM_ACTOR_SESSION_EXPIRY = "qmtool.session-expiry"

EVENT_LOGIN_SUCCEEDED = "auth.login.succeeded"
EVENT_LOGIN_DENIED = "auth.login.denied"
EVENT_LOGOUT_SUCCEEDED = "auth.logout.succeeded"
EVENT_LOGOUT_ALL_SUCCEEDED = "auth.logout_all.succeeded"
EVENT_SESSION_EXPIRED = "auth.session.expired"
EVENT_USER_CREATED = "user.created"
EVENT_USER_ACCESS_CHANGED = "user.access_changed"
EVENT_USER_PASSWORD_CHANGED = "user.password_changed"

RESULT_SUCCEEDED = "succeeded"
RESULT_DENIED = "denied"
RESULT_FAILED = "failed"

ACTOR_USER = "user"
ACTOR_SYSTEM = "system"
ACTOR_ANONYMOUS = "anonymous"

SOURCE_BACKEND = "backend"
CLIENT_BACKEND = "backend"

_AUDIT_INSERT_SQL = """
INSERT INTO usermanagement.audit_events (
    audit_id, event_type, occurred_at, result, reason_code,
    source, client_type, request_id,
    actor_kind, actor_user_id, actor_session_id, system_actor,
    target_user_id, target_session_id,
    affected_session_count, changed_fields,
    role_before, role_after,
    is_qmb_before, is_qmb_after,
    is_active_before, is_active_after,
    must_change_password_before, must_change_password_after
) VALUES (
    %s::uuid, %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s::uuid, %s::uuid, %s,
    %s::uuid, %s::uuid,
    %s, %s,
    %s, %s,
    %s, %s,
    %s, %s,
    %s, %s
)
"""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class AuditEventWrite:
    event_type: str
    result: str
    actor_kind: str
    source: str = SOURCE_BACKEND
    client_type: str = CLIENT_BACKEND
    occurred_at: datetime | None = None
    reason_code: str | None = None
    request_id: str | None = None
    actor_user_id: str | None = None
    actor_session_id: str | None = None
    system_actor: str | None = None
    target_user_id: str | None = None
    target_session_id: str | None = None
    affected_session_count: int | None = None
    changed_fields: Sequence[str] | None = None
    role_before: str | None = None
    role_after: str | None = None
    is_qmb_before: bool | None = None
    is_qmb_after: bool | None = None
    is_active_before: bool | None = None
    is_active_after: bool | None = None
    must_change_password_before: bool | None = None
    must_change_password_after: bool | None = None
    audit_id: str | None = None

    def validated_request_id(self) -> str:
        """Return the mandatory backend request id for one audit write."""
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise AuditUnavailableError("audit evidence unavailable")
        return self.request_id.strip()


class PostgresAuditRepository:
    """Append-only audit inserts on an existing runtime connection."""

    @staticmethod
    def insert_on_connection(
        conn: psycopg.Connection,
        event: AuditEventWrite,
        *,
        on_conflict_do_nothing: bool = False,
    ) -> bool:
        """Insert one audit row. Returns False when a conflict was skipped.

        Any insert failure is raised as ``AuditUnavailableError`` so callers
        can roll back the enclosing fachliche transaction.

        Expiry duplicates use UniqueViolation handling (not ``ON CONFLICT`` /
        ``RETURNING``) because those require SELECT, which runtime must not have.
        """
        try:
            audit_id = event.audit_id or str(uuid4())
            occurred_at = _as_utc(event.occurred_at or datetime.now(timezone.utc))
            changed = list(event.changed_fields) if event.changed_fields is not None else None
            params = (
                audit_id,
                event.event_type,
                occurred_at,
                event.result,
                event.reason_code,
                event.source,
                event.client_type,
                event.validated_request_id(),
                event.actor_kind,
                event.actor_user_id,
                event.actor_session_id,
                event.system_actor,
                event.target_user_id,
                event.target_session_id,
                event.affected_session_count,
                changed,
                event.role_before,
                event.role_after,
                event.is_qmb_before,
                event.is_qmb_after,
                event.is_active_before,
                event.is_active_after,
                event.must_change_password_before,
                event.must_change_password_after,
            )
            if on_conflict_do_nothing:
                # Nested transaction: UniqueViolation must not abort the outer fach TX.
                with conn.transaction():
                    cursor = conn.execute(_AUDIT_INSERT_SQL, params)
            else:
                cursor = conn.execute(_AUDIT_INSERT_SQL, params)
        except UniqueViolation:
            if on_conflict_do_nothing:
                return False
            raise AuditUnavailableError("audit evidence unavailable")
        except Exception as exc:  # noqa: BLE001 — any insert failure blocks the fach TX
            raise AuditUnavailableError("audit evidence unavailable") from exc
        return int(cursor.rowcount or 0) > 0
