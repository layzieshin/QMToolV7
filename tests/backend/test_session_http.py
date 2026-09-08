"""HTTP session connection and bootstrap contracts (WCON00-B)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from modules.usermanagement.memory_session_repository import InMemorySessionRepository
from modules.usermanagement.service import UserManagementService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.maintenance import enter_maintenance
from src.backend.api import create_app
from src.backend.bootstrap import build_platform_ports
from tests.database_helpers import user_repository as SQLiteUserRepository


def _build_licensed_test_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> RuntimeContainer:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_LICENSE_MODE", "dev")
    container = build_platform_ports(fail_closed_license=False)

    repository = SQLiteUserRepository(tmp_path / "users.db")
    repository.ensure_initial_admin("admin", "admin", role="Admin", must_change_password=False)
    repository.create_user("bob", "bob-secret", "User")

    service = UserManagementService(
        event_bus=container.get_port("event_bus"),
        repository=repository,
        session_repository=InMemorySessionRepository(),
    )
    container.register_port("usermanagement_service", service)
    return container


@pytest.fixture
def licensed_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    container = _build_licensed_test_container(tmp_path, monkeypatch)
    return TestClient(create_app(container))


def test_connection_without_container() -> None:
    response = TestClient(create_app()).get("/api/v1/session/connection")
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "1"
    assert body["service"] == "qmtool-backend"
    assert body["maintenance"] is False
    assert body["writes_allowed"] is True
    assert body["status"] == "ok"


def test_bootstrap_without_auth() -> None:
    response = TestClient(create_app()).get("/api/v1/session/bootstrap")
    assert response.status_code == 401


def test_bootstrap_after_login_lists_licensed_modules(licensed_client: TestClient) -> None:
    login = licensed_client.post(
        "/api/v1/auth/token",
        json={"username": "bob", "password": "bob-secret"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    response = licensed_client.get(
        "/api/v1/session/bootstrap",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "1"

    modules = {item["id"]: item for item in body["modules"]}
    assert "usermanagement" in modules
    assert modules["usermanagement"]["licensed"] is True
    assert modules["usermanagement"]["authorized"] is True
    assert isinstance(modules["usermanagement"]["capabilities"], list)

    assert "documents" in modules
    assert modules["documents"]["licensed"] is True
    assert modules["documents"]["authorized"] is True
    assert isinstance(modules["documents"]["capabilities"], list)


def test_connection_reports_maintenance_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = _build_licensed_test_container(tmp_path, monkeypatch)
    enter_maintenance(tmp_path)
    client = TestClient(create_app(container))

    response = client.get("/api/v1/session/connection")
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "1"
    assert body["maintenance"] is True
    assert body["writes_allowed"] is False
    assert body["status"] == "degraded"
