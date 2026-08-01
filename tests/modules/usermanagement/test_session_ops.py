"""AP-028 Milestone 2: repository-independent opaque session lifecycle."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from modules.usermanagement.api import (
    ExpiredSessionError,
    InactiveUserError,
    InvalidSessionError,
    IssuedSession,
    PasswordChangeRequiredError,
    RevokedSessionError,
    SessionNotFoundError,
    is_effective_qmb,
)
from modules.usermanagement.contracts import AuthenticatedUser
from modules.usermanagement.memory_session_repository import InMemorySessionRepository
from modules.usermanagement.session_ops import MappingUserByIdLookup, SessionOps
from modules.usermanagement.session_token import hash_session_token
from modules.usermanagement.service import UserManagementService


def _utc(hour: int = 10, minute: int = 0) -> datetime:
    return datetime(2026, 7, 31, hour, minute, tzinfo=timezone.utc)


def _user(
    *,
    user_id: str = "u-1",
    username: str = "alice",
    role: str = "User",
    is_active: bool = True,
    is_qmb: bool = False,
    must_change_password: bool = False,
) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        username=username,
        role=role,
        is_active=is_active,
        is_qmb=is_qmb,
        must_change_password=must_change_password,
    )


def _ops(user: AuthenticatedUser | None = None) -> tuple[SessionOps, MappingUserByIdLookup, InMemorySessionRepository]:
    users = MappingUserByIdLookup()
    if user is not None:
        users.put(user)
    repo = InMemorySessionRepository()
    return SessionOps(repo, users), users, repo


def test_create_session_stores_hash_only_and_returns_raw_token() -> None:
    user = _user()
    ops, _users, repo = _ops(user)
    issued = ops.create_session(user, client_type="test", now=_utc())
    assert isinstance(issued, IssuedSession)
    assert issued.raw_token
    assert issued.session.token_hash == hash_session_token(issued.raw_token)
    stored = repo.get_by_session_id(issued.session.session_id)
    assert stored is not None
    assert stored.token_hash == issued.session.token_hash
    assert "raw_token" not in stored.__dataclass_fields__
    assert "token" not in stored.__dataclass_fields__


def test_resolve_session_returns_confirmed_context_with_current_roles() -> None:
    user = _user(role="Admin", is_qmb=False)
    ops, users, _repo = _ops(user)
    issued = ops.create_session(user, client_type="test", now=_utc())
    ctx = ops.resolve_session(issued.raw_token, request_id="req-1", now=_utc(hour=11))
    assert ctx.is_confirmed is True
    assert ctx.user_id == "u-1"
    assert ctx.session_id == issued.session.session_id
    assert ctx.request_id == "req-1"
    assert ctx.global_roles == frozenset({"ADMIN"})
    assert ctx.is_qmb is False
    assert is_effective_qmb(user) is False

    users.put(_user(role="User", is_qmb=True))
    ctx2 = ops.resolve_session(issued.raw_token, request_id="req-2", now=_utc(hour=11, minute=1))
    assert ctx2.global_roles == frozenset({"USER"})
    assert ctx2.is_qmb is True


def test_resolve_rejects_missing_invalid_expired_revoked_and_inactive() -> None:
    user = _user()
    ops, users, _repo = _ops(user)
    issued = ops.create_session(
        user,
        client_type="test",
        now=_utc(),
        lifetime=timedelta(minutes=30),
    )

    with pytest.raises(InvalidSessionError):
        ops.resolve_session(None, request_id="r")
    with pytest.raises(InvalidSessionError):
        ops.resolve_session("   ", request_id="r")
    with pytest.raises(SessionNotFoundError):
        ops.resolve_session("not-a-real-token", request_id="r")

    with pytest.raises(ExpiredSessionError):
        ops.resolve_session(issued.raw_token, request_id="r", now=_utc(hour=12))

    issued2 = ops.create_session(user, client_type="test", now=_utc())
    ops.revoke_session(raw_token=issued2.raw_token, now=_utc(hour=10, minute=5))
    with pytest.raises(RevokedSessionError):
        ops.resolve_session(issued2.raw_token, request_id="r", now=_utc(hour=10, minute=6))
    # Idempotent revoke of already-revoked token (M5 logout contract)
    again = ops.revoke_session(raw_token=issued2.raw_token, now=_utc(hour=10, minute=7))
    assert again.revoked_at is not None

    issued3 = ops.create_session(user, client_type="test", now=_utc())
    users.put(_user(is_active=False))
    with pytest.raises(InactiveUserError):
        ops.resolve_session(issued3.raw_token, request_id="r", now=_utc(hour=10, minute=1))


def test_inactive_user_cannot_create_session() -> None:
    ops, _users, _repo = _ops(_user(is_active=False))
    with pytest.raises(InactiveUserError):
        ops.create_session(_user(is_active=False), client_type="test", now=_utc())


def test_nonpositive_lifetime_is_rejected() -> None:
    user = _user()
    ops, _users, _repo = _ops(user)
    with pytest.raises(ValueError, match="lifetime must be positive"):
        ops.create_session(user, client_type="test", now=_utc(), lifetime=timedelta(0))
    with pytest.raises(ValueError, match="lifetime must be positive"):
        ops.create_session(user, client_type="test", now=_utc(), lifetime=timedelta(seconds=-1))


def test_session_repository_port_requires_list_for_user() -> None:
    from modules.usermanagement.session_repository import SessionRepository

    assert "list_for_user" in SessionRepository.__abstractmethods__
    assert "touch" in SessionRepository.__abstractmethods__
    assert "revoke" in SessionRepository.__abstractmethods__
    assert "revoke_all_for_user" in SessionRepository.__abstractmethods__

    class IncompleteRepository(SessionRepository):
        def add(self, session):  # type: ignore[override]
            pass

        def get_by_token_hash(self, token_hash):  # type: ignore[override]
            return None

        def get_by_session_id(self, session_id):  # type: ignore[override]
            return None

        def touch(self, session_id, last_seen_at):  # type: ignore[override]
            return None

        def revoke(self, session_id, revoked_at):  # type: ignore[override]
            return None

        def revoke_all_for_user(self, user_id, revoked_at):  # type: ignore[override]
            return []

        def delete(self, session_id):  # type: ignore[override]
            pass

    with pytest.raises(TypeError):
        IncompleteRepository()  # type: ignore[abstract]


def test_must_change_password_blocks_resolve_unless_allowed() -> None:
    user = _user(must_change_password=True)
    ops, _users, _repo = _ops(user)
    issued = ops.create_session(user, client_type="test", now=_utc())
    with pytest.raises(PasswordChangeRequiredError):
        ops.resolve_session(issued.raw_token, request_id="r", now=_utc(hour=10, minute=1))
    ctx = ops.resolve_session(
        issued.raw_token,
        request_id="r",
        now=_utc(hour=10, minute=1),
        password_change_allowed=True,
    )
    assert ctx.is_confirmed is True


def test_client_cannot_inject_foreign_identity_via_resolve() -> None:
    alice = _user(user_id="alice", username="alice", role="User")
    ops, _users, _repo = _ops(alice)
    issued = ops.create_session(alice, client_type="test", now=_utc())
    ctx = ops.resolve_session(issued.raw_token, request_id="r", now=_utc(hour=10, minute=1))
    assert ctx.user_id == "alice"
    assert ctx.global_roles == frozenset({"USER"})
    assert ctx.is_qmb is False


def test_revoke_all_for_user_blocks_existing_sessions() -> None:
    user = _user()
    ops, _users, _repo = _ops(user)
    first = ops.create_session(user, client_type="cli", now=_utc())
    second = ops.create_session(user, client_type="pyqt", now=_utc())
    revoked = ops.revoke_all_for_user(user.user_id, now=_utc(hour=10, minute=5))
    assert len(revoked) == 2
    with pytest.raises(RevokedSessionError):
        ops.resolve_session(first.raw_token, request_id="r", now=_utc(hour=10, minute=6))
    with pytest.raises(RevokedSessionError):
        ops.resolve_session(second.raw_token, request_id="r", now=_utc(hour=10, minute=6))


@pytest.mark.parametrize("touch", [True, False])
def test_touch_cannot_overwrite_a_concurrent_revocation(touch: bool) -> None:
    class RevokeBeforeTouchRepository(InMemorySessionRepository):
        def touch(self, session_id, last_seen_at):  # type: ignore[override]
            self.revoke(session_id, last_seen_at)
            return super().touch(session_id, last_seen_at)

    user = _user()
    users = MappingUserByIdLookup({user.user_id: user})
    repo = RevokeBeforeTouchRepository()
    ops = SessionOps(repo, users)
    issued = ops.create_session(user, client_type="test", now=_utc())

    with pytest.raises(RevokedSessionError):
        ops.resolve_session(
            issued.raw_token,
            request_id="r",
            now=_utc(hour=10, minute=1),
            touch=touch,
        )
    stored = repo.get_by_session_id(issued.session.session_id)
    assert stored is not None
    expected_revoked_at = _utc(hour=10, minute=1) if touch else _utc()
    assert stored.revoked_at == expected_revoked_at


def test_revoke_requires_exactly_one_session_identifier() -> None:
    user = _user()
    ops, _users, _repo = _ops(user)
    issued = ops.create_session(user, client_type="test", now=_utc())

    with pytest.raises(InvalidSessionError, match="exactly one"):
        ops.revoke_session()
    with pytest.raises(InvalidSessionError, match="exactly one"):
        ops.revoke_session(session_id=issued.session.session_id, raw_token=issued.raw_token)


def test_service_delegates_opaque_sessions_when_repository_configured() -> None:
    user = _user(user_id="alice", username="alice")
    service = UserManagementService(
        session_repository=InMemorySessionRepository(),
        _users={user.user_id: ("unused", user.role)},
    )
    issued = service.create_session(user, client_type="test", now=_utc())
    ctx = service.resolve_session(issued.raw_token, request_id="req-svc", now=_utc(hour=10, minute=1))
    assert ctx.user_id == user.user_id
    assert ctx.is_confirmed is True
    service.revoke_session(raw_token=issued.raw_token, now=_utc(hour=10, minute=2))
    with pytest.raises(RevokedSessionError):
        service.resolve_session(issued.raw_token, request_id="req-svc", now=_utc(hour=10, minute=3))


def test_service_requires_session_repository_for_opaque_sessions() -> None:
    service = UserManagementService()
    with pytest.raises(RuntimeError, match="opaque session repository is not configured"):
        service.create_session(_user(), client_type="test", now=_utc())


def test_issued_session_exported_from_public_api() -> None:
    from modules.usermanagement import api as public_api

    assert "IssuedSession" in public_api.__all__
    assert public_api.IssuedSession is IssuedSession
