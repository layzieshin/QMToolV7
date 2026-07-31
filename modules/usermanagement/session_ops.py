"""Opaque server-side session lifecycle (AP-028 Milestone 2).

This is the authoritative multiuser session path. The JSON ``SessionStore`` remains
a desktop/legacy current-user file and must not be used as backend session truth.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

from .contracts import AuthenticatedUser, IssuedSession, SessionRecord, UserContext, issue_user_context
from .errors import (
    ExpiredSessionError,
    InactiveUserError,
    InvalidSessionError,
    PasswordChangeRequiredError,
    RevokedSessionError,
    SessionNotFoundError,
)
from .role_policies import is_effective_qmb, normalize_base_role
from .session_repository import SessionRepository
from .session_token import generate_session_token, hash_session_token

DEFAULT_SESSION_LIFETIME = timedelta(hours=12)


class UserByIdLookup(Protocol):
    def get_user_by_id(self, user_id: str) -> AuthenticatedUser | None:
        """Load current user state by stable user_id."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionOps:
    """Create, resolve, and revoke opaque sessions without freezing roles."""

    def __init__(
        self,
        session_repository: SessionRepository,
        users: UserByIdLookup,
        *,
        default_lifetime: timedelta = DEFAULT_SESSION_LIFETIME,
    ) -> None:
        self._sessions = session_repository
        self._users = users
        self._default_lifetime = default_lifetime

    def create_session(
        self,
        user: AuthenticatedUser,
        *,
        client_type: str,
        lifetime: timedelta | None = None,
        now: datetime | None = None,
        authentication_level: str = "password",
    ) -> IssuedSession:
        if not user.is_active:
            raise InactiveUserError("inactive user cannot obtain a session")
        if not client_type:
            raise ValueError("client_type is required")
        moment = _as_utc(now or _utc_now())
        ttl = lifetime if lifetime is not None else self._default_lifetime
        if ttl <= timedelta(0):
            raise ValueError("session lifetime must be positive")
        raw_token = generate_session_token()
        record = SessionRecord(
            session_id=str(uuid4()),
            token_hash=hash_session_token(raw_token),
            user_id=user.user_id,
            created_at=moment,
            last_seen_at=moment,
            expires_at=moment + ttl,
            client_type=str(client_type),
            authentication_level=str(authentication_level),
            revoked_at=None,
        )
        self._sessions.add(record)
        return IssuedSession(raw_token=raw_token, session=record)

    def resolve_session(
        self,
        raw_token: str | None,
        *,
        request_id: str,
        now: datetime | None = None,
        password_change_allowed: bool = False,
        touch: bool = True,
    ) -> UserContext:
        """Resolve a raw opaque token into a confirmed ``UserContext``.

        ``must_change_password`` policy (M2 default): block resolution unless
        ``password_change_allowed=True``. M5 handover: only the dedicated
        change-password transport path may set this flag; it must never be
        client-controlled or used by other endpoints.
        Roles and ``is_qmb`` are loaded from the current user record, not the session.
        """
        if raw_token is None or not str(raw_token).strip():
            raise InvalidSessionError("session token is missing")
        if not request_id:
            raise ValueError("request_id is required")

        token_hash = hash_session_token(str(raw_token))
        session = self._sessions.get_by_token_hash(token_hash)
        if session is None:
            raise SessionNotFoundError("session not found")

        moment = _as_utc(now or _utc_now())
        if session.revoked_at is not None:
            raise RevokedSessionError("session has been revoked")
        if moment >= session.expires_at:
            raise ExpiredSessionError("session has expired")

        user = self._users.get_user_by_id(session.user_id)
        if user is None:
            raise SessionNotFoundError("session user no longer exists")
        if not user.is_active:
            raise InactiveUserError("user is inactive")
        if user.must_change_password and not password_change_allowed:
            raise PasswordChangeRequiredError("password change required")

        last_seen_at = moment if touch else session.last_seen_at
        session = self._sessions.touch(session.session_id, last_seen_at)
        if session is None:
            raise SessionNotFoundError("session not found")
        if session.revoked_at is not None:
            raise RevokedSessionError("session has been revoked")
        if moment >= session.expires_at:
            raise ExpiredSessionError("session has expired")

        role = normalize_base_role(user.role)
        return issue_user_context(
            user_id=user.user_id,
            session_id=session.session_id,
            request_id=str(request_id),
            username=user.username,
            global_roles={role} if role else set(),
            is_qmb=is_effective_qmb(user),
            authenticated_at=session.created_at,
        )

    def revoke_session(
        self,
        *,
        session_id: str | None = None,
        raw_token: str | None = None,
        now: datetime | None = None,
    ) -> SessionRecord:
        session = self._load_for_revoke(session_id=session_id, raw_token=raw_token)
        moment = _as_utc(now or _utc_now())
        revoked = self._sessions.revoke(session.session_id, moment)
        if revoked is None:
            raise SessionNotFoundError("session not found")
        return revoked

    def revoke_all_for_user(self, user_id: str, *, now: datetime | None = None) -> list[SessionRecord]:
        if not user_id:
            raise ValueError("user_id is required")
        moment = _as_utc(now or _utc_now())
        return self._sessions.revoke_all_for_user(user_id, moment)

    def _load_for_revoke(
        self,
        *,
        session_id: str | None,
        raw_token: str | None,
    ) -> SessionRecord:
        if bool(session_id) == bool(raw_token):
            raise InvalidSessionError("exactly one of session_id or raw_token is required to revoke")
        if session_id:
            session = self._sessions.get_by_session_id(session_id)
        else:
            assert raw_token is not None
            session = self._sessions.get_by_token_hash(hash_session_token(raw_token))
        if session is None:
            raise SessionNotFoundError("session not found")
        return session


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


class MappingUserByIdLookup:
    """Simple in-memory user lookup for tests and non-SQLite wiring."""

    def __init__(self, users: dict[str, AuthenticatedUser] | None = None) -> None:
        self._users = dict(users or {})

    def put(self, user: AuthenticatedUser) -> None:
        self._users[user.user_id] = user

    def get_user_by_id(self, user_id: str) -> AuthenticatedUser | None:
        return self._users.get(user_id)
