"""OPS00-A/B uninstalled backend service host lifecycle and production negatives."""
from __future__ import annotations

import importlib
import os
import socket
import sys
import uuid
from pathlib import Path

import pytest

from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.testing import build_settings_service_for_tests
from qm_platform.blob.backup_orchestrator import (
    create_host_running_marker_exclusive,
    host_running_marker_path,
    write_host_running_marker,
)
from src.backend.api import create_app
from src.backend.bootstrap import BackendBootstrapError, build_backend_container
from src.backend.service_host import (
    ServiceHost,
    ServiceHostState,
    probe_health,
    validate_service_host_config,
)
from tests.backend.test_ops00_https_contract import (
    ssl_context_trusting,
    write_ephemeral_self_signed_pem,
)


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


def test_service_host_module_has_no_windows_service_imports() -> None:
    module_names = (
        "win32service",
        "win32serviceutil",
        "servicemanager",
        "pywintypes",
        "nssm",
    )
    for name in module_names:
        assert name not in sys.modules, f"unexpected import of {name!r} before service_host load"
    importlib.import_module("src.backend.service_host")
    for name in module_names:
        assert name not in sys.modules, f"service_host must not import {name!r}"


def test_service_host_start_status_graceful_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )

    host = ServiceHost()
    assert host.status().state == ServiceHostState.STOPPED

    host.start(timeout=15.0)
    try:
        status = host.status()
        assert status.state == ServiceHostState.RUNNING
        marker = host_running_marker_path(tmp_path)
        assert marker.is_file()
        stored = host._host_running_marker_token
        assert stored is not None
        assert stored == marker.read_text(encoding="ascii")
        assert stored.split(":", 1)[0] == str(os.getpid())
        assert len(stored.split(":", 1)[1]) >= 32
        assert status.bind_host == "127.0.0.1"
        assert status.bind_port > 0
        assert status.https_enabled is False
        assert host.is_serving()

        payload = probe_health(status.bind_host, status.bind_port)
        assert payload == {"status": "ok", "service": "qmtool-backend"}
    finally:
        host.stop(timeout=15.0)

    assert host.status().state == ServiceHostState.STOPPED
    assert not host.is_serving()
    assert not host_running_marker_path(tmp_path).exists()


def test_production_missing_dsn_fail_closed_via_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cert_path, key_path = write_ephemeral_self_signed_pem(tmp_path)

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert_path))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key_path))
    monkeypatch.setenv("QMTOOL_LICENSE_MODE", "strict")
    monkeypatch.delenv("QMTOOL_PG_DSN", raising=False)
    monkeypatch.delenv("QMTOOL_PG_HOST", raising=False)
    monkeypatch.delenv("QMTOOL_PG_DATABASE", raising=False)
    monkeypatch.delenv("QMTOOL_PG_USER", raising=False)
    monkeypatch.delenv("QMTOOL_PG_PASSWORD", raising=False)
    monkeypatch.setattr("src.backend.bootstrap._load_dotenv", lambda path=None: None)

    validate_service_host_config()
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="no SQLite fallback"):
        host.start(timeout=5.0)
    assert host.status().state == ServiceHostState.STOPPED


def test_production_missing_tls_paths_rejected_before_serve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.delenv("QMTOOL_TLS_CERT_FILE", raising=False)
    monkeypatch.delenv("QMTOOL_TLS_KEY_FILE", raising=False)

    with pytest.raises(BackendBootstrapError, match="TLS"):
        validate_service_host_config()

    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="TLS"):
        host.start(timeout=5.0)
    assert host.status().state == ServiceHostState.STOPPED
    assert not host.is_serving()


def test_production_missing_tls_files_rejected_before_serve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(tmp_path / "missing-cert.pem"))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(tmp_path / "missing-key.pem"))

    with pytest.raises(BackendBootstrapError, match="readable TLS"):
        validate_service_host_config()


def test_production_invalid_pem_rejected_before_serve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("cert", encoding="utf-8")
    key.write_text("key", encoding="utf-8")

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key))

    validate_service_host_config()
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="not valid PEM"):
        host.start(timeout=5.0)
    assert host.status().state == ServiceHostState.STOPPED
    assert not host.is_serving()


def test_production_unwritable_home_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = tmp_path / "blocked-home"
    blocked.write_text("not-a-directory", encoding="utf-8")

    cert_path, key_path = write_ephemeral_self_signed_pem(tmp_path)

    monkeypatch.setenv("QMTOOL_HOME", str(blocked))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert_path))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key_path))

    with pytest.raises(BackendBootstrapError, match="not writable"):
        validate_service_host_config()


def test_create_app_without_service_host_unchanged(tmp_path: Path) -> None:
    container = _minimal_container(tmp_path)
    from fastapi.testclient import TestClient

    client = TestClient(create_app(container))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_build_backend_container_not_called_when_config_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.delenv("QMTOOL_TLS_CERT_FILE", raising=False)

    called = {"value": False}

    def _fail_if_called() -> RuntimeContainer:
        called["value"] = True
        return build_backend_container()

    monkeypatch.setattr("src.backend.service_host.build_backend_container", _fail_if_called)
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError):
        host.start(timeout=5.0)
    assert called["value"] is False


def test_production_valid_pem_serves_https_after_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cert_path, key_path = write_ephemeral_self_signed_pem(tmp_path)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert_path))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )

    validate_service_host_config()
    host = ServiceHost()
    host.start(timeout=20.0)
    try:
        status = host.status()
        assert status.https_enabled is True
        ctx = ssl_context_trusting(cert_path)
        payload = probe_health(
            status.bind_host,
            status.bind_port,
            use_https=True,
            ssl_context=ctx,
        )
        assert payload == {"status": "ok", "service": "qmtool-backend"}
    finally:
        host.stop(timeout=15.0)


@pytest.mark.parametrize("license_mode", ["dev", "auto"])
def test_production_dev_or_auto_license_mode_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, license_mode: str
) -> None:
    cert_path, key_path = write_ephemeral_self_signed_pem(tmp_path)

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert_path))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key_path))
    monkeypatch.setenv("QMTOOL_LICENSE_MODE", license_mode)
    monkeypatch.setenv("QMTOOL_PG_DSN", "postgresql://u:p@127.0.0.1:5432/db")
    monkeypatch.setattr("src.backend.bootstrap._load_dotenv", lambda path=None: None)

    validate_service_host_config()
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="dev\\|auto is not allowed"):
        host.start(timeout=5.0)
    assert host.status().state == ServiceHostState.STOPPED
    assert not host.is_serving()


class _NonTerminatingThread:
    """Stub serve thread that never exits (stop-timeout regression)."""

    def is_alive(self) -> bool:
        return True

    def join(self, timeout: float | None = None) -> None:
        return


def test_stop_timeout_does_not_report_stopped_while_thread_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )

    host = ServiceHost()
    host.start(timeout=15.0)
    assert host.status().state == ServiceHostState.RUNNING

    real_thread = host._thread
    server = host._server
    host._thread = _NonTerminatingThread()
    try:
        with pytest.raises(RuntimeError, match="stop timed out"):
            host.stop(timeout=0.1)

        assert host.status().state == ServiceHostState.STOPPING
        assert host.status().state != ServiceHostState.STOPPED
    finally:
        host._thread = real_thread
        if server is not None:
            server.should_exit = True
        if real_thread is not None:
            real_thread.join(timeout=15.0)


def _occupy_port() -> tuple[socket.socket, int]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    return sock, int(sock.getsockname()[1])


def test_failed_second_start_does_not_remove_foreign_running_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    write_host_running_marker(tmp_path)
    marker = host_running_marker_path(tmp_path)
    original = marker.read_bytes()
    called = {"bootstrap": False}

    def _must_not_bootstrap():
        called["bootstrap"] = True
        raise AssertionError("bootstrap must not run while a foreign marker is present")

    monkeypatch.setattr("src.backend.service_host.build_backend_container", _must_not_bootstrap)
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="host running marker"):
        host.start(timeout=5.0)
    assert called["bootstrap"] is False
    assert marker.read_bytes() == original
    assert host.status().state == ServiceHostState.STOPPED


def test_bootstrap_error_does_not_remove_foreign_running_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    write_host_running_marker(tmp_path)
    marker = host_running_marker_path(tmp_path)
    original = marker.read_bytes()
    monkeypatch.setattr(
        "src.backend.service_host.is_host_running_marker_present",
        lambda app_home=None: False,
    )
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: (_ for _ in ()).throw(BackendBootstrapError("bootstrap exploded")),
    )
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="bootstrap exploded"):
        host.start(timeout=5.0)
    assert marker.read_bytes() == original


def test_bind_failure_does_not_remove_foreign_running_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    occupied, bind_port = _occupy_port()
    try:
        monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
        monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
        monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))
        write_host_running_marker(tmp_path)
        marker = host_running_marker_path(tmp_path)
        original = marker.read_bytes()
        monkeypatch.setattr(
            "src.backend.service_host.is_host_running_marker_present",
            lambda app_home=None: False,
        )
        monkeypatch.setattr(
            "src.backend.service_host.build_backend_container",
            lambda: _minimal_container(tmp_path),
        )
        host = ServiceHost()
        with pytest.raises((RuntimeError, BackendBootstrapError)):
            host.start(timeout=3.0)
        assert marker.read_bytes() == original
    finally:
        occupied.close()


def test_stop_does_not_remove_foreign_running_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    write_host_running_marker(tmp_path)
    marker = host_running_marker_path(tmp_path)
    original = marker.read_bytes()
    host = ServiceHost()
    host.stop(timeout=1.0)
    assert marker.read_bytes() == original


def test_stop_does_not_delete_replaced_foreign_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: _minimal_container(tmp_path),
    )
    host = ServiceHost()
    host.start(timeout=15.0)
    marker = host_running_marker_path(tmp_path)
    assert marker.is_file()
    foreign = b"foreign-replacement-marker"
    marker.write_bytes(foreign)
    try:
        host.stop(timeout=15.0)
        assert marker.read_bytes() == foreign
    finally:
        if host.status().state.name != "STOPPED":
            host._owns_host_running_marker = False
            host._host_running_marker_token = None
            host.stop(timeout=15.0)


def test_exclusive_marker_creates_distinct_instance_tokens(tmp_path: Path) -> None:
    token_a = create_host_running_marker_exclusive(tmp_path / "a")
    token_b = create_host_running_marker_exclusive(tmp_path / "b")
    assert token_a != token_b
    assert token_a.split(":", 1)[0] == str(os.getpid())
    assert token_b.split(":", 1)[0] == str(os.getpid())
    assert host_running_marker_path(tmp_path / "a").read_text(encoding="ascii") == token_a
    assert host_running_marker_path(tmp_path / "b").read_text(encoding="ascii") == token_b


def test_stop_does_not_delete_replaced_same_pid_different_instance_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: _minimal_container(tmp_path),
    )
    host = ServiceHost()
    host.start(timeout=15.0)
    marker = host_running_marker_path(tmp_path)
    owned = host._host_running_marker_token
    assert owned is not None
    replacement = f"{os.getpid()}:{uuid.uuid4().hex}"
    assert replacement != owned
    marker.write_text(replacement, encoding="ascii")
    try:
        host.stop(timeout=15.0)
        assert marker.read_text(encoding="ascii") == replacement
    finally:
        if host.status().state.name != "STOPPED":
            host._owns_host_running_marker = False
            host._host_running_marker_token = None
            host.stop(timeout=15.0)


def test_stop_uses_returned_create_token_not_reread_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: _minimal_container(tmp_path),
    )
    recorded: dict[str, str] = {}

    def _create_and_mutate(app_home=None) -> str:
        token = create_host_running_marker_exclusive(app_home)
        recorded["returned"] = token
        path = host_running_marker_path(tmp_path)
        path.write_text("mutated-after-create", encoding="ascii")
        recorded["file"] = path.read_text(encoding="ascii")
        return token

    monkeypatch.setattr(
        "src.backend.service_host.create_host_running_marker_exclusive",
        _create_and_mutate,
    )
    host = ServiceHost()
    host.start(timeout=15.0)
    try:
        assert host._host_running_marker_token == recorded["returned"]
        assert host._host_running_marker_token != recorded["file"]
        host.stop(timeout=15.0)
        assert host_running_marker_path(tmp_path).read_text(encoding="ascii") == "mutated-after-create"
    finally:
        if host.status().state.name != "STOPPED":
            host._owns_host_running_marker = False
            host._host_running_marker_token = None
            host.stop(timeout=15.0)
