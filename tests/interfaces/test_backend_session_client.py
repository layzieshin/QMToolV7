"""J04-M0-P0: process-local backend_session_api against /auth/*."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from interfaces.clients.backend_session import BackendSessionApi, BackendSessionUser
from interfaces.clients.documents_http import (
    DocumentsBackendTransportError,
    bind_pyqt_session_token_provider,
    clear_pyqt_session_token_provider,
    resolve_session_token,
)
from interfaces.clients.http_transport import BackendHttpTransport, BackendTransportError
from tests.backend.test_auth_api import _build_test_container
from src.backend.api import create_app


class _TestClientTransport(BackendHttpTransport):
    """Maps BackendHttpTransport onto Starlette TestClient (no real sockets)."""

    def __init__(self, client: TestClient, *, token_provider) -> None:
        # Skip URL validation / urllib — TestClient owns the ASGI app.
        self._base_url = "http://testserver"
        self._token_provider = token_provider
        self._timeout_seconds = 30.0
        self._client = client

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        raw_body: bytes | None = None,
        content_type: str = "application/json",
        auth: bool = True,
        expect_json: bool = True,
    ) -> Any:
        headers: dict[str, str] = {}
        if auth:
            token = ""
            if self._token_provider is not None:
                token = (self._token_provider() or "").strip()
            if not token:
                raise BackendTransportError("backend session token is required", status_code=401)
            headers["Authorization"] = f"Bearer {token}"
        data = raw_body
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = content_type
        elif raw_body is not None:
            headers["Content-Type"] = content_type
        response = self._client.request(method, path, content=data, headers=headers)
        if response.status_code >= 400:
            detail = response.text
            raise BackendTransportError(
                f"backend HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
                body=detail,
            )
        if not expect_json:
            return response.content
        if not response.content:
            return None
        return response.json()


@pytest.fixture
def auth_app(tmp_path: Path) -> TestClient:
    container, _repo, _service = _build_test_container(tmp_path)
    return TestClient(create_app(container))


@pytest.fixture
def session_api(auth_app: TestClient) -> BackendSessionApi:
    api = BackendSessionApi.__new__(BackendSessionApi)
    api._token = None
    api._user = None
    api._transport = _TestClientTransport(auth_app, token_provider=api.bearer_token)
    return api


def test_two_sessions_are_independent(session_api: BackendSessionApi, auth_app: TestClient) -> None:
    other = BackendSessionApi.__new__(BackendSessionApi)
    other._token = None
    other._user = None
    other._transport = _TestClientTransport(auth_app, token_provider=other.bearer_token)

    bob = session_api.login("bob", "bob-secret")
    admin = other.login("admin", "admin")
    assert bob.username == "bob"
    assert admin.must_change_password is True
    assert session_api.bearer_token() != other.bearer_token()
    assert bob.user_id
    assert bob.session_id


def test_forced_password_change_then_me(session_api: BackendSessionApi) -> None:
    user = session_api.login("admin", "admin")
    assert user.must_change_password is True
    assert session_api.bearer_token()
    refreshed = session_api.change_password("adminpass01")
    assert refreshed.must_change_password is False
    assert refreshed.username == "admin"
    assert refreshed.user_id
    assert refreshed.session_id


def test_401_clears_session(session_api: BackendSessionApi) -> None:
    session_api.login("bob", "bob-secret")
    session_api._token = "definitely-invalid-token"
    with pytest.raises(BackendTransportError) as exc:
        session_api.refresh_me()
    assert exc.value.status_code == 401
    assert session_api.bearer_token() is None
    assert session_api.current_user() is None


def test_token_not_in_user_repr_or_str(session_api: BackendSessionApi) -> None:
    user = session_api.login("bob", "bob-secret")
    token = session_api.bearer_token()
    assert token
    assert token not in repr(user)
    assert token not in str(user)
    assert "token" not in BackendSessionUser.__dataclass_fields__


def test_pyqt_ignores_env_session_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMTOOL_SESSION_TOKEN", "env-must-be-ignored")
    clear_pyqt_session_token_provider()
    bind_pyqt_session_token_provider(lambda: None)
    try:
        with pytest.raises(DocumentsBackendTransportError) as exc:
            resolve_session_token()
        assert "ignored in PyQt" in str(exc.value)
    finally:
        clear_pyqt_session_token_provider()


def test_cli_still_reads_env_token(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_pyqt_session_token_provider()
    monkeypatch.setenv("QMTOOL_SESSION_TOKEN", "cli-token-ok")
    assert resolve_session_token() == "cli-token-ok"


def test_https_required_for_non_loopback() -> None:
    from interfaces.clients.http_transport import validate_backend_base_url

    with pytest.raises(BackendTransportError):
        validate_backend_base_url("http://192.168.0.10:8000")
    assert validate_backend_base_url("https://192.168.0.10:8000") == "https://192.168.0.10:8000"
    assert validate_backend_base_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
