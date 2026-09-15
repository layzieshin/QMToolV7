"""INT00 joint browser/PostgreSQL/HTTPS integration (test-only).

Orchestrates the unchanged production ServiceHost via ``python -m src.backend``
against guarded Slot-2 PostgreSQL, file-PEM HTTPS, built webclient/dist, and
real Chromium. It is not a product CLI, entrypoint, or alternate backend.
"""
from __future__ import annotations

import datetime
import ipaddress
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, TextIO

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from modules.documents import api as documents_api
from modules.registry import api as registry_api
from modules.signature import api as signature_api
from modules.usermanagement import api as usermanagement_api
from qm_platform.blob import is_host_running_marker_present
from src.backend import bootstrap as backend_bootstrap
from src.backend import service_host as service_host_mod
from src.backend.service_host import probe_health
from tests.acceptance.j04_m0_realprocess_harness import (
    backend_popen_creationflags,
    prepend_pythonpath,
    python_executable,
    redact_log_text,
    send_graceful_stop_signal,
    write_backend_sigbreak_startup,
)
from tests.postgres_destructive_guard import RESET_OPT_IN_VALUE, TEST_RESET_ENV
from tests.postgres_live_support import LivePostgresEnv, cleanup_live_environment

pytestmark = pytest.mark.postgres

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPO_ROOT / "build" / "ap-029-int00"
FORBIDDEN_BACKEND = "tests.backend.web00_browser_smoke_backend"
BOOTSTRAP_USERNAME = "opsadmin"
BOOTSTRAP_PASSWORD = "ops-secret-1"
LOGIN_PASSWORD = "ops-secret-2"
TRACKED_LICENSE = REPO_ROOT / "license" / "license.json"


def _evidence_dir() -> Path:
    raw = os.environ.get("QMTOOL_INT00_EVIDENCE_DIR", "").strip()
    if not raw:
        pytest.fail("QMTOOL_INT00_EVIDENCE_DIR is required for the INT00 joint test")
    path = Path(raw).expanduser().resolve()
    try:
        path.relative_to(EVIDENCE_ROOT.resolve())
    except ValueError:
        pytest.fail("INT00 evidence dir must resolve under build/ap-029-int00")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _allocate_ephemeral_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def _assert_port_free(host: str, port: int) -> None:
    if not _port_is_free(host, port):
        pytest.fail(
            f"refusing INT00 joint start: {host}:{port} is occupied by a foreign process"
        )


def _wait_port_free(host: str, port: int, *, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_is_free(host, port):
            return
        time.sleep(0.1)
    pytest.fail(f"INT00 ServiceHost port {host}:{port} still occupied after stop")


def _write_ephemeral_pems(target: Path) -> tuple[Path, Path]:
    target.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=2))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = target / "localhost.pem"
    key_path = target / "localhost-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _http_bytes(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=20, context=_ssl_context()) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


def _redact(text: str, extra_secrets: tuple[str, ...]) -> str:
    redacted = redact_log_text(text)
    for secret in extra_secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return redacted


def _write_redacted(path: Path, text: str, extra_secrets: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_redact(text, extra_secrets), encoding="utf-8")


def _stop_owned_process(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32" and proc.pid:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


_PRODUCTIVE_SERVICEHOST_STOP_SECONDS = 30.0
_BACKEND_GRACEFUL_STOP_TIMEOUT = 40.0
_MARKER_GONE_WAIT_SECONDS = 2.0


def _assert_host_marker_present(home: Path) -> None:
    if not is_host_running_marker_present(app_home=home):
        pytest.fail("production ServiceHost did not create a host-running marker")


def _wait_until_host_marker_gone(home: Path) -> bool:
    """Observe marker absence only. Never unlink, rmdir, or repair the marker."""
    deadline = time.monotonic() + _MARKER_GONE_WAIT_SECONDS
    while True:
        if not is_host_running_marker_present(app_home=home):
            return True
        if time.monotonic() >= deadline:
            return not is_host_running_marker_present(app_home=home)
        time.sleep(0.05)


def _start_backend_process(*, env: dict[str, str], log_handle: TextIO) -> subprocess.Popen[str]:
    popen_kwargs: dict[str, Any] = {
        "cwd": str(REPO_ROOT),
        "env": env,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "text": True,
    }
    creationflags = backend_popen_creationflags()
    if creationflags:
        popen_kwargs["creationflags"] = creationflags
    proc = subprocess.Popen([python_executable(), "-m", "src.backend"], **popen_kwargs)
    if proc.pid is None:
        pytest.fail("production ServiceHost subprocess did not receive a PID")
    return proc


def _write_graceful_stop_diagnosis(evidence: Path, payload: dict[str, Any]) -> None:
    allowed = {
        "signal",
        "outer_wait_budget_seconds",
        "productive_servicehost_stop_window_seconds",
        "shutdown_duration_seconds",
        "child_returncode",
        "fallback_used",
        "marker_present_after_exit",
    }
    body = {key: payload[key] for key in allowed}
    path = evidence / "graceful-stop-diagnosis.json"
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def _stop_backend_for_restart(
    proc: subprocess.Popen[str] | None,
    *,
    home: Path,
    evidence: Path,
) -> None:
    """Fail-closed graceful stop for the INT00 handshake restart.

    Outer wait is 40s: productive ServiceHost.stop() uses 30s, plus 10s process
    exit margin. Terminate/kill fallback must not count as a successful restart.
    The productive host marker must disappear through ServiceHost itself.
    """
    fallback_used = False
    signal_name = "none"
    started = time.monotonic()
    if proc is not None and proc.poll() is None:
        signal_name = send_graceful_stop_signal(proc)
        try:
            proc.wait(timeout=_BACKEND_GRACEFUL_STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            fallback_used = True
    elapsed = round(time.monotonic() - started, 3)
    returncode = None if proc is None else proc.poll()
    if proc is not None and returncode is None:
        fallback_used = True
    if returncode is not None:
        marker_present = not _wait_until_host_marker_gone(home)
    else:
        marker_present = is_host_running_marker_present(app_home=home)
    _write_graceful_stop_diagnosis(
        evidence,
        {
            "signal": signal_name,
            "outer_wait_budget_seconds": _BACKEND_GRACEFUL_STOP_TIMEOUT,
            "productive_servicehost_stop_window_seconds": _PRODUCTIVE_SERVICEHOST_STOP_SECONDS,
            "shutdown_duration_seconds": elapsed,
            "child_returncode": returncode,
            "fallback_used": fallback_used,
            "marker_present_after_exit": marker_present,
        },
    )
    if proc is not None and proc.poll() is None:
        _stop_owned_process(proc)
    if fallback_used:
        pytest.fail(
            f"backend graceful stop fallback to terminate/kill after {signal_name}; "
            "refusing restart"
        )
    if proc is not None and proc.poll() is None:
        pytest.fail("backend child still running after graceful stop; refusing restart")
    if returncode != 0:
        pytest.fail(
            f"backend graceful stop returned {returncode}; refusing restart"
        )
    if marker_present:
        pytest.fail(
            "backend host running marker still present after graceful stop; "
            "refusing restart over stale marker"
        )


def _wait_https_health(host: str, port: int, *, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = "not-started"
    while time.monotonic() < deadline:
        try:
            payload = probe_health(
                host,
                port,
                use_https=True,
                ssl_context=_ssl_context(),
                timeout=2.0,
            )
            if payload.get("status") == "ok":
                return
            last_error = repr(payload)
        except Exception as exc:  # noqa: BLE001
            last_error = type(exc).__name__
        time.sleep(0.25)
    pytest.fail(f"INT00 production ServiceHost health timed out ({last_error})")


def _provision_postgres(live: LivePostgresEnv) -> None:
    usermanagement_api.migrate_postgres_schema(live.migrator_dsn)
    documents_api.provision_postgres_schema(live.admin_dsn)
    documents_api.migrate_postgres_schema(live.migrator_dsn)
    registry_api.provision_postgres_schema(live.admin_dsn)
    registry_api.migrate_postgres_schema(live.migrator_dsn)
    signature_api.provision_postgres_schema(live.admin_dsn)
    signature_api.migrate_postgres_schema(live.migrator_dsn)
    documents_api.seed_postgres_workflow_profiles(live.runtime_dsn)


def _copy_tracked_license(home: Path) -> None:
    if not TRACKED_LICENSE.is_file():
        pytest.fail("tracked production licence license/license.json is missing")
    destination = home / "license"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TRACKED_LICENSE, destination / "license.json")


def _complete_bootstrap_password_change(base_url: str) -> None:
    status, body = _http_bytes(
        "POST",
        f"{base_url}/api/v1/auth/token",
        body={"username": BOOTSTRAP_USERNAME, "password": BOOTSTRAP_PASSWORD},
    )
    if status != 200:
        pytest.fail(f"bootstrap token login failed: HTTP {status}")
    payload = json.loads(body.decode("utf-8"))
    token = str(payload.get("token") or "")
    if not token:
        pytest.fail("bootstrap token login returned no token")
    changed, _changed_body = _http_bytes(
        "POST",
        f"{base_url}/api/v1/auth/change-password",
        body={"new_password": LOGIN_PASSWORD},
        headers={"Authorization": f"Bearer {token}"},
    )
    if changed != 204:
        pytest.fail(f"bootstrap password change failed: HTTP {changed}")


def test_int00_joint_browser_postgres_https_restart(
    monkeypatch: pytest.MonkeyPatch,
    live_postgres_env: LivePostgresEnv,
) -> None:
    if os.environ.get(TEST_RESET_ENV) != RESET_OPT_IN_VALUE:
        pytest.fail(
            "INT00 joint test can only succeed after scripts/run_postgres_live_tests.py "
            "Slot-2 preflight and child-only RESET injection"
        )
    assert FORBIDDEN_BACKEND not in sys.modules
    assert service_host_mod.build_backend_container is backend_bootstrap.build_backend_container

    evidence = _evidence_dir()
    node_exe = os.environ.get("QMTOOL_INT00_NODE_EXE", "").strip()
    if not node_exe or not Path(node_exe).is_file():
        pytest.fail("QMTOOL_INT00_NODE_EXE must point to the pinned Node 20.11 executable")
    dist_dir = REPO_ROOT / "webclient" / "dist"
    if not (dist_dir / "index.html").is_file():
        pytest.fail("webclient/dist is missing; npm run build must precede the joint gate")

    extra_secrets = (
        BOOTSTRAP_PASSWORD,
        LOGIN_PASSWORD,
        live_postgres_env.runtime_password,
        live_postgres_env.migrator_password,
        live_postgres_env.runtime_dsn,
        live_postgres_env.migrator_dsn,
        live_postgres_env.admin_dsn,
    )

    home = evidence / "qmtool-home"
    tls_dir = evidence / "tls"
    home.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = _write_ephemeral_pems(tls_dir)
    _copy_tracked_license(home)
    _provision_postgres(live_postgres_env)

    bind_host = "127.0.0.1"
    bind_port = _allocate_ephemeral_port()
    _assert_port_free(bind_host, bind_port)
    base_url = f"https://{bind_host}:{bind_port}"

    monkeypatch.setenv("QMTOOL_HOME", str(home))
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("QMTOOL_LICENSE_MODE", "production")
    monkeypatch.setenv("QMTOOL_PG_DSN", live_postgres_env.runtime_dsn)
    monkeypatch.setenv("QMTOOL_TLS_CERT_FILE", str(cert_path))
    monkeypatch.setenv("QMTOOL_TLS_KEY_FILE", str(key_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", bind_host)
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))
    monkeypatch.setenv("QMTOOL_WEBCLIENT_DIST", str(dist_dir))
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", BOOTSTRAP_USERNAME)
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", BOOTSTRAP_PASSWORD)
    monkeypatch.setenv("QMTOOL_UVICORN_LOG_LEVEL", "warning")
    monkeypatch.delenv("QMTOOL_PG_HOST", raising=False)
    monkeypatch.delenv("QMTOOL_PG_DATABASE", raising=False)
    monkeypatch.delenv("QMTOOL_PG_USER", raising=False)
    monkeypatch.delenv("QMTOOL_PG_PASSWORD", raising=False)

    playwright_cli = REPO_ROOT / "webclient" / "node_modules" / "@playwright" / "test" / "cli.js"
    if not playwright_cli.is_file():
        pytest.fail("Playwright CLI is missing; npm ci must precede the joint gate")

    backend_env = os.environ.copy()
    backend_env["PYTHONUNBUFFERED"] = "1"
    existing_pythonpath = backend_env.get("PYTHONPATH", "")
    backend_env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(REPO_ROOT), existing_pythonpath) if part
    )
    if sys.platform == "win32":
        startup = write_backend_sigbreak_startup(evidence)
        backend_env["PYTHONPATH"] = prepend_pythonpath(
            backend_env.get("PYTHONPATH", ""),
            startup,
        )

    playwright: subprocess.Popen[str] | None = None
    backend: subprocess.Popen[str] | None = None
    stdout_handle: TextIO | None = None
    stderr_handle: TextIO | None = None
    backend_log_handle: TextIO | None = None
    stdout_path = evidence / "playwright-stdout.log"
    stderr_path = evidence / "playwright-stderr.log"
    backend_log_path = evidence / "backend-stdout.log"
    try:
        backend_log_handle = backend_log_path.open("w", encoding="utf-8")
        backend = _start_backend_process(env=backend_env, log_handle=backend_log_handle)
        _wait_https_health(bind_host, bind_port)
        _assert_host_marker_present(home)
        _complete_bootstrap_password_change(base_url)

        child_env = {
            key: value
            for key, value in os.environ.items()
            if "DSN" not in key.upper()
            and not key.upper().endswith("PASSWORD")
            and "SECRET" not in key.upper()
        }
        child_env["QMTOOL_INT00_JOINT"] = "1"
        child_env["QMTOOL_INT00_USERNAME"] = BOOTSTRAP_USERNAME
        child_env["QMTOOL_INT00_PASSWORD"] = LOGIN_PASSWORD
        child_env["QMTOOL_INT00_EVIDENCE_DIR"] = str(evidence)
        child_env["WEB00_SMOKE_BASE_URL"] = base_url
        child_env["WEB00_SMOKE_EVIDENCE_DIR"] = str(evidence)
        child_env["QMTOOL_INT00_NODE_EXE"] = node_exe

        stdout_handle = stdout_path.open("w", encoding="utf-8")
        stderr_handle = stderr_path.open("w", encoding="utf-8")
        playwright = subprocess.Popen(
            [
                node_exe,
                str(playwright_cli),
                "test",
                "e2e/int00-joint-integration.spec.ts",
            ],
            cwd=str(REPO_ROOT / "webclient"),
            env=child_env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )

        restart_request = evidence / "restart-request.json"
        restart_complete = evidence / "restart-complete.json"
        deadline = time.monotonic() + 120.0
        while not restart_request.is_file():
            rc = playwright.poll()
            if rc is not None:
                pytest.fail(f"Playwright exited {rc} before host restart handshake")
            if backend is None or backend.poll() is not None:
                pytest.fail("production ServiceHost exited during browser run")
            if time.monotonic() > deadline:
                pytest.fail("timeout waiting for Playwright restart request")
            time.sleep(0.25)

        _stop_backend_for_restart(backend, home=home, evidence=evidence)
        backend = None
        _wait_port_free(bind_host, bind_port)
        _assert_port_free(bind_host, bind_port)
        backend = _start_backend_process(env=backend_env, log_handle=backend_log_handle)
        _wait_https_health(bind_host, bind_port)
        _assert_host_marker_present(home)
        restart_complete.write_text(
            json.dumps({"phase": "host-restarted", "port": bind_port}, indent=2) + "\n",
            encoding="utf-8",
        )

        try:
            playwright_rc = playwright.wait(timeout=90)
        except subprocess.TimeoutExpired:
            pytest.fail("timeout waiting for Playwright to finish after host restart")
        if playwright_rc != 0:
            pytest.fail(f"INT00 Playwright joint spec failed with exit {playwright_rc}")
    finally:
        _stop_owned_process(playwright)
        _stop_owned_process(backend)
        if stdout_handle is not None:
            stdout_handle.close()
        if stderr_handle is not None:
            stderr_handle.close()
        if backend_log_handle is not None:
            backend_log_handle.close()
        _wait_port_free(bind_host, bind_port, timeout=10.0)
        for name in ("platform.log", "audit.log"):
            source = home / "storage" / "platform" / "logs" / name
            if source.is_file():
                original = source.read_text(encoding="utf-8", errors="replace")
                _write_redacted(
                    evidence / "redacted-host-logs" / name,
                    original,
                    extra_secrets,
                )
        for raw_log in (stdout_path, stderr_path, backend_log_path):
            if raw_log.is_file():
                original = raw_log.read_text(encoding="utf-8", errors="replace")
                redacted = _redact(original, extra_secrets)
                raw_log.write_text(redacted, encoding="utf-8")
                _write_redacted(
                    evidence / "redacted-playwright" / raw_log.name,
                    original,
                    extra_secrets,
                )
        cleanup_live_environment(admin_dsn=live_postgres_env.admin_dsn)

    assert FORBIDDEN_BACKEND not in sys.modules
    assert service_host_mod.build_backend_container is backend_bootstrap.build_backend_container
    json_report = evidence / "browser-smoke-playwright.json"
    assert json_report.is_file(), "Playwright JSON reporter output is missing"
    redacted_platform = evidence / "redacted-host-logs" / "platform.log"
    assert redacted_platform.is_file() or (evidence / "redacted-host-logs" / "audit.log").is_file()
    for candidate in (
        redacted_platform,
        evidence / "redacted-host-logs" / "audit.log",
        evidence / "redacted-playwright" / "backend-stdout.log",
    ):
        if not candidate.is_file():
            continue
        leaked = candidate.read_text(encoding="utf-8", errors="replace")
        for secret in extra_secrets:
            if secret:
                assert secret not in leaked
