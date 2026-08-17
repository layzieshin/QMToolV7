"""Hotspot: Documents/Home actor identity follows backend session after login."""
from __future__ import annotations

from interfaces.clients.backend_identity import BackendIdentityAdapter
from interfaces.clients.backend_session import BackendSessionApi, BackendSessionUser
from interfaces.clients.documents_http import (
    bind_pyqt_session_token_provider,
    clear_pyqt_session_token_provider,
    resolve_session_token,
)


def test_documents_bearer_matches_session_and_adapter_user() -> None:
    session = BackendSessionApi.__new__(BackendSessionApi)
    session._token = "session-token-abc"
    session._user = BackendSessionUser(
        user_id="uid-1",
        session_id="sid-1",
        username="bob",
        role="USER",
        global_roles=("USER",),
        is_qmb=False,
        authenticated_at="2026-01-01T00:00:00+00:00",
    )
    session._transport = None  # type: ignore[assignment]

    adapter = BackendIdentityAdapter(session, transport=None)  # type: ignore[arg-type]
    # Override transport unused for get_current_user
    clear_pyqt_session_token_provider()
    bind_pyqt_session_token_provider(session.bearer_token)
    try:
        assert adapter.get_current_user() is session.current_user()
        assert adapter.get_current_user().user_id == "uid-1"
        assert resolve_session_token() == "session-token-abc"
    finally:
        clear_pyqt_session_token_provider()


def test_adapter_logout_clears_session_and_token_provider() -> None:
    session = BackendSessionApi.__new__(BackendSessionApi)
    session._token = "tok"
    session._user = BackendSessionUser(
        user_id="u",
        session_id="s",
        username="bob",
        role="USER",
        global_roles=("USER",),
        is_qmb=False,
        authenticated_at="2026-01-01T00:00:00+00:00",
    )

    def _logout() -> None:
        session.clear()

    session.logout = _logout  # type: ignore[method-assign]
    adapter = BackendIdentityAdapter.__new__(BackendIdentityAdapter)
    adapter._session = session
    adapter._transport = None
    clear_pyqt_session_token_provider()
    bind_pyqt_session_token_provider(session.bearer_token)
    adapter.logout()
    assert session.current_user() is None
    assert session.bearer_token() is None
    clear_pyqt_session_token_provider()
