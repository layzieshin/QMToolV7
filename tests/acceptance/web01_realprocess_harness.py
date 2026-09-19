"""WEB01 real-process orchestration (test-only).

Starts production ``python -m src.backend`` with HTTPS, built ``webclient/dist``,
isolated ``QMTOOL_HOME``, and real Chromium. Not a product entrypoint.
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
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from modules.documents import api as documents_api
from modules.registry import api as registry_api
from modules.signature import api as signature_api
from modules.usermanagement import api as usermanagement_api
from qm_platform.blob import is_host_running_marker_present
from src.backend.service_host import probe_health
from tests.acceptance.j04_m0_realprocess_harness import (
    backend_popen_creationflags,
    prepend_pythonpath,
    python_executable,
    redact_log_text,
    send_graceful_stop_signal,
    write_backend_sigbreak_startup,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPO_ROOT / "build" / "ap-029-web01"
TRACKED_LICENSE = REPO_ROOT / "license" / "license.json"
WORKFLOW_PROFILE_ID = "fast_path"
JOINT_ENV = "QMTOOL_WEB01_JOINT"
JOINT_OPT_IN = "1"
DETAIL_READY_FILENAME = "detail-ready.json"
STALE_MUTATION_COMPLETE_FILENAME = "stale-mutation-complete.json"
BOOTSTRAP_USERNAME = "opsadmin"
BOOTSTRAP_PASSWORD = "ops-secret-1"
LOGIN_PASSWORD = "ops-secret-2"
_BACKEND_GRACEFUL_STOP_TIMEOUT = 40.0
_MARKER_GONE_WAIT_SECONDS = 2.0


class Web01HarnessError(RuntimeError):
    """Base WEB01 harness failure."""


class Web01HarnessBlockedError(Web01HarnessError):
    """Precondition blocked the harness."""


@dataclass
class Web01FixtureDocument:
    document_id: str
    version: int
    workflow_profile_id: str
    etag: str


@dataclass
class Web01RealProcessHarness:
    workspace: Path
    bind_host: str = "127.0.0.1"
    bind_port: int = 0
    base_url: str = ""
    backend: subprocess.Popen[str] | None = None
    playwright: subprocess.Popen[str] | None = None
    backend_log_handle: TextIO | None = None
    extra_secrets: tuple[str, ...] = field(default_factory=tuple)
    _home: Path | None = None

    def __post_init__(self) -> None:
        self.workspace = self.workspace.resolve()
        require_inside_web01_evidence(self.workspace)

    @property
    def home(self) -> Path:
        if self._home is None:
            self._home = self.workspace / "qmtool-home"
            self._home.mkdir(parents=True, exist_ok=True)
        return self._home

    def allocate_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((self.bind_host, 0))
            return int(sock.getsockname()[1])

    def assert_port_free(self, port: int) -> None:
        if not port_is_free(self.bind_host, port):
            raise Web01HarnessBlockedError(
                f"refusing WEB01 start: {self.bind_host}:{port} is occupied by a foreign process"
            )

    def write_log(self, name: str, text: str) -> None:
        path = self.workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(redact_log_text(text), encoding="utf-8")

    def provision_postgres(self, live_env: Any) -> None:
        usermanagement_api.migrate_postgres_schema(live_env.migrator_dsn)
        documents_api.provision_postgres_schema(live_env.admin_dsn)
        documents_api.migrate_postgres_schema(live_env.migrator_dsn)
        registry_api.provision_postgres_schema(live_env.admin_dsn)
        registry_api.migrate_postgres_schema(live_env.migrator_dsn)
        signature_api.provision_postgres_schema(live_env.admin_dsn)
        signature_api.migrate_postgres_schema(live_env.migrator_dsn)
        documents_api.seed_postgres_workflow_profiles(live_env.runtime_dsn)

    def copy_tracked_license(self) -> None:
        if not TRACKED_LICENSE.is_file():
            raise Web01HarnessBlockedError("tracked production licence license/license.json is missing")
        destination = self.home / "license"
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TRACKED_LICENSE, destination / "license.json")

    def start_backend(self, *, live_env: Any, dist_dir: Path) -> None:
        if self.bind_port <= 0:
            self.bind_port = self.allocate_port()
        self.assert_port_free(self.bind_port)
        self.base_url = f"https://{self.bind_host}:{self.bind_port}"

        tls_dir = self.workspace / "tls"
        cert_path, key_path = write_ephemeral_pems(tls_dir)
        self.copy_tracked_license()

        env = os.environ.copy()
        env["QMTOOL_HOME"] = str(self.home)
        env["QMTOOL_RUNTIME_PROFILE"] = "production"
        env["QMTOOL_LICENSE_MODE"] = "production"
        env["QMTOOL_PG_DSN"] = live_env.runtime_dsn
        env["QMTOOL_TLS_CERT_FILE"] = str(cert_path)
        env["QMTOOL_TLS_KEY_FILE"] = str(key_path)
        env["QMTOOL_BIND_HOST"] = self.bind_host
        env["QMTOOL_BIND_PORT"] = str(self.bind_port)
        env["QMTOOL_WEBCLIENT_DIST"] = str(dist_dir)
        env["QMTOOL_BOOTSTRAP_ADMIN_USERNAME"] = BOOTSTRAP_USERNAME
        env["QMTOOL_BOOTSTRAP_ADMIN_PASSWORD"] = BOOTSTRAP_PASSWORD
        env["QMTOOL_UVICORN_LOG_LEVEL"] = "warning"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(REPO_ROOT), env.get("PYTHONPATH", "")) if part
        )
        for key in (
            "QMTOOL_PG_HOST",
            "QMTOOL_PG_DATABASE",
            "QMTOOL_PG_USER",
            "QMTOOL_PG_PASSWORD",
        ):
            env.pop(key, None)
        if sys.platform == "win32":
            startup = write_backend_sigbreak_startup(self.workspace)
            env["PYTHONPATH"] = prepend_pythonpath(env.get("PYTHONPATH", ""), startup)

        backend_log_path = self.workspace / "backend-stdout.log"
        self.backend_log_handle = backend_log_path.open("w", encoding="utf-8")
        popen_kwargs: dict[str, Any] = {
            "cwd": str(REPO_ROOT),
            "env": env,
            "stdout": self.backend_log_handle,
            "stderr": subprocess.STDOUT,
            "text": True,
        }
        creationflags = backend_popen_creationflags()
        if creationflags:
            popen_kwargs["creationflags"] = creationflags
        self.backend = subprocess.Popen([python_executable(), "-m", "src.backend"], **popen_kwargs)
        wait_https_health(self.bind_host, self.bind_port)
        if not is_host_running_marker_present(app_home=self.home):
            raise Web01HarnessError("production ServiceHost did not create a host-running marker")
        complete_bootstrap_password_change(self.base_url)
        ensure_bootstrap_admin_qmb(self.base_url)

    def create_planned_document(self, document_id: str) -> Web01FixtureDocument:
        token = bearer_token(self.base_url, BOOTSTRAP_USERNAME, LOGIN_PASSWORD)
        actor_id = actor_user_id(self.base_url, token)
        auth_headers = {"Authorization": f"Bearer {token}"}
        create_status, create_body = http_json(
            "POST",
            f"{self.base_url}/api/v1/documents/versions/create",
            json_body={
                "document_id": document_id,
                "version": 1,
                "title": document_id,
                "doc_type": "OTHER",
                "control_class": "CONTROLLED_SHORT",
                "workflow_profile_id": WORKFLOW_PROFILE_ID,
            },
            headers=auth_headers,
        )
        if create_status != 200:
            raise Web01HarnessError(
                f"document create failed: HTTP {create_status} "
                f"error={_safe_error_code(create_body) or 'unknown'}"
            )
        payload = json.loads(create_body.decode("utf-8"))
        etag = str(payload.get("etag") or "")
        assign_status, assign_body = http_json(
            "POST",
            f"{self.base_url}/api/v1/documents/versions/{document_id}/1/workflow/assign-roles",
            json_body={
                "editors": [actor_id],
                "reviewers": [],
                "approvers": [actor_id],
            },
            headers={**auth_headers, "If-Match": etag},
        )
        if assign_status != 200:
            raise Web01HarnessError(f"assign roles failed: HTTP {assign_status}")
        assigned = json.loads(assign_body.decode("utf-8"))
        return Web01FixtureDocument(
            document_id=document_id,
            version=1,
            workflow_profile_id=WORKFLOW_PROFILE_ID,
            etag=str(assigned.get("etag") or ""),
        )

    def bump_document_etag_via_assign_roles(self, fixture: Web01FixtureDocument) -> None:
        """Apply a successful server-side mutation so the browser keeps a stale ETag.

        Must stay on a state where the UI action under test (``start``) remains authorized;
        otherwise stale-token masking returns HTTP 404 instead of 409.
        """
        detail_ready_path = self.workspace / DETAIL_READY_FILENAME
        if not detail_ready_path.is_file():
            raise Web01HarnessError("detail-ready.json missing before etag bump")
        payload = json.loads(detail_ready_path.read_text(encoding="utf-8"))
        etag = str(payload.get("etag") or fixture.etag or "").strip()
        if not etag:
            raise Web01HarnessError("detail-ready.json missing etag for stale mutation")

        token = bearer_token(self.base_url, BOOTSTRAP_USERNAME, LOGIN_PASSWORD)
        actor_id = actor_user_id(self.base_url, token)
        status, body = http_json(
            "POST",
            f"{self.base_url}/api/v1/documents/versions/{fixture.document_id}/{fixture.version}/workflow/assign-roles",
            json_body={
                "editors": [actor_id],
                "reviewers": [],
                "approvers": [actor_id],
            },
            headers={"Authorization": f"Bearer {token}", "If-Match": etag},
        )
        if status != 200:
            raise Web01HarnessError(
                f"assign-roles etag bump failed: HTTP {status} "
                f"error={_safe_error_code(body) or 'unknown'}"
            )

    def wait_for_detail_ready(self, *, timeout: float = 120.0) -> None:
        path = self.workspace / DETAIL_READY_FILENAME
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.is_file():
                return
            if self.playwright is not None and self.playwright.poll() is not None:
                raise Web01HarnessError("Playwright exited before detail-ready handshake")
            time.sleep(0.25)
        raise Web01HarnessError("timeout waiting for detail-ready handshake")

    def write_stale_mutation_complete(self) -> None:
        path = self.workspace / STALE_MUTATION_COMPLETE_FILENAME
        path.write_text(json.dumps({"phase": "stale-mutation-complete"}, indent=2) + "\n", encoding="utf-8")

    def run_playwright_conflict_spec(self, *, fixture: Web01FixtureDocument, node_exe: Path) -> None:
        playwright_cli = REPO_ROOT / "webclient" / "node_modules" / "@playwright" / "test" / "cli.js"
        if not playwright_cli.is_file():
            raise Web01HarnessBlockedError("Playwright CLI is missing; npm ci must precede the WEB01 gate")
        if not node_exe.is_file():
            raise Web01HarnessBlockedError("QMTOOL_WEB01_NODE_EXE must point to a Node executable")

        child_env = {
            key: value
            for key, value in os.environ.items()
            if "DSN" not in key.upper()
            and not key.upper().endswith("PASSWORD")
            and "SECRET" not in key.upper()
        }
        child_env[JOINT_ENV] = JOINT_OPT_IN
        child_env["QMTOOL_WEB01_USERNAME"] = BOOTSTRAP_USERNAME
        child_env["QMTOOL_WEB01_PASSWORD"] = LOGIN_PASSWORD
        child_env["QMTOOL_WEB01_EVIDENCE_DIR"] = str(self.workspace)
        child_env["QMTOOL_WEB01_DOCUMENT_ID"] = fixture.document_id
        child_env["QMTOOL_WEB01_VERSION"] = str(fixture.version)
        child_env["QMTOOL_WEB01_PROFILE_ID"] = fixture.workflow_profile_id
        child_env["WEB00_SMOKE_BASE_URL"] = self.base_url
        child_env["WEB00_SMOKE_EVIDENCE_DIR"] = str(self.workspace)

        stdout_path = self.workspace / "playwright-stdout.log"
        stderr_path = self.workspace / "playwright-stderr.log"
        stdout_handle = stdout_path.open("w", encoding="utf-8")
        stderr_handle = stderr_path.open("w", encoding="utf-8")
        self.playwright = subprocess.Popen(
            [str(node_exe), str(playwright_cli), "test", "e2e/documents-conflict-live.spec.ts"],
            cwd=str(REPO_ROOT / "webclient"),
            env=child_env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )

    def wait_playwright(self, *, timeout: float = 180.0) -> None:
        if self.playwright is None:
            raise Web01HarnessError("Playwright was not started")
        try:
            rc = self.playwright.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Web01HarnessError("timeout waiting for Playwright to finish") from None
        if rc != 0:
            raise Web01HarnessError(f"WEB01 Playwright conflict spec failed with exit {rc}")

    def cleanup(self) -> None:
        stop_owned_process(self.playwright)
        self.playwright = None
        if self.backend is not None:
            stop_backend_graceful(self.backend, home=self.home, workspace=self.workspace)
            self.backend = None
        if self.backend_log_handle is not None:
            self.backend_log_handle.close()
            self.backend_log_handle = None
        if self.bind_port > 0:
            wait_port_free(self.bind_host, self.bind_port, timeout=10.0)

    def __enter__(self) -> Web01RealProcessHarness:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.cleanup()


def repo_root() -> Path:
    return REPO_ROOT


def evidence_root() -> Path:
    return EVIDENCE_ROOT


def require_inside_web01_evidence(path: Path) -> Path:
    resolved = Path(path).resolve()
    root = evidence_root().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise Web01HarnessBlockedError(
            f"WEB01 evidence path must resolve under {root}; rejected {resolved}"
        ) from exc
    return resolved


def allocate_web01_workspace() -> Path:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{stamp}-{uuid.uuid4().hex}"
    candidate = evidence_root() / "checkpoints" / "h" / run_id
    resolved = require_inside_web01_evidence(candidate)
    if resolved.exists():
        raise Web01HarnessBlockedError(f"refusing to reuse existing WEB01 workspace: {resolved}")
    resolved.mkdir(parents=True, exist_ok=False)
    return resolved


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def wait_port_free(host: str, port: int, *, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_free(host, port):
            return
        time.sleep(0.1)
    raise Web01HarnessError(f"WEB01 ServiceHost port {host}:{port} still occupied after stop")


def write_ephemeral_pems(target: Path) -> tuple[Path, Path]:
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


def ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _safe_error_code(body: bytes) -> str | None:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    detail = payload.get("detail")
    if isinstance(detail, dict):
        error = detail.get("error")
        return str(error) if error else None
    return None


def http_json(
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    data = None if json_body is None else json.dumps(json_body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    if json_body is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=30, context=ssl_context()) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


def _safe_error_detail(body: bytes) -> str:
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return "unparseable"
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("error") or detail.get("message") or "unknown")
    return "unknown"


def bearer_token(base_url: str, username: str, password: str) -> str:
    status, body = http_json(
        "POST",
        f"{base_url}/api/v1/auth/token",
        json_body={"username": username, "password": password},
    )
    if status != 200:
        raise Web01HarnessError(f"token login failed: HTTP {status}")
    payload = json.loads(body.decode("utf-8"))
    token = str(payload.get("token") or "")
    if not token:
        raise Web01HarnessError("token login returned no token")
    return token


def actor_user_id(base_url: str, token: str) -> str:
    status, body = http_json(
        "GET",
        f"{base_url}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if status != 200:
        raise Web01HarnessError(f"auth me failed: HTTP {status}")
    payload = json.loads(body.decode("utf-8"))
    user_id = str(payload.get("user_id") or "")
    if not user_id:
        raise Web01HarnessError("auth me returned no user_id")
    return user_id


def ensure_bootstrap_admin_qmb(base_url: str) -> None:
    token = bearer_token(base_url, BOOTSTRAP_USERNAME, LOGIN_PASSWORD)
    status, _body = http_json(
        "PATCH",
        f"{base_url}/api/v1/users/{BOOTSTRAP_USERNAME}/access",
        json_body={"is_qmb": True, "role": "Admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if status != 200:
        raise Web01HarnessError(f"failed to grant QMB to bootstrap admin: HTTP {status}")


def complete_bootstrap_password_change(base_url: str) -> None:
    status, body = http_json(
        "POST",
        f"{base_url}/api/v1/auth/token",
        json_body={"username": BOOTSTRAP_USERNAME, "password": BOOTSTRAP_PASSWORD},
    )
    if status != 200:
        raise Web01HarnessError(f"bootstrap token login failed: HTTP {status}")
    payload = json.loads(body.decode("utf-8"))
    token = str(payload.get("token") or "")
    if not token:
        raise Web01HarnessError("bootstrap token login returned no token")
    changed, _changed_body = http_json(
        "POST",
        f"{base_url}/api/v1/auth/change-password",
        json_body={"new_password": LOGIN_PASSWORD},
        headers={"Authorization": f"Bearer {token}"},
    )
    if changed != 204:
        raise Web01HarnessError(f"bootstrap password change failed: HTTP {changed}")


def wait_https_health(host: str, port: int, *, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = "not-started"
    while time.monotonic() < deadline:
        try:
            payload = probe_health(host, port, use_https=True, ssl_context=ssl_context(), timeout=2.0)
            if payload.get("status") == "ok":
                return
            last_error = repr(payload)
        except Exception as exc:  # noqa: BLE001
            last_error = type(exc).__name__
        time.sleep(0.25)
    raise Web01HarnessError(f"WEB01 production ServiceHost health timed out ({last_error})")


def stop_owned_process(proc: subprocess.Popen[str] | None) -> None:
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


def stop_backend_graceful(
    proc: subprocess.Popen[str],
    *,
    home: Path,
    workspace: Path,
) -> None:
    fallback_used = False
    if proc.poll() is None:
        send_graceful_stop_signal(proc)
        try:
            proc.wait(timeout=_BACKEND_GRACEFUL_STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            fallback_used = True
    if proc.poll() is None:
        fallback_used = True
        stop_owned_process(proc)
    marker_present = is_host_running_marker_present(app_home=home)
    deadline = time.monotonic() + _MARKER_GONE_WAIT_SECONDS
    while marker_present and time.monotonic() < deadline:
        marker_present = is_host_running_marker_present(app_home=home)
        time.sleep(0.05)
    diagnosis = {
        "fallback_used": fallback_used,
        "marker_present_after_exit": marker_present,
        "child_returncode": proc.poll(),
    }
    (workspace / "graceful-stop-diagnosis.json").write_text(
        json.dumps(diagnosis, indent=2) + "\n",
        encoding="utf-8",
    )


def require_joint_opt_in() -> None:
    if os.environ.get(JOINT_ENV, "").strip() != JOINT_OPT_IN:
        raise Web01HarnessBlockedError(f"{JOINT_ENV} must equal {JOINT_OPT_IN} for guarded browser specs")
