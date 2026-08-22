"""Usermanagement public DTOs and context contracts (AP-028 Milestone 1).

Concept separation (do not conflate):

- authenticated user: identity proven by a valid session
- effective user: identity in whose name a use case runs (normally same as authenticated)
- actor: identity recorded in audit as the acting party (derived from confirmed context)
- target user: user affected by an admin action (never an actor fallback)
- system actor: explicit non-human actor for true system actions only

``UserContext`` and ``SystemExecutionContext`` are only *confirmed* when created via
``issue_user_context`` / ``issue_system_execution_context``. Direct dataclass
construction is possible for tests/fixtures but must not be treated as
server-confirmed authorization input.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from qm_platform.organization.server_context import resolve_active_organization_id


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    username: str
    role: str
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    email: str | None = None
    department: str | None = None
    scope: str | None = None
    organization_unit: str | None = None
    is_active: bool = True
    is_qmb: bool = False
    must_change_password: bool = False


@dataclass(frozen=True)
class UserContext:
    """Confirmed identity context for a backend-authenticated request.

    Carries identity and global role *references* only. It does not decide
    module-specific authorization. No plaintext session token.
    """

    user_id: str
    session_id: str
    request_id: str
    organization_id: str
    username: str
    global_roles: frozenset[str]
    is_qmb: bool
    authenticated_at: datetime
    _server_confirmed: bool = field(default=False, init=False, repr=False, compare=False)

    @property
    def is_confirmed(self) -> bool:
        return self._server_confirmed


@dataclass(frozen=True)
class SystemExecutionContext:
    """Explicit non-human execution context for true system actions only."""

    system_actor: str
    request_id: str
    organization_id: str
    _server_confirmed: bool = field(default=False, init=False, repr=False, compare=False)

    @property
    def is_confirmed(self) -> bool:
        return self._server_confirmed


@dataclass(frozen=True)
class SessionRecord:
    """Server-side session metadata. Stores ``token_hash`` only — never a plaintext token."""

    session_id: str
    token_hash: str
    user_id: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    client_type: str
    authentication_level: str = "password"
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class IssuedSession:
    """One-time return of a newly created opaque session.

    ``raw_token`` is returned to the client only at creation time and must never be persisted.
    """

    raw_token: str
    session: SessionRecord


def _require_aware_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware (UTC)")
    return value.astimezone(timezone.utc)


def _as_frozenset(roles: Iterable[str]) -> frozenset[str]:
    return frozenset(str(role) for role in roles)


def issue_user_context(
    *,
    user_id: str,
    session_id: str,
    request_id: str,
    organization_id: str,
    username: str,
    global_roles: Iterable[str],
    is_qmb: bool,
    authenticated_at: datetime,
) -> UserContext:
    """Server-side factory for a confirmed ``UserContext``.

    Callers outside the usermanagement service layer must not invent contexts;
    only session resolution (later milestones) should issue them.
    """
    if not user_id or not session_id or not request_id or not username:
        raise ValueError("user_id, session_id, request_id, and username are required")
    if not str(organization_id).strip():
        raise ValueError("organization_id is required")
    resolved_org = resolve_active_organization_id()
    if str(organization_id).strip() != resolved_org:
        raise ValueError("organization_id must match the server-confirmed installation organization")
    context = UserContext(
        user_id=str(user_id),
        session_id=str(session_id),
        request_id=str(request_id),
        organization_id=resolved_org,
        username=str(username),
        global_roles=_as_frozenset(global_roles),
        is_qmb=bool(is_qmb),
        authenticated_at=_require_aware_utc(authenticated_at, "authenticated_at"),
    )
    object.__setattr__(context, "_server_confirmed", True)
    return context


def issue_system_execution_context(*, system_actor: str, request_id: str) -> SystemExecutionContext:
    """Server-side factory for a confirmed ``SystemExecutionContext``."""
    if not system_actor or not request_id:
        raise ValueError("system_actor and request_id are required")
    if system_actor.strip().lower() in {"system", "unknown", ""}:
        raise ValueError("system_actor must be an explicit named system actor, not a bare fallback")
    context = SystemExecutionContext(
        system_actor=str(system_actor),
        request_id=str(request_id),
        organization_id=resolve_active_organization_id(),
    )
    object.__setattr__(context, "_server_confirmed", True)
    return context
