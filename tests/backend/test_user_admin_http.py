"""HTTP contracts for WCON00-F admin user list/detail and password actions."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from modules.usermanagement.memory_session_repository import InMemorySessionRepository
from modules.usermanagement.service import UserManagementService
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.testing import build_settings_service_for_tests
from src.backend.api import create_app
from tests.database_helpers import user_repository as SQLiteUserRepository


def _build_test_container(tmp_path: Path) -> tuple[RuntimeContainer, SQLiteUserRepository, UserManagementService]:
    container = RuntimeContainer()
    events = EventBus()
    container.register_port("logger", LoggerService(tmp_path / "platform.log"))
    container.register_port("audit_logger", AuditLogger(tmp_path / "audit.log"))
    container.register_port("event_bus", events)
    container.register_port(
        "settings_service",
        build_settings_service_for_tests(tmp_path),
    )
    container.register_port("app_home", tmp_path)
    container.register_port("resource_root", tmp_path)

    repository = SQLiteUserRepository(tmp_path / "users.db")
    repository.ensure_initial_admin("admin", "adminpass12", role="Admin", must_change_password=False)
    repository.create_user("bob", "bobsecret12", "User", must_change_password=False)
    repository.create_user("inactive", "inactive-secret", "User", is_active=False, must_change_password=False)

    service = UserManagementService(
        event_bus=events,
        repository=repository,
        session_repository=InMemorySessionRepository(),
    )
    container.register_port("usermanagement_service", service)
    return container, repository, service


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    container, _repo, _service = _build_test_container(tmp_path)
    return TestClient(create_app(container))


def _admin_token(client: TestClient) -> str:
    login = client.post("/api/v1/auth/token", json={"username": "admin", "password": "adminpass12"})
    assert login.status_code == 200
    return login.json()["token"]


def _bob_token(client: TestClient) -> str:
    login = client.post("/api/v1/auth/token", json={"username": "bob", "password": "bobsecret12"})
    assert login.status_code == 200
    return login.json()["token"]


def test_admin_list_includes_inactive_after_deactivate(client: TestClient) -> None:
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    deactivated = client.patch(
        "/api/v1/users/bob/access",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200

    listed = client.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200
    usernames = {item["username"] for item in listed.json()}
    assert "bob" in usernames
    bob = next(item for item in listed.json() if item["username"] == "bob")
    assert bob["is_active"] is False
    assert "must_change_password" in bob


def test_directory_omits_inactive(client: TestClient) -> None:
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.patch("/api/v1/users/bob/access", headers=headers, json={"is_active": False})

    directory = client.get("/api/v1/users/directory", headers=headers)
    assert directory.status_code == 200
    usernames = {item["username"] for item in directory.json()}
    assert "bob" not in usernames
    assert "inactive" not in usernames
    assert "admin" in usernames
    assert all("must_change_password" not in item for item in directory.json())


def test_admin_detail_includes_must_change_password(client: TestClient) -> None:
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    detail = client.get("/api/v1/users/bob", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert set(body) == {
        "user_id",
        "username",
        "role",
        "is_active",
        "is_qmb",
        "must_change_password",
    }
    assert body["username"] == "bob"
    assert isinstance(body["must_change_password"], bool)


def test_non_admin_forbidden_on_admin_user_routes(client: TestClient) -> None:
    bob = _bob_token(client)
    headers = {"Authorization": f"Bearer {bob}"}

    assert client.get("/api/v1/users", headers=headers).status_code == 403
    assert client.get("/api/v1/users/bob", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/users/bob/password-actions",
            headers=headers,
            json={"new_password": "newpassword1"},
        ).status_code
        == 403
    )


def test_unauth_returns_401(client: TestClient) -> None:
    assert client.get("/api/v1/users").status_code == 401
    assert client.get("/api/v1/users/bob").status_code == 401
    assert (
        client.post("/api/v1/users/bob/password-actions", json={"new_password": "newpassword1"}).status_code
        == 401
    )


def test_password_action_sets_must_change_and_weak_password_field_errors(client: TestClient) -> None:
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    bob_token = _bob_token(client)
    action = client.post(
        "/api/v1/users/bob/password-actions",
        headers=headers,
        json={"new_password": "resetpassword1"},
    )
    assert action.status_code == 204

    detail = client.get("/api/v1/users/bob", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["must_change_password"] is True

    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bob_token}"}).status_code == 401

    weak = client.post(
        "/api/v1/users/bob/password-actions",
        headers=headers,
        json={"new_password": "short"},
    )
    assert weak.status_code == 400
    assert weak.json()["detail"]["error"] == "weak_password"
    assert weak.json()["detail"]["field_errors"][0]["field"] == "new_password"
