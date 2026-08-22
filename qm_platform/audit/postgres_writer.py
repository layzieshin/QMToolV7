"""Append-only platform audit writer for PostgreSQL (AP-029 PG00-C).

Not a public module API surface for fachliche callers; modules should emit audit
through their service layer using this contract when wired to PostgreSQL.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg

from qm_platform.organization.server_context import resolve_active_organization_id

from .redaction import redact_audit_details

ACTOR_USER = "user"
ACTOR_SYSTEM = "system"
ACTOR_ANONYMOUS = "anonymous"

RESULT_SUCCEEDED = "succeeded"
RESULT_DENIED = "denied"
RESULT_FAILED = "failed"


class PlatformAuditWriteError(RuntimeError):
    """Raised when a platform audit row cannot be written safely."""


_AUDIT_INSERT_SQL = """
INSERT INTO platform.audit_events (
    audit_id, organization_id, occurred_at, request_id, correlation_id,
    actor_kind, actor_user_id, actor_label,
    action, object_type, object_id, result, reason_code, details_json
) VALUES (
    %s::uuid, %s, %s, %s, %s,
    %s, %s::uuid, %s,
    %s, %s, %s, %s, %s, %s::jsonb
)
"""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


def _json_details(details: Any) -> str | None:
    if details is None:
        return None
    redacted = redact_audit_details(details)
    return json.dumps(redacted, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class PlatformAuditEventWrite:
    action: str
    object_type: str
    object_id: str
    result: str
    actor_kind: str
    request_id: str
    organization_id: str | None = None
    correlation_id: str | None = None
    occurred_at: datetime | None = None
    reason_code: str | None = None
    actor_user_id: str | None = None
    actor_label: str | None = None
    details: Any = None
    audit_id: str | None = None

    def validated_request_id(self) -> str:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise PlatformAuditWriteError("platform audit request_id is required")
        return self.request_id.strip()

    def resolved_organization_id(self) -> str:
        if self.organization_id is not None and str(self.organization_id).strip():
            return resolve_active_organization_id(
                client_organization_id=str(self.organization_id).strip()
            )
        return resolve_active_organization_id()


class PlatformAuditWriter:
    """Append-only audit inserts on an existing runtime connection."""

    @staticmethod
    def insert_on_connection(
        conn: psycopg.Connection,
        event: PlatformAuditEventWrite,
    ) -> str:
        """Insert one audit row and return its audit_id."""
        try:
            audit_id = event.audit_id or str(uuid4())
            occurred_at = _as_utc(event.occurred_at or datetime.now(timezone.utc))
            details_json = _json_details(event.details)
            params = (
                audit_id,
                event.resolved_organization_id(),
                occurred_at,
                event.validated_request_id(),
                event.correlation_id,
                event.actor_kind,
                event.actor_user_id,
                event.actor_label,
                event.action,
                event.object_type,
                event.object_id,
                event.result,
                event.reason_code,
                details_json,
            )
            cursor = conn.execute(_AUDIT_INSERT_SQL, params)
        except PlatformAuditWriteError:
            raise
        except Exception as exc:  # noqa: BLE001 — any insert failure blocks the caller TX
            raise PlatformAuditWriteError("platform audit evidence unavailable") from exc
        if int(cursor.rowcount or 0) <= 0:
            raise PlatformAuditWriteError("platform audit evidence unavailable")
        return audit_id
