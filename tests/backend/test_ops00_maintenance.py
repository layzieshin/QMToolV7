"""OPS00-D backend maintenance mode HTTP gate."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.maintenance import enter_maintenance, exit_maintenance
from qm_platform.settings.testing import build_settings_service_for_tests
from src.backend.api import create_app


def _minimal_container(tmp_path: Path) -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("logger", LoggerService(tmp_path / "platform.log"))
    container.register_port("audit_logger", AuditLogger(tmp_path / "audit.log"))
    container.register_port("event_bus", EventBus())
    container.register_port(
        "settings_service",
        build_settings_service_for_tests(tmp_path),
    )
    container.register_port("app_home", tmp_path)
    container.register_port("resource_root", tmp_path)
    return container


def test_maintenance_blocks_state_changing_requests_but_not_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    enter_maintenance(tmp_path)
    client = TestClient(create_app(_minimal_container(tmp_path)))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    blocked = client.post("/api/v1/auth/token", json={"username": "u", "password": "p"})
    assert blocked.status_code == 503
    detail = blocked.json()["detail"]
    assert detail["error"] == "maintenance_mode"


def test_exit_maintenance_restores_write_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    enter_maintenance(tmp_path)
    app = create_app(_minimal_container(tmp_path))

    @app.post("/__test_maintenance_probe__")
    def _probe() -> dict[str, str]:
        return {"status": "writable"}

    client = TestClient(app)
    blocked = client.post("/__test_maintenance_probe__")
    assert blocked.status_code == 503
    assert blocked.json()["detail"]["error"] == "maintenance_mode"

    exit_maintenance(tmp_path)
    response = client.post("/__test_maintenance_probe__")
    assert response.status_code == 200
    assert response.json()["status"] == "writable"
