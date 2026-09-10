"""PostgreSQL live coverage for AP-028 M6 session enforcement."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from fastapi.testclient import TestClient

from modules.usermanagement import postgres_schema as pgs
from qm_platform.runtime.backend_bootstrap import wire_backend_usermanagement
from src.backend.api import create_app
from src.backend.bootstrap import build_platform_ports
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
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "opsadmin")
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "ops-secret-1")
    yield admin_dsn, migrator_dsn, runtime_dsn


def _wired_client(runtime_dsn):
    container = build_platform_ports(fail_closed_license=True)
    container.register_port("usermanagement_postgres_dsn", runtime_dsn)
    wire_backend_usermanagement(container)
    return TestClient(create_app(container)), container.get_port("usermanagement_service")


def test_postgres_change_password_revokes_other_sessions_atomically(runtime_env) -> None:
    _admin, _migrator, runtime_dsn = runtime_env
    client, service = _wired_client(runtime_dsn)
    first = client.post("/api/v1/auth/token", json={"username": "opsadmin", "password": "ops-secret-1"})
    second = client.post("/api/v1/auth/token", json={"username": "opsadmin", "password": "ops-secret-1"})
    token_a = first.json()["token"]
    token_b = second.json()["token"]
    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"new_password": "ops-secret-2"},
    )
    assert changed.status_code == 204
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"}).status_code == 200
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"}).status_code == 401
    assert service.authenticate("opsadmin", "ops-secret-2") is not None


def test_postgres_deactivate_revokes_and_reactivation_does_not_revive(runtime_env) -> None:
    _admin, _migrator, runtime_dsn = runtime_env
    client, service = _wired_client(runtime_dsn)
    admin_login = client.post("/api/v1/auth/token", json={"username": "opsadmin", "password": "ops-secret-1"})
    admin_token = admin_login.json()["token"]
    client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"new_password": "ops-secret-2"},
    )
    created = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "worker",
            "password": "workerpass1",
            "must_change_password": False,
        },
    )
    assert created.status_code == 201
    worker_token = client.post(
        "/api/v1/auth/token", json={"username": "worker", "password": "workerpass1"}
    ).json()["token"]
    deactivated = client.patch(
        "/api/v1/users/worker/access",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker_token}"}).status_code == 401
    with psycopg.connect(runtime_dsn) as conn:
        row = conn.execute(
            """
            SELECT is_active, deactivated_at
            FROM usermanagement.users
            WHERE username = %s
            """,
            ("worker",),
        ).fetchone()
    assert row is not None
    assert row[0] is False
    assert row[1] is not None
    client.patch(
        "/api/v1/users/worker/access",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": True},
    )
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker_token}"}).status_code == 401
    assert (
        client.post("/api/v1/auth/token", json={"username": "worker", "password": "workerpass1"}).status_code
        == 200
    )


def test_postgres_concurrent_last_admin_guard(runtime_env) -> None:
    _admin, _migrator, runtime_dsn = runtime_env
    client, service = _wired_client(runtime_dsn)
    token = client.post(
        "/api/v1/auth/token", json={"username": "opsadmin", "password": "ops-secret-1"}
    ).json()["token"]
    client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "ops-secret-2"},
    )

    def _attempt(payload: dict) -> int:
        response = client.patch(
            "/api/v1/users/opsadmin/access",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_attempt, {"is_active": False}),
            pool.submit(_attempt, {"role": "User"}),
        ]
        results = [future.result() for future in futures]
    assert 409 in results
    admin = service.repository.get_user("opsadmin")
    assert admin is not None
    assert admin.is_active is True
    assert admin.role == "Admin"


def test_postgres_concurrent_mutual_admin_demotion_keeps_one_admin(runtime_env) -> None:
    """Two active admins must not both succeed at removing each other."""
    _admin, _migrator, runtime_dsn = runtime_env
    client, service = _wired_client(runtime_dsn)
    token_a = client.post(
        "/api/v1/auth/token", json={"username": "opsadmin", "password": "ops-secret-1"}
    ).json()["token"]
    client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"new_password": "ops-secret-2"},
    )
    created = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "username": "opsadmin2",
            "password": "ops-secret-3",
            "role": "Admin",
            "must_change_password": False,
        },
    )
    assert created.status_code == 201
    token_b = client.post(
        "/api/v1/auth/token", json={"username": "opsadmin2", "password": "ops-secret-3"}
    ).json()["token"]

    def _demote(actor_token: str, target: str) -> int:
        return client.patch(
            f"/api/v1/users/{target}/access",
            headers={"Authorization": f"Bearer {actor_token}"},
            json={"role": "User"},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_demote, token_a, "opsadmin2"),
            pool.submit(_demote, token_b, "opsadmin"),
        ]
        results = [future.result() for future in futures]
    assert sorted(results) == [200, 409]
    active_admins = [
        user
        for user in service.list_users()
        if user.is_active and user.role == "Admin"
    ]
    assert len(active_admins) == 1


def _read_password_changed_audits(migrator_dsn: str, *, target_user_id: str) -> list[dict]:
    with psycopg.connect(migrator_dsn, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        rows = conn.execute(
            """
            SELECT event_type, target_user_id::text AS target_user_id
            FROM usermanagement.audit_events
            WHERE event_type = 'user.password_changed'
              AND target_user_id = %s::uuid
            ORDER BY occurred_at, audit_id
            """,
            (target_user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def test_postgres_admin_password_reset_revokes_sessions_and_sets_must_change(runtime_env) -> None:
    admin_dsn, migrator_dsn, runtime_dsn = runtime_env
    client, service = _wired_client(runtime_dsn)
    admin_token = client.post(
        "/api/v1/auth/token", json={"username": "opsadmin", "password": "ops-secret-1"}
    ).json()["token"]
    client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"new_password": "ops-secret-2"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    created = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": "worker",
            "password": "workerpass1",
            "must_change_password": False,
        },
    )
    assert created.status_code == 201
    worker_token_a = client.post(
        "/api/v1/auth/token", json={"username": "worker", "password": "workerpass1"}
    ).json()["token"]
    worker_token_b = client.post(
        "/api/v1/auth/token", json={"username": "worker", "password": "workerpass1"}
    ).json()["token"]

    reset = client.post(
        "/api/v1/users/worker/password-actions",
        headers=admin_headers,
        json={"new_password": "workerreset1"},
    )
    assert reset.status_code == 204
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker_token_a}"}).status_code
        == 401
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker_token_b}"}).status_code
        == 401
    )
    assert service.authenticate("worker", "workerreset1") is not None
    detail = client.get("/api/v1/users/worker", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["must_change_password"] is True
    del admin_dsn, migrator_dsn


def test_postgres_admin_password_reset_rolls_back_on_late_failure(
    runtime_env,
    monkeypatch,
) -> None:
    admin_dsn, migrator_dsn, runtime_dsn = runtime_env
    client, service = _wired_client(runtime_dsn)
    from modules.usermanagement.postgres_user_repository import PostgresUserRepository

    admin_token = client.post(
        "/api/v1/auth/token", json={"username": "opsadmin", "password": "ops-secret-1"}
    ).json()["token"]
    client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"new_password": "ops-secret-2"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    created = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": "worker",
            "password": "workerpass1",
            "must_change_password": False,
        },
    )
    assert created.status_code == 201
    worker = service.repository.get_user("worker")
    assert worker is not None
    worker_token = client.post(
        "/api/v1/auth/token", json={"username": "worker", "password": "workerpass1"}
    ).json()["token"]

    def _fail_after_password_update(conn, username, must_change_password):
        raise RuntimeError("injected admin password reset failure")

    monkeypatch.setattr(
        PostgresUserRepository,
        "set_must_change_password_on_connection",
        _fail_after_password_update,
    )

    with pytest.raises(RuntimeError):
        client.post(
            "/api/v1/users/worker/password-actions",
            headers=admin_headers,
            json={"new_password": "workerreset1"},
        )

    assert service.authenticate("worker", "workerpass1") is not None
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker_token}"}).status_code
        == 200
    )
    assert _read_password_changed_audits(migrator_dsn, target_user_id=worker.user_id) == []
    del admin_dsn
