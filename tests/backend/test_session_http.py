"""HTTP session connection and bootstrap contracts (WCON00-B)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from modules.documents.module import (
    create_documents_client_module_contract,
    create_documents_module_contract,
)
from modules.usermanagement.memory_session_repository import InMemorySessionRepository
from modules.usermanagement.module import create_usermanagement_module_contract
from modules.usermanagement.service import UserManagementService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.maintenance import enter_maintenance
from src.backend.api import create_app
from src.backend.bootstrap import (
    ACTIVE_BACKEND_MODULE_CONTRACTS_PORT,
    build_platform_ports,
)
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
    container.register_port(
        ACTIVE_BACKEND_MODULE_CONTRACTS_PORT,
        (
            create_usermanagement_module_contract(),
            create_documents_module_contract(),
        ),
    )
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


def test_bootstrap_uses_license_tags_not_module_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(create_app(_build_licensed_test_container(tmp_path, monkeypatch)))
    license_service = client.app.state.container.get_port("license_service")
    original_allowed = license_service.is_module_allowed

    def _is_module_allowed(module_tag: str) -> bool:
        if module_tag in {"documents", "signature", "registry", "training"}:
            return False
        return original_allowed(module_tag)

    monkeypatch.setattr(license_service, "is_module_allowed", _is_module_allowed)
    login = client.post(
        "/api/v1/auth/token",
        json={"username": "bob", "password": "bob-secret"},
    )
    assert login.status_code == 200
    response = client.get(
        "/api/v1/session/bootstrap",
        headers={"Authorization": f"Bearer {login.json()['token']}"},
    )
    assert response.status_code == 200
    modules = {item["id"]: item for item in response.json()["modules"]}
    assert modules["documents"]["licensed"] is True
    assert modules["usermanagement"]["licensed"] is True
    assert "training" not in modules
    assert "incident_management" not in modules


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


def test_bootstrap_without_composition_port_returns_empty_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    client = TestClient(create_app(container))

    login = client.post(
        "/api/v1/auth/token",
        json={"username": "bob", "password": "bob-secret"},
    )
    assert login.status_code == 200
    response = client.get(
        "/api/v1/session/bootstrap",
        headers={"Authorization": f"Bearer {login.json()['token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "1"
    assert body["modules"] == []
    module_ids = {item["id"] for item in body["modules"]}
    assert "training" not in module_ids
    assert "incident_management" not in module_ids


def test_auth_routes_does_not_import_runtime_bootstrap_at_module_level() -> None:
    """Keep create_app importable without pulling incident_management/reportlab."""
    source = Path("src/backend/auth_routes.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "qm_platform.runtime.bootstrap":
            raise AssertionError("auth_routes must not import runtime.bootstrap")
        if isinstance(node, ast.ImportFrom) and node.module == "qm_platform.runtime":
            imported = {alias.name for alias in node.names}
            assert "bootstrap" not in imported
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "qm_platform.runtime.bootstrap"


def test_backend_composition_registers_full_documents_module_contract() -> None:
    """Backend wiring must publish the full documents contract, not the client variant."""
    backend_source = Path("src/backend/bootstrap.py").read_text(encoding="utf-8")
    assert "create_documents_module_contract" in backend_source
    assert "create_documents_client_module_contract" not in backend_source

    backend_contract = create_documents_module_contract()
    client_contract = create_documents_client_module_contract()
    assert "documents_service" in backend_contract.provided_ports
    assert "documents_service" not in client_contract.provided_ports

    tree = ast.parse(backend_source)
    build_fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "build_backend_container"
    )
    call_names = {
        node.func.id
        for node in ast.walk(build_fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "create_documents_module_contract" in call_names
    assert "create_documents_client_module_contract" not in call_names
