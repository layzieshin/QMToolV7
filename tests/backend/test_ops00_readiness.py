"""OPS00-F HTTP liveness vs ops readiness."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.health import build_readiness_report
from qm_platform.runtime.maintenance import enter_maintenance
from qm_platform.runtime.operation_lock import operation_lock_path
from qm_platform.runtime.paths import resolve_home_path
from qm_platform.settings.testing import build_settings_service_for_tests
from src.backend.api import create_app
from src.backend.bootstrap import BackendBootstrapError
from interfaces.cli.main import _build_parser


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


def _writable_blob_root(tmp_path: Path) -> None:
    resolve_home_path(tmp_path, "storage/platform/blobs").mkdir(parents=True, exist_ok=True)


def _missing_dsn() -> str:
    raise BackendBootstrapError("dsn missing")


def test_health_stays_ok_when_ready_is_not(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    client = TestClient(create_app(_minimal_container(tmp_path)))
    monkeypatch.setattr("src.backend.api.resolve_usermanagement_postgres_dsn", _missing_dsn)

    health = client.get("/health")
    ready = client.get("/ready")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 503
    body = ready.json()
    assert body["ready"] is False
    assert body["checks"]["postgres"] == "missing_dsn"
    assert body["checks"]["blob_root"] == "missing"
    assert body["checks"]["migrations"] == "not_checked"


def test_ready_reports_writable_blob_and_missing_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _writable_blob_root(tmp_path)
    report = build_readiness_report(app_home=tmp_path, postgres_dsn=None)
    assert report.ready is False
    assert report.checks["blob_root"] == "ok"
    assert report.checks["postgres"] == "missing_dsn"
    assert report.checks["maintenance"] == "ok"
    assert report.checks["update_rehearsal"] == "ok"
    assert report.checks["operation_lock"] == "ok"


def test_ready_false_during_maintenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _writable_blob_root(tmp_path)
    enter_maintenance(tmp_path)
    monkeypatch.setattr("src.backend.api.resolve_usermanagement_postgres_dsn", _missing_dsn)
    client = TestClient(create_app(_minimal_container(tmp_path)))

    health = client.get("/health")
    ready = client.get("/ready")
    assert health.status_code == 200
    assert ready.status_code == 503
    assert ready.json()["checks"]["maintenance"] == "active"
    assert ready.json().get("detail", {}).get("error") != "maintenance_mode"


def test_ready_false_when_candidate_staged(tmp_path: Path) -> None:
    _writable_blob_root(tmp_path)
    state_dir = resolve_home_path(tmp_path, "maintenance")
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "rehearsal_state.json").write_text(
        '{"phase": "candidate_staged", "backup_path": "x"}',
        encoding="utf-8",
    )
    report = build_readiness_report(app_home=tmp_path, postgres_dsn=None)
    assert report.checks["update_rehearsal"] == "candidate_staged"
    assert report.ready is False


@pytest.mark.parametrize(
    "state",
    [
        {"phase": "future_phase"},
        {"phase": "candidate_staged"},
        {"phase": "aborted"},
    ],
)
def test_ready_false_when_rehearsal_state_is_unknown_or_incomplete(
    tmp_path: Path, state: dict[str, str]
) -> None:
    _writable_blob_root(tmp_path)
    state_dir = resolve_home_path(tmp_path, "maintenance")
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "rehearsal_state.json").write_text(
        json.dumps(state),
        encoding="utf-8",
    )
    report = build_readiness_report(app_home=tmp_path, postgres_dsn=None)
    assert report.checks["update_rehearsal"] == "invalid_state"
    assert report.ready is False


def test_ready_false_when_rehearsal_state_path_is_not_a_regular_file(
    tmp_path: Path,
) -> None:
    _writable_blob_root(tmp_path)
    state_path = resolve_home_path(tmp_path, "maintenance/rehearsal_state.json")
    state_path.mkdir(parents=True)
    report = build_readiness_report(app_home=tmp_path, postgres_dsn=None)
    assert report.checks["update_rehearsal"] == "invalid_state"
    assert report.ready is False


def test_ready_false_when_operation_lock_held(tmp_path: Path) -> None:
    _writable_blob_root(tmp_path)
    lock_path = operation_lock_path(tmp_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("held", encoding="utf-8")
    report = build_readiness_report(app_home=tmp_path, postgres_dsn=None)
    assert report.checks["operation_lock"] == "held"
    assert report.ready is False


def test_ready_false_when_blob_root_is_a_file(tmp_path: Path) -> None:
    blob = resolve_home_path(tmp_path, "storage/platform/blobs")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_text("not-a-dir", encoding="utf-8")
    report = build_readiness_report(app_home=tmp_path, postgres_dsn=None)
    assert report.checks["blob_root"] == "not_a_directory"
    assert report.ready is False


def test_ready_body_does_not_leak_dsn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _writable_blob_root(tmp_path)
    secret = "postgresql://secretuser:super-secret-pass@127.0.0.1:1/qmtool"
    monkeypatch.setattr("src.backend.api.resolve_usermanagement_postgres_dsn", lambda: secret)
    client = TestClient(create_app(_minimal_container(tmp_path)))
    ready = client.get("/ready")
    text = ready.text.casefold()
    assert "super-secret-pass" not in text
    assert "secretuser" not in text
    assert "postgresql://" not in text
    assert ready.status_code == 503
    assert ready.json()["checks"]["postgres"] == "unreachable"


class _FakePgConn:
    def __enter__(self) -> "_FakePgConn":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, *_args: object, **_kwargs: object) -> None:
        return None


def test_ready_uses_assert_runtime_schema_ready_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _writable_blob_root(tmp_path)
    called: dict[str, object] = {}

    def _connect(*_args: object, **_kwargs: object) -> _FakePgConn:
        called["connect"] = True
        return _FakePgConn()

    def _ready(dsn: str, **_kwargs: object) -> int:
        called["dsn"] = dsn
        return 6

    monkeypatch.setattr("qm_platform.runtime.health.psycopg.connect", _connect)
    monkeypatch.setattr(
        "qm_platform.runtime.health.assert_runtime_schema_ready",
        _ready,
    )
    report = build_readiness_report(
        app_home=tmp_path,
        postgres_dsn="postgresql://u@127.0.0.1:5432/db",
    )
    assert called.get("connect") is True
    assert called.get("dsn") == "postgresql://u@127.0.0.1:5432/db"
    assert report.checks["postgres"] == "ok"
    assert report.checks["migrations"] == "ok"
    assert report.ready is True


def test_ready_false_when_schema_owner_fails_without_leaking_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _writable_blob_root(tmp_path)
    secret = "postgresql://secretuser:super-secret-pass@127.0.0.1:5432/qmtool"

    def _connect(*_args: object, **_kwargs: object) -> _FakePgConn:
        return _FakePgConn()

    def _fail(dsn: str, **_kwargs: object) -> int:
        raise RuntimeError(f"missing intermediate migration {dsn}")

    monkeypatch.setattr("qm_platform.runtime.health.psycopg.connect", _connect)
    monkeypatch.setattr(
        "qm_platform.runtime.health.assert_runtime_schema_ready",
        _fail,
    )
    monkeypatch.setattr(
        "src.backend.api.resolve_usermanagement_postgres_dsn",
        lambda: secret,
    )
    report = build_readiness_report(app_home=tmp_path, postgres_dsn=secret)
    assert report.ready is False
    assert report.checks["postgres"] == "ok"
    assert report.checks["migrations"] == "failed"
    client = TestClient(create_app(_minimal_container(tmp_path)))
    ready = client.get("/ready")
    text = ready.text.casefold()
    assert "super-secret-pass" not in text
    assert "secretuser" not in text
    assert "postgresql://" not in text
    assert "missing intermediate" not in text
    assert ready.status_code == 503
    assert ready.json()["ready"] is False
    assert ready.json()["checks"]["migrations"] == "failed"
    assert "detail" not in ready.json() or "postgresql://" not in str(ready.json()).casefold()


def test_health_and_logs_backup_parsers_remain_registered_once() -> None:
    parser = _build_parser()
    health = parser.parse_args(["health"])
    logs = parser.parse_args(["logs-backup"])
    assert health.command == "health"
    assert logs.command == "logs-backup"
    with pytest.raises(SystemExit):
        parser.parse_args(["ops", "diagnostic-bundle"])


def test_ready_is_unauthenticated_in_openapi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    client = TestClient(create_app(_minimal_container(tmp_path)))
    schema = client.get("/openapi.json").json()
    ready = schema["paths"]["/ready"]["get"]
    assert ready.get("security") in (None, [])
    health = schema["paths"]["/health"]["get"]
    assert health.get("security") in (None, [])
