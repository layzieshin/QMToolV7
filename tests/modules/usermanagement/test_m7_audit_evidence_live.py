"""AP-028 M7 live PostgreSQL audit evidence tests.

Audit rows are read only via the migrator/admin DSN — never via qmtool_runtime.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from modules.usermanagement import postgres_schema as pgs
from modules.usermanagement.contracts import issue_user_context
from modules.usermanagement.errors import (
    AuditUnavailableError,
    AuthenticationError,
    ExpiredSessionError,
    SessionNotFoundError,
)
from modules.usermanagement.postgres_session_repository import PostgresSessionRepository
from modules.usermanagement.postgres_user_repository import PostgresUserRepository
from modules.usermanagement.service import UserManagementService
from qm_platform.events.event_bus import EventBus
from qm_platform.runtime.backend_bootstrap import wire_backend_usermanagement
from src.backend.api import create_app
from src.backend.bootstrap import build_platform_ports
from tests.postgres_destructive_guard import DestructivePostgresGuardError
from tests.postgres_live_support import (
    LivePostgresEnv,
    cleanup_live_environment,
    os_environ_required,
    prepare_live_environment,
)

pytestmark = pytest.mark.postgres


def _utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _read_audits(migrator_dsn: str) -> list[dict]:
    with psycopg.connect(migrator_dsn, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        rows = conn.execute(
            """
            SELECT event_type, result, reason_code, request_id, actor_kind,
                   actor_user_id::text AS actor_user_id,
                   actor_session_id::text AS actor_session_id,
                   system_actor,
                   target_user_id::text AS target_user_id,
                   target_session_id::text AS target_session_id,
                   affected_session_count, changed_fields,
                   role_before, role_after,
                   is_qmb_before, is_qmb_after,
                   is_active_before, is_active_after,
                   must_change_password_before, must_change_password_after
            FROM usermanagement.audit_events
            ORDER BY occurred_at, event_type, audit_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _prepare_or_skip() -> LivePostgresEnv:
    try:
        return prepare_live_environment()
    except DestructivePostgresGuardError as exc:
        if os_environ_required():
            pytest.fail(str(exc))
        pytest.skip(str(exc))


@pytest.fixture
def pg_service(tmp_path, monkeypatch, live_postgres_env: LivePostgresEnv):
    admin_dsn = live_postgres_env.admin_dsn
    migrator_dsn = live_postgres_env.migrator_dsn
    runtime_dsn = live_postgres_env.runtime_dsn
    pgs.migrate_usermanagement_schema(migrator_dsn)
    events = EventBus()
    published: list[str] = []

    class _CaptureBus:
        def publish(self, envelope) -> None:
            published.append(envelope.name)
            events.publish(envelope)

    service = UserManagementService(
        event_bus=_CaptureBus(),
        repository=PostgresUserRepository(runtime_dsn),
        session_repository=PostgresSessionRepository(runtime_dsn),
    )
    admin = service.repository.create_user(
        "opsadmin",
        "ops-secret-1",
        "Admin",
        must_change_password=False,
    )
    yield {
        "admin_dsn": admin_dsn,
        "migrator_dsn": migrator_dsn,
        "runtime_dsn": runtime_dsn,
        "service": service,
        "admin": admin,
        "published": published,
    }


def test_login_success_and_denied_audit(pg_service) -> None:
    service: UserManagementService = pg_service["service"]
    admin = pg_service["admin"]
    migrator_dsn = pg_service["migrator_dsn"]

    issued = service.login_backend("opsadmin", "ops-secret-1", request_id="req-login-ok")
    assert issued.session.user_id == admin.user_id

    with pytest.raises(AuthenticationError):
        service.login_backend("opsadmin", "wrong-password", request_id="req-login-bad")
    with pytest.raises(AuthenticationError):
        service.login_backend("missing-user", "whatever", request_id="req-login-unknown")

    rows = _read_audits(migrator_dsn)
    types = [row["event_type"] for row in rows]
    assert types == [
        "auth.login.succeeded",
        "auth.login.denied",
        "auth.login.denied",
    ]
    ok = rows[0]
    assert ok["actor_kind"] == "user"
    assert ok["actor_user_id"] == admin.user_id
    assert ok["actor_session_id"] == issued.session.session_id
    assert ok["target_user_id"] == admin.user_id
    assert ok["request_id"] == "req-login-ok"
    assert ok["reason_code"] is None
    bad = rows[1]
    assert bad["actor_kind"] == "anonymous"
    assert bad["target_user_id"] == admin.user_id
    assert bad["reason_code"] == "wrong_password"
    assert bad["request_id"] == "req-login-bad"
    unknown = rows[2]
    assert unknown["reason_code"] == "unknown_user"
    assert unknown["target_user_id"] is None
    assert not any(name.startswith("domain.usermanagement.auth.") for name in pg_service["published"])


def test_logout_idempotent_and_unknown_token(pg_service) -> None:
    service: UserManagementService = pg_service["service"]
    migrator_dsn = pg_service["migrator_dsn"]
    issued = service.login_backend("opsadmin", "ops-secret-1", request_id="req-a")
    service.logout_backend(raw_token=issued.raw_token, request_id="req-logout")
    service.logout_backend(raw_token=issued.raw_token, request_id="req-logout-retry")
    with pytest.raises(SessionNotFoundError):
        service.logout_backend(raw_token="not-a-token", request_id="req-missing")

    logout_rows = [
        row for row in _read_audits(migrator_dsn) if row["event_type"] == "auth.logout.succeeded"
    ]
    assert len(logout_rows) == 1
    assert logout_rows[0]["request_id"] == "req-logout"
    assert logout_rows[0]["target_session_id"] == issued.session.session_id


def test_logout_all_password_create_access_expiry(pg_service) -> None:
    service: UserManagementService = pg_service["service"]
    migrator_dsn = pg_service["migrator_dsn"]
    admin = pg_service["admin"]

    first = service.login_backend("opsadmin", "ops-secret-1", request_id="req-1")
    second = service.login_backend("opsadmin", "ops-secret-1", request_id="req-2")
    ctx = service.resolve_session(first.raw_token, request_id="req-ctx")
    revoked = service.revoke_all_own_sessions(ctx)
    assert len(revoked) == 2

    # Fresh login for password change / admin actions.
    keep = service.login_backend("opsadmin", "ops-secret-1", request_id="req-keep")
    other = service.login_backend("opsadmin", "ops-secret-1", request_id="req-other")
    ctx2 = service.resolve_session(keep.raw_token, request_id="req-pw")
    service.change_own_password(ctx2, "ops-secret-2")

    created = service.create_user_as_admin(
        ctx2,
        "alice",
        "alice-secret-1",
        role="User",
        is_qmb=False,
        must_change_password=True,
    )
    patched = service.update_user_access_as_admin(
        ctx2,
        "alice",
        role="QMB",
        is_qmb=True,
        is_active=False,
    )
    assert patched.is_active is False

    expired = service.login_backend("opsadmin", "ops-secret-2", request_id="req-exp")
    past = _utc() - timedelta(hours=2)
    expired_at = past + timedelta(minutes=30)
    with psycopg.connect(pg_service["runtime_dsn"]) as conn:
        conn.execute("SET ROLE qmtool_runtime")
        conn.execute(
            """
            UPDATE usermanagement.sessions
            SET created_at = %s,
                last_seen_at = %s,
                expires_at = %s
            WHERE session_id = %s::uuid
            """,
            (past, past, expired_at, expired.session.session_id),
        )
        conn.commit()
    with pytest.raises(ExpiredSessionError):
        service.resolve_session(expired.raw_token, request_id="req-expired")
    with pytest.raises(ExpiredSessionError):
        service.resolve_session(expired.raw_token, request_id="req-expired-2")

    rows = _read_audits(migrator_dsn)
    by_type = {}
    for row in rows:
        by_type.setdefault(row["event_type"], []).append(row)

    logout_all = by_type["auth.logout_all.succeeded"][-1]
    assert logout_all["affected_session_count"] == 2
    assert logout_all["actor_user_id"] == admin.user_id

    password = by_type["user.password_changed"][-1]
    assert password["actor_user_id"] == admin.user_id
    assert password["target_user_id"] == admin.user_id
    assert password["must_change_password_after"] is False

    created_row = by_type["user.created"][-1]
    assert created_row["actor_user_id"] == admin.user_id
    assert created_row["target_user_id"] == created.user_id
    assert created_row["actor_user_id"] != created.user_id

    access = by_type["user.access_changed"][-1]
    assert access["changed_fields"] == ["role", "is_qmb", "is_active"]
    assert access["role_before"] == "User"
    assert access["role_after"] == "QMB"
    assert access["is_active_before"] is True
    assert access["is_active_after"] is False
    assert access["affected_session_count"] == 0
    assert access["actor_user_id"] == admin.user_id

    expired_rows = by_type["auth.session.expired"]
    assert len(expired_rows) == 1
    assert expired_rows[0]["actor_kind"] == "system"
    assert expired_rows[0]["system_actor"] == "qmtool.session-expiry"
    assert expired_rows[0]["target_session_id"] == expired.session.session_id

    assert "domain.usermanagement.user.created.v1" not in pg_service["published"]
    assert "domain.usermanagement.user.password_changed.v1" not in pg_service["published"]
    del other  # created only to be revoked by password change


def test_missing_insert_privilege_rolls_back_login(pg_service) -> None:
    service: UserManagementService = pg_service["service"]
    migrator_dsn = pg_service["migrator_dsn"]
    admin_dsn = pg_service["admin_dsn"]
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("REVOKE INSERT ON usermanagement.audit_events FROM qmtool_runtime")

    before_sessions = 0
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        before_sessions = int(
            conn.execute("SELECT COUNT(*) FROM usermanagement.sessions").fetchone()[0]
        )

    with pytest.raises(AuditUnavailableError):
        service.login_backend("opsadmin", "ops-secret-1", request_id="req-fail")

    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        after_sessions = int(
            conn.execute("SELECT COUNT(*) FROM usermanagement.sessions").fetchone()[0]
        )
        audits = int(
            conn.execute("SELECT COUNT(*) FROM usermanagement.audit_events").fetchone()[0]
        )
    assert after_sessions == before_sessions
    assert audits == 0


def test_http_login_writes_audit_and_body_cannot_set_actor(tmp_path, monkeypatch) -> None:
    env = _prepare_or_skip()
    admin_dsn = env.admin_dsn
    migrator_dsn = env.migrator_dsn
    runtime_dsn = env.runtime_dsn
    try:
        pgs.migrate_usermanagement_schema(migrator_dsn)
        monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
        monkeypatch.setenv("QMTOOL_LICENSE_MODE", "dev")
        monkeypatch.setenv("QMTOOL_PG_DSN", runtime_dsn)
        monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "opsadmin")
        monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "ops-secret-1")
        container = build_platform_ports(fail_closed_license=True)
        container.register_port("usermanagement_postgres_dsn", runtime_dsn)
        wire_backend_usermanagement(container)
        client = TestClient(create_app(container))

        login = client.post(
            "/auth/login",
            json={
                "username": "opsadmin",
                "password": "ops-secret-1",
                "actor_user_id": "forged",
            },
            headers={"X-Request-ID": "http-login-1"},
        )
        assert login.status_code == 200
        token = login.json()["token"]
        assert set(login.json()) == {"token"}

        change = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {token}", "X-Request-ID": "http-pw"},
            json={"new_password": "ops-secret-2"},
        )
        assert change.status_code == 204

        rows = _read_audits(migrator_dsn)
        login_row = next(row for row in rows if row["event_type"] == "auth.login.succeeded")
        assert login_row["request_id"] == "http-login-1"
        assert login_row["actor_kind"] == "user"
        assert "forged" not in str(login_row)
        for row in rows:
            blob = str(row)
            for secret in (token, "ops-secret-1", "ops-secret-2", "opsadmin"):
                assert secret not in blob
    finally:
        cleanup_live_environment(admin_dsn=admin_dsn)


def test_http_login_returns_503_and_rolls_back_when_audit_is_unavailable(
    tmp_path,
    monkeypatch,
) -> None:
    env = _prepare_or_skip()
    admin_dsn = env.admin_dsn
    migrator_dsn = env.migrator_dsn
    runtime_dsn = env.runtime_dsn
    try:
        pgs.migrate_usermanagement_schema(migrator_dsn)
        monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
        monkeypatch.setenv("QMTOOL_LICENSE_MODE", "dev")
        monkeypatch.setenv("QMTOOL_PG_DSN", runtime_dsn)
        monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "opsadmin")
        monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "ops-secret-1")
        container = build_platform_ports(fail_closed_license=True)
        container.register_port("usermanagement_postgres_dsn", runtime_dsn)
        wire_backend_usermanagement(container)
        client = TestClient(create_app(container))

        with psycopg.connect(migrator_dsn) as conn:
            conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
            before_sessions = int(
                conn.execute("SELECT COUNT(*) FROM usermanagement.sessions").fetchone()[0]
            )
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute("REVOKE INSERT ON usermanagement.audit_events FROM qmtool_runtime")

        response = client.post(
            "/auth/login",
            json={"username": "opsadmin", "password": "ops-secret-1"},
            headers={"X-Request-ID": "http-audit-unavailable"},
        )

        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "unavailable"
        with psycopg.connect(migrator_dsn) as conn:
            conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
            after_sessions = int(
                conn.execute("SELECT COUNT(*) FROM usermanagement.sessions").fetchone()[0]
            )
        assert after_sessions == before_sessions
    finally:
        cleanup_live_environment(admin_dsn=admin_dsn)


def test_create_user_audit_actor_is_admin_not_target(pg_service) -> None:
    service: UserManagementService = pg_service["service"]
    admin = pg_service["admin"]
    issued = service.login_backend("opsadmin", "ops-secret-1", request_id="req")
    ctx = issue_user_context(
        user_id=admin.user_id,
        session_id=issued.session.session_id,
        request_id="req-create",
        username=admin.username,
        global_roles={"ADMIN"},
        is_qmb=False,
        authenticated_at=issued.session.created_at,
    )
    created = service.create_user_as_admin(ctx, "carol", "carol-secret-1")
    row = next(
        r for r in _read_audits(pg_service["migrator_dsn"]) if r["event_type"] == "user.created"
    )
    assert row["actor_user_id"] == admin.user_id
    assert row["target_user_id"] == created.user_id
    assert row["actor_user_id"] != row["target_user_id"]
