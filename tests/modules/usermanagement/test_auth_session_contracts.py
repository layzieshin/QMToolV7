"""AP-028 Milestone 1: public identity and session contracts."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from modules.usermanagement.api import (
    AuthenticationError,
    ExpiredSessionError,
    InactiveUserError,
    InvalidSessionError,
    PasswordChangeRequiredError,
    RevokedSessionError,
    SessionError,
    SessionNotFoundError,
    SessionRecord,
    SystemExecutionContext,
    UserContext,
    UsermanagementError,
)
from modules.usermanagement.contracts import (
    issue_system_execution_context,
    issue_user_context,
)
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID


def _utc(year: int = 2026, month: int = 7, day: int = 31, hour: int = 10) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)


def test_issue_user_context_is_confirmed_immutable_and_publicly_importable() -> None:
    ctx = issue_user_context(
        user_id="u-1",
        session_id="s-1",
        request_id="r-1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
        username="alice",
        global_roles={"USER", "user"},
        is_qmb=False,
        authenticated_at=_utc(),
    )
    assert isinstance(ctx, UserContext)
    assert ctx.is_confirmed is True
    assert ctx.user_id == "u-1"
    assert ctx.session_id == "s-1"
    assert ctx.request_id == "r-1"
    assert ctx.organization_id == INSTALLATION_ORGANIZATION_ID
    assert ctx.username == "alice"
    assert ctx.global_roles == frozenset({"USER", "user"})
    assert ctx.is_qmb is False
    assert ctx.authenticated_at == _utc()
    assert ctx.authenticated_at.tzinfo is not None
    with pytest.raises(FrozenInstanceError):
        ctx.username = "bob"  # type: ignore[misc]


def test_issue_user_context_rejects_non_server_organization_id() -> None:
    with pytest.raises(ValueError, match="server-confirmed installation organization"):
        issue_user_context(
            user_id="u-1",
            session_id="s-1",
            request_id="r-1",
            organization_id="00000000-0000-4000-8000-000000000099",
            username="alice",
            global_roles=["USER"],
            is_qmb=False,
            authenticated_at=_utc(),
        )


def test_direct_user_context_construction_is_not_confirmed() -> None:
    forged = UserContext(
        user_id="attacker",
        session_id="forged-session",
        request_id="forged-request",
        organization_id=INSTALLATION_ORGANIZATION_ID,
        username="attacker",
        global_roles=frozenset({"ADMIN"}),
        is_qmb=True,
        authenticated_at=_utc(),
    )
    assert forged.is_confirmed is False


def test_user_context_constructor_rejects_server_confirmed_keyword() -> None:
    with pytest.raises(TypeError):
        UserContext(
            user_id="attacker",
            session_id="forged-session",
            request_id="forged-request",
            organization_id=INSTALLATION_ORGANIZATION_ID,
            username="attacker",
            global_roles=frozenset({"ADMIN"}),
            is_qmb=True,
            authenticated_at=_utc(),
            _server_confirmed=True,  # type: ignore[call-arg]
        )


def test_issue_user_context_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        issue_user_context(
            user_id="u-1",
            session_id="s-1",
            request_id="r-1",
            organization_id=INSTALLATION_ORGANIZATION_ID,
            username="alice",
            global_roles=["USER"],
            is_qmb=False,
            authenticated_at=datetime(2026, 7, 31, 10, 0, 0),
        )


def test_issue_system_execution_context_is_confirmed_and_rejects_bare_fallback() -> None:
    ctx = issue_system_execution_context(
        system_actor="usermanagement.session-cleanup",
        request_id="r-sys-1",
    )
    assert isinstance(ctx, SystemExecutionContext)
    assert ctx.is_confirmed is True
    assert ctx.system_actor == "usermanagement.session-cleanup"
    assert ctx.organization_id == INSTALLATION_ORGANIZATION_ID
    with pytest.raises(FrozenInstanceError):
        ctx.system_actor = "other"  # type: ignore[misc]
    with pytest.raises(ValueError, match="explicit named system actor"):
        issue_system_execution_context(system_actor="system", request_id="r-1")
    with pytest.raises(ValueError, match="explicit named system actor"):
        issue_system_execution_context(system_actor="unknown", request_id="r-1")


def test_direct_system_context_construction_is_not_confirmed() -> None:
    forged = SystemExecutionContext(
        system_actor="usermanagement.session-cleanup",
        request_id="r-1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
    )
    assert forged.is_confirmed is False


def test_system_context_constructor_rejects_server_confirmed_keyword() -> None:
    with pytest.raises(TypeError):
        SystemExecutionContext(
            system_actor="usermanagement.session-cleanup",
            request_id="r-1",
            organization_id=INSTALLATION_ORGANIZATION_ID,
            _server_confirmed=True,  # type: ignore[call-arg]
        )


def test_session_record_has_hash_not_plaintext_token_field() -> None:
    record = SessionRecord(
        session_id="s-1",
        token_hash="abc123hash",
        user_id="u-1",
        created_at=_utc(),
        last_seen_at=_utc(),
        expires_at=_utc(hour=12),
        client_type="backend",
        authentication_level="password",
        revoked_at=None,
    )
    assert record.token_hash == "abc123hash"
    assert not hasattr(record, "token")
    assert "token" not in record.__dataclass_fields__
    assert "token_hash" in record.__dataclass_fields__
    with pytest.raises(FrozenInstanceError):
        record.user_id = "other"  # type: ignore[misc]


def test_error_hierarchy_distinguishes_auth_session_and_inactive() -> None:
    assert issubclass(AuthenticationError, UsermanagementError)
    assert issubclass(InactiveUserError, UsermanagementError)
    assert issubclass(PasswordChangeRequiredError, UsermanagementError)
    assert issubclass(SessionError, UsermanagementError)
    assert issubclass(SessionNotFoundError, SessionError)
    assert issubclass(InvalidSessionError, SessionError)
    assert issubclass(ExpiredSessionError, SessionError)
    assert issubclass(RevokedSessionError, SessionError)
    assert not issubclass(InactiveUserError, SessionError)
    assert not issubclass(AuthenticationError, SessionError)


def test_public_api_exports_do_not_require_internal_imports() -> None:
    import modules.usermanagement.api as api

    for name in (
        "UserContext",
        "SystemExecutionContext",
        "SessionRecord",
        "UsermanagementError",
        "AuthenticationError",
        "InactiveUserError",
        "PasswordChangeRequiredError",
        "SessionError",
        "SessionNotFoundError",
        "InvalidSessionError",
        "ExpiredSessionError",
        "RevokedSessionError",
    ):
        assert name in api.__all__
        assert hasattr(api, name)

    assert "issue_user_context" not in api.__all__
    assert "issue_system_execution_context" not in api.__all__
    assert not hasattr(api, "issue_user_context")
    assert not hasattr(api, "issue_system_execution_context")
