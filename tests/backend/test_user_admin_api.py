"""HTTP contracts for AP-028 M6 logout-all and minimal admin user API."""
from __future__ import annotations

from qm_platform.settings.testing import build_settings_service_for_tests
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from modules.usermanagement.memory_session_repository import InMemorySessionRepository
from modules.usermanagement.service import UserManagementService
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from src.backend.api import create_app
from tests.database_helpers import user_repository as SQLiteUserRepository


def _build(tmp_path: Path) -> tuple[TestClient, UserManagementService]:
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
    repository.create_user("admin2", "admin2pass1", "Admin", must_change_password=False)

    service = UserManagementService(
        event_bus=events,
        repository=repository,
        session_repository=InMemorySessionRepository(),
    )
    container.register_port("usermanagement_service", service)
    return TestClient(create_app(container)), service


def _admin_token(client: TestClient) -> str:
    login = client.post("/api/v1/auth/token", json={"username": "admin", "password": "adminpass12"})
    assert login.status_code == 200
    return login.json()["token"]


def test_logout_all_invalidates_current_token(tmp_path: Path) -> None:
    client, _service = _build(tmp_path)
    token = _admin_token(client)
    other = client.post("/api/v1/auth/token", json={"username": "admin", "password": "adminpass12"}).json()["token"]
    response = client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {other}"}).status_code == 401


def test_admin_create_user_defaults_and_explicit(tmp_path: Path) -> None:
    client, _service = _build(tmp_path)
    token = _admin_token(client)
    created = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "newbie", "password": "newpassword1"},
    )
    assert created.status_code == 201
    body = created.json()
    assert set(body) == {
        "user_id",
        "username",
        "role",
        "is_active",
        "is_qmb",
        "must_change_password",
    }
    assert body["role"] == "User"
    assert body["is_qmb"] is False
    assert body["must_change_password"] is True
    assert "password_hash" not in created.text.lower()
    assert '"password"' not in created.text.lower()
    assert "token" not in created.text.lower()

    explicit = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "qmbuser",
            "password": "newpassword2",
            "role": "User",
            "is_qmb": True,
            "must_change_password": False,
        },
    )
    assert explicit.status_code == 201
    assert explicit.json()["is_qmb"] is True
    assert explicit.json()["must_change_password"] is False


def test_non_admin_forbidden_and_unauth(tmp_path: Path) -> None:
    client, _service = _build(tmp_path)
    assert client.post("/api/v1/users", json={"username": "x", "password": "password12"}).status_code == 401
    bob = client.post("/api/v1/auth/token", json={"username": "bob", "password": "bobsecret12"}).json()["token"]
    denied = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {bob}"},
        json={"username": "x", "password": "password12"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "forbidden"


def test_patch_access_role_qmb_deactivate_and_errors(tmp_path: Path) -> None:
    client, service = _build(tmp_path)
    token = _admin_token(client)
    bob_login = client.post("/api/v1/auth/token", json={"username": "bob", "password": "bobsecret12"})
    bob_token = bob_login.json()["token"]

    patched = client.patch(
        "/api/v1/users/bob/access",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_qmb": True},
    )
    assert patched.status_code == 200
    assert patched.json()["is_qmb"] is True
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bob_token}"})
    assert me.status_code == 200
    assert me.json()["is_qmb"] is True

    deactivated = client.patch(
        "/api/v1/users/bob/access",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bob_token}"}).status_code == 401

    empty = client.patch(
        "/api/v1/users/bob/access",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert empty.status_code == 400
    assert empty.json()["detail"]["error"] == "invalid_user_update"

    missing = client.patch(
        "/api/v1/users/missing/access",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_active": True},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "user_not_found"

    # With admin2 active, demoting admin is allowed
    demoted = client.patch(
        "/api/v1/users/admin/access",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "User"},
    )
    assert demoted.status_code == 200
    assert demoted.json()["role"] == "User"

    # Sole remaining admin cannot be deactivated
    admin2_token = client.post(
        "/api/v1/auth/token", json={"username": "admin2", "password": "admin2pass1"}
    ).json()["token"]
    blocked = client.patch(
        "/api/v1/users/admin2/access",
        headers={"Authorization": f"Bearer {admin2_token}"},
        json={"is_active": False},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["error"] == "last_active_admin"

    weak = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin2_token}"},
        json={"username": "weakling", "password": ""},
    )
    assert weak.status_code == 400
    assert weak.json()["detail"]["error"] == "weak_password"

    dup = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin2_token}"},
        json={"username": "bob", "password": "password12"},
    )
    assert dup.status_code == 409
    assert dup.json()["detail"]["error"] == "user_exists"
