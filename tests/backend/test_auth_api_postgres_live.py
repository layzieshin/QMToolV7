"""PostgreSQL live coverage for the M5 backend auth composition path."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.usermanagement import postgres_schema as pgs
from qm_platform.runtime.backend_bootstrap import (
    BackendUsermanagementBootstrapError,
    wire_backend_usermanagement,
)
from src.backend.api import create_app
from src.backend.bootstrap import BackendBootstrapError, build_platform_ports
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres


@pytest.fixture
def runtime_env(tmp_path, monkeypatch, live_postgres_env: LivePostgresEnv):
    admin_dsn = live_postgres_env.admin_dsn
    migrator_dsn = live_postgres_env.migrator_dsn
    runtime_dsn = live_postgres_env.runtime_dsn
    pgs.migrate_usermanagement_schema(migrator_dsn)
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_LICENSE_MODE", "dev")
    monkeypatch.setenv("QMTOOL_PG_DSN", runtime_dsn)
    monkeypatch.delenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    yield admin_dsn, migrator_dsn, runtime_dsn


def test_backend_wire_refuses_empty_users_without_bootstrap(runtime_env, monkeypatch) -> None:
    _admin, _migrator, runtime_dsn = runtime_env
    container = build_platform_ports(fail_closed_license=True)
    container.register_port("usermanagement_postgres_dsn", runtime_dsn)
    with pytest.raises(BackendUsermanagementBootstrapError, match="no users"):
        wire_backend_usermanagement(container)


def test_backend_wire_refuses_admin_admin_bootstrap(runtime_env, monkeypatch) -> None:
    _admin, _migrator, runtime_dsn = runtime_env
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "admin")
    container = build_platform_ports(fail_closed_license=True)
    container.register_port("usermanagement_postgres_dsn", runtime_dsn)
    with pytest.raises(BackendUsermanagementBootstrapError, match="insecure"):
        wire_backend_usermanagement(container)


def test_backend_wire_refuses_weak_bootstrap_password(runtime_env, monkeypatch) -> None:
    _admin, _migrator, runtime_dsn = runtime_env
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "opsadmin")
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "short")
    container = build_platform_ports(fail_closed_license=True)
    container.register_port("usermanagement_postgres_dsn", runtime_dsn)
    with pytest.raises(BackendUsermanagementBootstrapError, match="password policy"):
        wire_backend_usermanagement(container)


def test_existing_users_ignore_bootstrap_env(runtime_env, monkeypatch) -> None:
    _admin, _migrator, runtime_dsn = runtime_env
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "opsadmin")
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "ops-secret-1")
    container = build_platform_ports(fail_closed_license=True)
    container.register_port("usermanagement_postgres_dsn", runtime_dsn)
    wire_backend_usermanagement(container)

    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "otheradmin")
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "other-secret-1")
    from qm_platform.runtime.backend_bootstrap import _ensure_users_or_bootstrap

    _ensure_users_or_bootstrap(container)
    service = container.get_port("usermanagement_service")
    names = {user.username for user in service.list_users()}
    assert names == {"opsadmin"}
    assert service.authenticate("opsadmin", "ops-secret-1") is not None
    assert service.authenticate("otheradmin", "other-secret-1") is None


def test_backend_auth_http_over_postgres(runtime_env, monkeypatch) -> None:
    _admin, _migrator, runtime_dsn = runtime_env
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "opsadmin")
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "ops-secret-1")
    container = build_platform_ports(fail_closed_license=True)
    container.register_port("usermanagement_postgres_dsn", runtime_dsn)
    wire_backend_usermanagement(container)
    client = TestClient(create_app(container))

    login = client.post(
        "/auth/login",
        json={"username": "opsadmin", "password": "ops-secret-1"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    assert set(login.json()) == {"token"}

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 409
    assert me.json()["detail"]["error"] == "password_change_required"

    changed = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "ops-secret-2"},
    )
    assert changed.status_code == 204
    me_ok = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_ok.status_code == 200
    assert me_ok.json()["username"] == "opsadmin"

    logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout.status_code == 204


def test_license_mode_required_for_backend_platform(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.delenv("QMTOOL_LICENSE_MODE", raising=False)
    with pytest.raises(BackendBootstrapError, match="QMTOOL_LICENSE_MODE"):
        build_platform_ports(fail_closed_license=True)


def test_runtime_schema_ready_rejects_fingerprint_drift(runtime_env) -> None:
    _admin, migrator_dsn, runtime_dsn = runtime_env
    with __import__("psycopg").connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        conn.execute("ALTER TABLE usermanagement.users ADD COLUMN drift_col text")
        conn.commit()
    with pytest.raises(pgs.PostgresSchemaError, match="fingerprint"):
        pgs.assert_runtime_schema_ready(runtime_dsn)
