"""Backend identity adapter: session mirror + directory HTTP, no shadow login."""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from interfaces.clients.backend_identity import BackendIdentityAdapter
from interfaces.clients.backend_session import BackendSessionApi
from interfaces.clients.http_transport import BackendHttpTransport, BackendTransportError
from src.backend.api import create_app
from tests.backend.test_auth_api import _build_test_container


class _TestClientTransport(BackendHttpTransport):
    def __init__(self, client: TestClient, *, token_provider) -> None:
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
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers: dict[str, str] = {}
        if headers:
            request_headers.update(headers)
        if auth:
            token = ""
            if self._token_provider is not None:
                token = (self._token_provider() or "").strip()
            if not token:
                raise BackendTransportError("backend session token is required", status_code=401)
            request_headers["Authorization"] = f"Bearer {token}"
        data = raw_body
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = content_type
        response = self._client.request(method, path, content=data, headers=request_headers)
        if response.status_code >= 400:
            raise BackendTransportError(
                f"backend HTTP {response.status_code}: {response.text}",
                status_code=response.status_code,
                body=response.text,
            )
        if not expect_json:
            return response.content
        if not response.content:
            return None
        return response.json()


@pytest.fixture
def session_and_adapter(tmp_path):
    container, _repo, _service = _build_test_container(tmp_path)
    # Ensure bob is usable without password-change gate for directory tests.
    client = TestClient(create_app(container))
    api = BackendSessionApi.__new__(BackendSessionApi)
    api._token = None
    api._user = None
    api._transport = _TestClientTransport(client, token_provider=api.bearer_token)
    adapter = BackendIdentityAdapter(
        api,
        transport=_TestClientTransport(client, token_provider=api.bearer_token),
    )
    return api, adapter


def test_get_current_user_mirrors_session_not_local_login(session_and_adapter) -> None:
    api, adapter = session_and_adapter
    assert adapter.get_current_user() is None
    user = api.login("bob", "bob-secret")
    assert adapter.get_current_user() is user
    assert adapter.get_current_user().user_id == user.user_id


def test_local_login_is_fail_closed(session_and_adapter) -> None:
    _api, adapter = session_and_adapter
    with pytest.raises(RuntimeError, match="lokales Login"):
        adapter.login("bob", "bob-secret")


def test_list_users_uses_directory_after_session_login(session_and_adapter) -> None:
    api, adapter = session_and_adapter
    api.login("bob", "bob-secret")
    rows = adapter.list_users()
    names = {row.username for row in rows}
    assert "bob" in names
    assert all(row.is_active for row in rows)


def test_admin_create_user_and_patch_qmb_via_http(session_and_adapter) -> None:
    api, adapter = session_and_adapter
    api.login("admin", "admin")
    api.change_password("admin-ready1")
    created = adapter.create_user(
        "qmb_gui",
        "qmbsecret12",
        "QMB",
        must_change_password=False,
    )
    assert created.username == "qmb_gui"
    assert created.role == "QMB"
    assert created.user_id

    names = {row.username for row in adapter.list_users()}
    assert "qmb_gui" in names

    patched = adapter.update_user_admin_fields("bob", is_qmb=True, is_active=True)
    assert patched.username == "bob"
    assert patched.is_qmb is True


def test_create_user_forbidden_for_non_admin(session_and_adapter) -> None:
    api, adapter = session_and_adapter
    api.login("bob", "bob-secret")
    with pytest.raises(RuntimeError, match="Administrator"):
        adapter.create_user("x", "password12", "User", must_change_password=False)


def test_update_rejects_unsupported_stammdaten(session_and_adapter) -> None:
    api, adapter = session_and_adapter
    api.login("admin", "admin")
    api.change_password("admin-ready2")
    with pytest.raises(RuntimeError, match="nicht unterstützt"):
        adapter.update_user_admin_fields("bob", department="QM", is_active=True)
