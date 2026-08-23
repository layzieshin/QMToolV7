"""User directory HTTP API (J04-M0)."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from qm_platform.settings.testing import build_settings_service_for_tests
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from modules.usermanagement.memory_session_repository import InMemorySessionRepository
from modules.usermanagement.service import UserManagementService
from src.backend.api import create_app
from tests.database_helpers import user_repository as SQLiteUserRepository


def _build_test_container(tmp_path: Path) -> RuntimeContainer:
    container = RuntimeContainer()
    events = EventBus()
    container.register_port("logger", LoggerService(tmp_path / "platform.log"))
    container.register_port("audit_logger", AuditLogger(tmp_path / "audit.log"))
    container.register_port("event_bus", events)
    container.register_port("settings_service", build_settings_service_for_tests(tmp_path))
    container.register_port("app_home", tmp_path)
    container.register_port("resource_root", tmp_path)
    repository = SQLiteUserRepository(tmp_path / "users.db")
    repository.ensure_initial_admin("admin", "admin", role="Admin", must_change_password=False)
    repository.create_user("bob", "bob-secret", "User")
    service = UserManagementService(
        event_bus=events,
        repository=repository,
        session_repository=InMemorySessionRepository(),
    )
    container.register_port("usermanagement_service", service)
    return container


def test_user_directory_requires_auth(tmp_path: Path) -> None:
    client = TestClient(create_app(_build_test_container(tmp_path)))
    denied = client.get("/api/v1/users/directory")
    assert denied.status_code == 401


def test_user_directory_lists_active_users(tmp_path: Path) -> None:
    client = TestClient(create_app(_build_test_container(tmp_path)))
    login = client.post("/api/v1/auth/token", json={"username": "bob", "password": "bob-secret"})
    token = login.json()["token"]
    response = client.get("/api/v1/users/directory", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    rows = response.json()
    assert any(row["username"] == "bob" and row["user_id"] for row in rows)
