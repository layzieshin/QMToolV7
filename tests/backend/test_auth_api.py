"""HTTP auth API contracts for AP-028 M5."""
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
from src.backend.bootstrap import BackendBootstrapError, resolve_usermanagement_postgres_dsn
from tests.database_helpers import user_repository as SQLiteUserRepository


def _build_test_container(tmp_path: Path) -> tuple[RuntimeContainer, object, UserManagementService]:
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
    repository.ensure_initial_admin("admin", "admin", role="Admin", must_change_password=True)
    repository.create_user("bob", "bob-secret", "User")
    repository.create_user("inactive", "inactive-secret", "User", is_active=False)

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


def test_health_without_container() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "qmtool-backend"}
    assert "X-Request-ID" in response.headers


def test_login_me_logout_and_separate_sessions(client: TestClient) -> None:
    login_a = client.post("/auth/login", json={"username": "bob", "password": "bob-secret"})
    login_b = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert login_a.status_code == 200
    assert login_b.status_code == 200
    assert set(login_a.json()) == {"token"}
    assert login_a.json()["token"] != login_b.json()["token"]

    me_a = client.get("/auth/me", headers={"Authorization": f"Bearer {login_a.json()['token']}"})
    assert me_a.status_code == 200
    assert me_a.json()["username"] == "bob"
    assert me_a.json()["user_id"]
    assert "password" not in me_a.text.lower()

    me_admin = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {login_b.json()['token']}",
            "X-Request-ID": "corr-123",
        },
    )
    assert me_admin.status_code == 409
    assert me_admin.json()["detail"]["error"] == "password_change_required"
    assert me_admin.headers["X-Request-ID"] == "corr-123"

    logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {login_a.json()['token']}"})
    assert logout.status_code == 204
    again = client.post("/auth/logout", headers={"Authorization": f"Bearer {login_a.json()['token']}"})
    assert again.status_code == 204
    denied = client.get("/auth/me", headers={"Authorization": f"Bearer {login_a.json()['token']}"})
    assert denied.status_code == 401


def test_invalid_and_inactive_login(client: TestClient) -> None:
    bad = client.post("/auth/login", json={"username": "bob", "password": "wrong"})
    inactive = client.post("/auth/login", json={"username": "inactive", "password": "inactive-secret"})
    assert bad.status_code == 401
    assert inactive.status_code == 401
    assert bad.json()["detail"]["error"] == "unauthorized"


def test_missing_and_foreign_token(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401


def test_change_password_keeps_current_session(tmp_path: Path) -> None:
    container, repository, service = _build_test_container(tmp_path)
    client = TestClient(create_app(container))

    login = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    token = login.json()["token"]
    other = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    other_token = other.json()["token"]

    # /me blocked until password change
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 409

    changed = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "admin-new1"},
    )
    assert changed.status_code == 204

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    # M6: other sessions ARE revoked; current session remains valid
    other_me = client.get("/auth/me", headers={"Authorization": f"Bearer {other_token}"})
    assert other_me.status_code == 401

    weak = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "short"},
    )
    assert weak.status_code == 400
    assert weak.json()["detail"]["error"] == "weak_password"

    empty = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": ""},
    )
    assert empty.status_code == 400
    assert empty.json()["detail"]["error"] == "weak_password"

    spaces = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "   "},
    )
    assert spaces.status_code == 400
    assert spaces.json()["detail"]["error"] == "weak_password"

    # password_change_allowed cannot be set by client fields
    spoof = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "againagain", "username": "bob", "password_change_allowed": True},
    )
    assert spoof.status_code == 204
    bob_login = client.post("/auth/login", json={"username": "bob", "password": "bob-secret"})
    assert bob_login.status_code == 200
    # admin password was changed again; bob unchanged
    assert client.post("/auth/login", json={"username": "admin", "password": "againagain"}).status_code == 200

    # ensure body cannot target another user — bob password still original
    assert repository.get_by_username("bob") is not None
    assert service.authenticate("bob", "bob-secret") is not None


def test_dsn_resolution_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QMTOOL_PG_DSN", raising=False)
    monkeypatch.delenv("QMTOOL_PG_HOST", raising=False)
    monkeypatch.delenv("QMTOOL_PG_DATABASE", raising=False)
    monkeypatch.delenv("QMTOOL_PG_USER", raising=False)
    monkeypatch.delenv("QMTOOL_PG_PASSWORD", raising=False)
    monkeypatch.setattr("src.backend.bootstrap._load_dotenv", lambda path=None: None)
    with pytest.raises(BackendBootstrapError, match="no SQLite fallback"):
        resolve_usermanagement_postgres_dsn()


def test_backend_license_mode_defaults_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.backend.bootstrap import build_platform_ports

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.delenv("QMTOOL_LICENSE_MODE", raising=False)
    with pytest.raises(BackendBootstrapError, match="QMTOOL_LICENSE_MODE"):
        build_platform_ports(fail_closed_license=True)

    monkeypatch.setenv("QMTOOL_LICENSE_MODE", "dev")
    container = build_platform_ports(fail_closed_license=True)
    assert container.has_port("license_service")

    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    with pytest.raises(BackendBootstrapError, match="production"):
        build_platform_ports(fail_closed_license=True)
