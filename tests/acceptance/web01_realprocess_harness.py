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
from collections.abc import Callable
from typing import Any, TextIO

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from PIL import Image

from modules.documents import api as documents_api
from modules.registry import api as registry_api
from modules.signature import api as signature_api
from modules.usermanagement import api as usermanagement_api
from qm_platform.blob import is_host_running_marker_present
from qm_platform.runtime.maintenance import enter_maintenance, exit_maintenance, is_maintenance_active
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
PIS_DOCUMENT_ID = "DOC-WEB01-K1-PIS"
CONFLICT_DOCUMENT_ID = "DOC-WEB01-K1-409"
JOINT_ENV = "QMTOOL_WEB01_JOINT"
JOINT_OPT_IN = "1"
DETAIL_READY_FILENAME = "detail-ready.json"
STALE_MUTATION_COMPLETE_FILENAME = "stale-mutation-complete.json"
RESTART_REQUEST_FILENAME = "restart-request.json"
RESTART_COMPLETE_FILENAME = "restart-complete.json"
GRACEFUL_STOP_DIAGNOSIS_FILENAME = "graceful-stop-diagnosis.json"
RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME = "restart-graceful-stop-diagnosis.json"
FINAL_GRACEFUL_STOP_DIAGNOSIS_FILENAME = "final-graceful-stop-diagnosis.json"
MAINTENANCE_REQUEST_FILENAME = "maintenance-request.json"
MAINTENANCE_COMPLETE_FILENAME = "maintenance-complete.json"
MAINTENANCE_EXIT_REQUEST_FILENAME = "maintenance-exit-request.json"
MAINTENANCE_EXIT_COMPLETE_FILENAME = "maintenance-exit-complete.json"
PIS_DOCUMENT_READY_FILENAME = "pis-document-ready.json"
PIS_ROLES_ASSIGNED_FILENAME = "pis-roles-assigned.json"
PLAYWRIGHT_JSON_FILENAME = "web01-product-slice-playwright.json"
BOOTSTRAP_USERNAME = "opsadmin"
BOOTSTRAP_PASSWORD = "ops-secret-1"
LOGIN_PASSWORD = "ops-secret-2"
FIXTURE_WEB01_BOOTSTRAP_PASS = "web01-fixture-bootstrap-pass"
FIXTURE_WEB01_ADMIN_PASS = "web01-fixture-admin-pass"
FIXTURE_WEB01_MUSTCHANGE_PASS = "web01-fixture-mustchange-pass"
FIXTURE_WEB01_EDITOR_PASS = "web01-fixture-editor-pass"
FIXTURE_WEB01_REVIEWER_PASS = "web01-fixture-reviewer-pass"
FIXTURE_WEB01_APPROVER_PASS = "web01-fixture-approver-pass"
WEB01_BOOTSTRAP_USERNAME = "web01_bootstrap"
WEB01_ADMIN_USERNAME = "web01_admin"
WEB01_MUSTCHANGE_USERNAME = "web01_mustchange"
WEB01_EDITOR_USERNAME = "web01_editor"
WEB01_REVIEWER_USERNAME = "web01_reviewer"
WEB01_APPROVER_USERNAME = "web01_approver"
MANDATORY_SCREENSHOTS: tuple[str, ...] = (
    "login-desktop.png",
    "login-stacked.png",
    "change-password-desktop.png",
    "dashboard-desktop.png",
    "loading-pool-desktop.png",
    "pool-split-desktop.png",
    "pool-stacked.png",
    "empty-pool-desktop.png",
    "error-pool-desktop.png",
    "detail-desktop.png",
    "forbidden-desktop.png",
    "viewer-desktop.png",
    "signature-desktop.png",
    "admin-users-desktop.png",
    "conflict-desktop.png",
    "maintenance-banner-desktop.png",
)
_DESKTOP_VIEWPORT = (1280, 800)
_STACKED_VIEWPORT = (390, 844)
MANDATORY_SCREENSHOT_DIMENSIONS: dict[str, tuple[int, int]] = {
    name: _STACKED_VIEWPORT if name.endswith("-stacked.png") else _DESKTOP_VIEWPORT
    for name in MANDATORY_SCREENSHOTS
}
_MIN_VALID_SCREENSHOT_BYTES = 512
_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000062 00000 n \n0000000117 00000 n \n"
    b"trailer << /Root 1 0 R /Size 4 >>\nstartxref\n188\n%%EOF\n"
)
_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
_BACKEND_GRACEFUL_STOP_TIMEOUT = 40.0
_MARKER_GONE_WAIT_SECONDS = 2.0


class Web01HarnessError(RuntimeError):
    """Base WEB01 harness failure."""


class Web01HarnessBlockedError(Web01HarnessError):
    """Precondition blocked the harness."""


HANDSHAKE_PIS_ROLES = "pis_roles"
HANDSHAKE_CONFLICT_STALE = "conflict_stale"
HANDSHAKE_MAINTENANCE = "maintenance"
HANDSHAKE_MAINTENANCE_EXIT = "maintenance_exit"
HANDSHAKE_RESTART = "restart"
WEB01_HANDSHAKE_IDS: tuple[str, ...] = (
    HANDSHAKE_PIS_ROLES,
    HANDSHAKE_CONFLICT_STALE,
    HANDSHAKE_MAINTENANCE,
    HANDSHAKE_MAINTENANCE_EXIT,
    HANDSHAKE_RESTART,
)


@dataclass
class Web01HandshakeTracker:
    """Processes each handshake marker at most once after a successful handler."""

    _completed: set[str] = field(default_factory=set)

    def try_process(
        self,
        handshake_id: str,
        *,
        marker_path: Path,
        handler: Callable[[], None],
    ) -> bool:
        if handshake_id in self._completed:
            return False
        if not marker_path.is_file():
            return False
        handler()
        self._completed.add(handshake_id)
        return True

    def is_complete(self, handshake_id: str) -> bool:
        return handshake_id in self._completed


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
    _fixture_initialized: bool = False

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

    def start_backend(
        self,
        *,
        live_env: Any,
        dist_dir: Path,
        run_fixture_initialization: bool = True,
    ) -> None:
        if run_fixture_initialization:
            if self._fixture_initialized:
                raise Web01HarnessError(
                    "fixture initialization already completed; initial backend start refused"
                )
        elif not self._fixture_initialized:
            raise Web01HarnessError("backend start refused before fixture initialization completed")
        self._launch_backend_process(
            live_env=live_env,
            dist_dir=dist_dir,
            append_backend_log=not run_fixture_initialization,
        )
        if run_fixture_initialization:
            complete_bootstrap_password_change(self.base_url)
            ensure_bootstrap_admin_qmb(self.base_url)
            self._fixture_initialized = True

    def _close_backend_log_handle(self) -> None:
        if self.backend_log_handle is not None:
            self.backend_log_handle.close()
            self.backend_log_handle = None

    def _launch_backend_process(
        self,
        *,
        live_env: Any,
        dist_dir: Path,
        append_backend_log: bool = False,
    ) -> None:
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
        log_mode = "a" if append_backend_log else "w"
        self.backend_log_handle = backend_log_path.open(log_mode, encoding="utf-8")
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

    def admin_token(self) -> str:
        return bearer_token(self.base_url, BOOTSTRAP_USERNAME, LOGIN_PASSWORD)

    def create_user_via_http(
        self,
        *,
        username: str,
        password: str,
        role: str = "User",
        is_qmb: bool = False,
        must_change_password: bool = False,
    ) -> None:
        token = self.admin_token()
        status, body = http_json(
            "POST",
            f"{self.base_url}/api/v1/users",
            json_body={
                "username": username,
                "password": password,
                "role": role,
                "is_qmb": is_qmb,
                "must_change_password": must_change_password,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if status not in (201, 409):
            raise Web01HarnessError(
                f"create user {username} failed: HTTP {status} "
                f"error={_safe_error_code(body) or 'unknown'}"
            )

    def seed_synthetic_users(self) -> dict[str, str]:
        self.create_user_via_http(
            username=WEB01_BOOTSTRAP_USERNAME,
            password=FIXTURE_WEB01_BOOTSTRAP_PASS,
            role="Admin",
            is_qmb=True,
            must_change_password=False,
        )
        self.create_user_via_http(
            username=WEB01_ADMIN_USERNAME,
            password=FIXTURE_WEB01_ADMIN_PASS,
            role="Admin",
            is_qmb=True,
            must_change_password=False,
        )
        self.create_user_via_http(
            username=WEB01_MUSTCHANGE_USERNAME,
            password=FIXTURE_WEB01_MUSTCHANGE_PASS,
            role="User",
            must_change_password=True,
        )
        self.create_user_via_http(
            username=WEB01_EDITOR_USERNAME,
            password=FIXTURE_WEB01_EDITOR_PASS,
            role="User",
            is_qmb=True,
            must_change_password=False,
        )
        self.create_user_via_http(
            username=WEB01_REVIEWER_USERNAME,
            password=FIXTURE_WEB01_REVIEWER_PASS,
            role="User",
            must_change_password=False,
        )
        self.create_user_via_http(
            username=WEB01_APPROVER_USERNAME,
            password=FIXTURE_WEB01_APPROVER_PASS,
            role="User",
            must_change_password=False,
        )
        return {
            "bootstrap": WEB01_BOOTSTRAP_USERNAME,
            "admin": WEB01_ADMIN_USERNAME,
            "mustchange": WEB01_MUSTCHANGE_USERNAME,
            "editor": WEB01_EDITOR_USERNAME,
            "reviewer": WEB01_REVIEWER_USERNAME,
            "approver": WEB01_APPROVER_USERNAME,
        }

    def activate_signature_asset(self, *, username: str, password: str) -> None:
        token = bearer_token(self.base_url, username, password)
        status, body = http_bytes(
            "POST",
            f"{self.base_url}/api/v1/signature/assets/import-and-activate",
            content=_MINIMAL_PNG,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "image/png",
                "X-Filename-Hint": f"web01-{username}.png",
                "X-Signature-Password": password,
            },
        )
        if status != 200:
            raise Web01HarnessError(
                f"signature asset import failed for {username}: HTTP {status} "
                f"error={_safe_error_code(body) or 'unknown'}"
            )
        verify_status, verify_body = http_json(
            "POST",
            f"{self.base_url}/api/v1/signature/verify-password",
            json_body={"password": password},
            headers={"Authorization": f"Bearer {token}"},
        )
        if verify_status != 200:
            raise Web01HarnessError(f"signature verify-password failed for {username}")
        payload = json.loads(verify_body.decode("utf-8"))
        if not payload.get("ok"):
            raise Web01HarnessError(f"signature verify-password not ok for {username}")

    def activate_role_signature_assets(self) -> None:
        for username, password in (
            (WEB01_EDITOR_USERNAME, FIXTURE_WEB01_EDITOR_PASS),
            (WEB01_REVIEWER_USERNAME, FIXTURE_WEB01_REVIEWER_PASS),
            (WEB01_APPROVER_USERNAME, FIXTURE_WEB01_APPROVER_PASS),
        ):
            self.activate_signature_asset(username=username, password=password)

    def assign_pis_roles_from_handshake(
        self,
        *,
        editor_id: str,
        reviewer_id: str,
        approver_id: str,
    ) -> Web01FixtureDocument:
        path = self.workspace / PIS_DOCUMENT_READY_FILENAME
        if not path.is_file():
            raise Web01HarnessError("pis-document-ready.json missing before role assignment")
        payload = json.loads(path.read_text(encoding="utf-8"))
        fixture = Web01FixtureDocument(
            document_id=str(payload.get("documentId") or PIS_DOCUMENT_ID),
            version=int(payload.get("version") or 1),
            workflow_profile_id=str(payload.get("profileId") or WORKFLOW_PROFILE_ID),
            etag=str(payload.get("etag") or ""),
        )
        if not fixture.etag:
            raise Web01HarnessError("pis-document-ready.json missing etag")
        self.assign_document_roles(
            fixture,
            editor_id=editor_id,
            reviewer_id=reviewer_id,
            approver_id=approver_id,
        )
        (self.workspace / PIS_ROLES_ASSIGNED_FILENAME).write_text(
            json.dumps(
                {
                    "phase": "pis-roles-assigned",
                    "documentId": fixture.document_id,
                    "version": fixture.version,
                    "etag": fixture.etag,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return fixture

    def assign_document_roles(
        self,
        fixture: Web01FixtureDocument,
        *,
        editor_id: str,
        reviewer_id: str,
        approver_id: str,
    ) -> None:
        token = self.admin_token()
        status, body = http_json(
            "POST",
            f"{self.base_url}/api/v1/documents/versions/{fixture.document_id}/{fixture.version}/workflow/assign-roles",
            json_body={
                "editors": [editor_id],
                "reviewers": [reviewer_id],
                "approvers": [approver_id],
            },
            headers={"Authorization": f"Bearer {token}", "If-Match": fixture.etag},
        )
        if status != 200:
            raise Web01HarnessError(
                f"assign roles failed: HTTP {status} error={_safe_error_code(body) or 'unknown'}"
            )
        payload = json.loads(body.decode("utf-8"))
        fixture.etag = str(payload.get("etag") or fixture.etag)

    def run_playwright_product_slice_spec(
        self,
        *,
        fixture: Web01FixtureDocument,
        visual_dir: Path,
        node_exe: Path,
    ) -> None:
        playwright_cli = REPO_ROOT / "webclient" / "node_modules" / "@playwright" / "test" / "cli.js"
        if not playwright_cli.is_file():
            raise Web01HarnessBlockedError("Playwright CLI is missing; npm ci must precede the WEB01 gate")
        if not node_exe.is_file():
            raise Web01HarnessBlockedError("QMTOOL_WEB01_NODE_EXE must point to a Node executable")
        visual_dir.mkdir(parents=True, exist_ok=True)

        child_env = {
            key: value
            for key, value in os.environ.items()
            if "DSN" not in key.upper()
            and not key.upper().endswith("PASSWORD")
            and "SECRET" not in key.upper()
        }
        child_env[JOINT_ENV] = JOINT_OPT_IN
        child_env["QMTOOL_WEB01_EVIDENCE_DIR"] = str(self.workspace)
        child_env["QMTOOL_WEB01_VISUAL_DIR"] = str(visual_dir)
        child_env["QMTOOL_WEB01_DOCUMENT_ID"] = fixture.document_id
        child_env["QMTOOL_WEB01_VERSION"] = str(fixture.version)
        child_env["QMTOOL_WEB01_PROFILE_ID"] = fixture.workflow_profile_id
        child_env["QMTOOL_WEB01_PIS_DOCUMENT_ID"] = PIS_DOCUMENT_ID
        child_env["QMTOOL_WEB01_ADMIN_USER"] = WEB01_ADMIN_USERNAME
        child_env["QMTOOL_WEB01_ADMIN_PASS"] = FIXTURE_WEB01_ADMIN_PASS
        child_env["QMTOOL_WEB01_MUSTCHANGE_USER"] = WEB01_MUSTCHANGE_USERNAME
        child_env["QMTOOL_WEB01_MUSTCHANGE_PASS"] = FIXTURE_WEB01_MUSTCHANGE_PASS
        child_env["QMTOOL_WEB01_EDITOR_USER"] = WEB01_EDITOR_USERNAME
        child_env["QMTOOL_WEB01_EDITOR_PASS"] = FIXTURE_WEB01_EDITOR_PASS
        child_env["QMTOOL_WEB01_REVIEWER_USER"] = WEB01_REVIEWER_USERNAME
        child_env["QMTOOL_WEB01_REVIEWER_PASS"] = FIXTURE_WEB01_REVIEWER_PASS
        child_env["QMTOOL_WEB01_APPROVER_USER"] = WEB01_APPROVER_USERNAME
        child_env["QMTOOL_WEB01_APPROVER_PASS"] = FIXTURE_WEB01_APPROVER_PASS
        child_env["WEB00_SMOKE_BASE_URL"] = self.base_url
        child_env["WEB00_SMOKE_EVIDENCE_DIR"] = str(self.workspace)

        stdout_path = self.workspace / "playwright-stdout.log"
        stderr_path = self.workspace / "playwright-stderr.log"
        stdout_handle = stdout_path.open("w", encoding="utf-8")
        stderr_handle = stderr_path.open("w", encoding="utf-8")
        self.playwright = subprocess.Popen(
            [str(node_exe), str(playwright_cli), "test", "e2e/web01-product-slice.spec.ts"],
            cwd=str(REPO_ROOT / "webclient"),
            env=child_env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )

    def wait_for_restart_request(self, *, timeout: float = 240.0) -> None:
        path = self.workspace / RESTART_REQUEST_FILENAME
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.is_file():
                return
            if self.playwright is not None and self.playwright.poll() is not None:
                raise Web01HarnessError("Playwright exited before restart handshake")
            time.sleep(0.25)
        raise Web01HarnessError("timeout waiting for restart-request handshake")

    def write_restart_complete(self) -> None:
        path = self.workspace / RESTART_COMPLETE_FILENAME
        path.write_text(
            json.dumps({"phase": "host-restarted", "port": self.bind_port}, indent=2) + "\n",
            encoding="utf-8",
        )

    def wait_for_maintenance_request(self, *, timeout: float = 240.0) -> None:
        path = self.workspace / MAINTENANCE_REQUEST_FILENAME
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.is_file():
                return
            if self.playwright is not None and self.playwright.poll() is not None:
                raise Web01HarnessError("Playwright exited before maintenance handshake")
            time.sleep(0.25)
        raise Web01HarnessError("timeout waiting for maintenance-request handshake")

    def enter_degraded_maintenance(self) -> None:
        enter_maintenance(self.home)
        (self.workspace / MAINTENANCE_COMPLETE_FILENAME).write_text(
            json.dumps({"phase": "maintenance-enabled"}, indent=2) + "\n",
            encoding="utf-8",
        )

    def wait_for_maintenance_exit_request(self, *, timeout: float = 240.0) -> None:
        path = self.workspace / MAINTENANCE_EXIT_REQUEST_FILENAME
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.is_file():
                return
            if self.playwright is not None and self.playwright.poll() is not None:
                raise Web01HarnessError("Playwright exited before maintenance-exit handshake")
            time.sleep(0.25)
        raise Web01HarnessError("timeout waiting for maintenance-exit-request handshake")

    def complete_maintenance_exit_handshake(self) -> None:
        exit_maintenance(self.home)
        if is_maintenance_active(self.home):
            raise Web01HarnessError("maintenance flag still active after exit_maintenance")
        (self.workspace / MAINTENANCE_EXIT_COMPLETE_FILENAME).write_text(
            json.dumps({"phase": "maintenance-exited"}, indent=2) + "\n",
            encoding="utf-8",
        )

    def restart_backend_process(self, *, live_env: Any, dist_dir: Path) -> None:
        if not self._fixture_initialized:
            raise Web01HarnessError("restart refused before fixture initialization completed")
        if self.backend is not None:
            diagnosis = stop_backend_graceful(
                self.backend,
                home=self.home,
                workspace=self.workspace,
                diagnosis_filename=RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
            )
            self.backend = None
            self._close_backend_log_handle()
            require_clean_restart_stop_diagnosis(diagnosis)
        if self.bind_port > 0:
            wait_port_free(self.bind_host, self.bind_port, timeout=10.0)
        self.start_backend(live_env=live_env, dist_dir=dist_dir, run_fixture_initialization=False)

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
        proc = self.playwright
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                stop_owned_process(proc)
            except Web01HarnessError:
                raise Web01HarnessError(
                    "timeout waiting for Playwright to finish; forced stop failed "
                    f"(pid={proc.pid}, poll={proc.poll()})"
                ) from None
            self.playwright = None
            raise Web01HarnessError("timeout waiting for Playwright to finish") from None
        self.playwright = None
        if rc != 0:
            raise Web01HarnessError(f"WEB01 Playwright spec failed with exit {rc}")

    def cleanup(
        self,
        *,
        diagnosis_filename: str = GRACEFUL_STOP_DIAGNOSIS_FILENAME,
    ) -> None:
        stop_owned_process(self.playwright)
        self.playwright = None
        if self.backend is not None:
            stop_backend_graceful(
                self.backend,
                home=self.home,
                workspace=self.workspace,
                diagnosis_filename=diagnosis_filename,
            )
            self.backend = None
        self._close_backend_log_handle()
        if self.bind_port > 0:
            wait_port_free(self.bind_host, self.bind_port, timeout=10.0)
        exit_maintenance(self.home)

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


def allocate_web01_workspace(*, checkpoint: str = "h") -> Path:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{stamp}-{uuid.uuid4().hex}"
    candidate = evidence_root() / "checkpoints" / checkpoint / run_id
    resolved = require_inside_web01_evidence(candidate)
    if resolved.exists():
        raise Web01HarnessBlockedError(f"refusing to reuse existing WEB01 workspace: {resolved}")
    resolved.mkdir(parents=True, exist_ok=False)
    return resolved


def allocate_k1_workspace() -> Path:
    return allocate_web01_workspace(checkpoint="k1")


def allocate_k1_visual_dir() -> Path:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    candidate = evidence_root() / "visual" / "k1" / stamp
    resolved = require_inside_web01_evidence(candidate)
    if resolved.exists():
        raise Web01HarnessBlockedError(f"refusing to reuse existing WEB01 visual dir: {resolved}")
    resolved.mkdir(parents=True, exist_ok=False)
    return resolved


def copy_playwright_json_report(workspace: Path, visual_dir: Path) -> Path:
    source = workspace / "browser-smoke-playwright.json"
    if not source.is_file():
        raise Web01HarnessError("Playwright JSON reporter output is missing")
    destination = visual_dir / PLAYWRIGHT_JSON_FILENAME
    shutil.copy2(source, destination)
    return destination


def read_png_dimensions(path: Path) -> tuple[int, int]:
    width, height = validate_png_screenshot(path)
    return width, height


def _png_is_uniform_color(path: Path) -> bool:
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        if width <= 1 and height <= 1:
            return True
        flattened = list(rgb.get_flattened_data())
        if not flattened:
            return True
        first = flattened[0]
        return all(channel == first for channel in flattened)


def is_blank_or_trivial_png(path: Path) -> bool:
    data = path.read_bytes()
    if len(data) < _MIN_VALID_SCREENSHOT_BYTES:
        return True
    if data == _MINIMAL_PNG:
        return True
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            img.load()
            width, height = img.size
    except Exception:  # noqa: BLE001
        return True
    if width <= 1 and height <= 1:
        return True
    return _png_is_uniform_color(path)


def validate_png_screenshot(
    path: Path,
    *,
    expected_dimensions: tuple[int, int] | None = None,
) -> tuple[int, int]:
    if not path.is_file():
        raise Web01HarnessError(f"missing PNG screenshot: {path.name}")
    try:
        with Image.open(path) as img:
            if img.format != "PNG":
                raise Web01HarnessError(
                    f"screenshot {path.name} is not PNG "
                    f"(detected {img.format or 'unknown'})"
                )
            img.verify()
        with Image.open(path) as img:
            img.load()
            width, height = img.size
    except Web01HarnessError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise Web01HarnessError(f"invalid or corrupt PNG: {path.name} ({exc})") from exc
    if width <= 0 or height <= 0:
        raise Web01HarnessError(f"invalid PNG dimensions: {path.name}")
    if expected_dimensions is not None and (width, height) != expected_dimensions:
        raise Web01HarnessError(
            f"screenshot {path.name} has dimensions {width}x{height}; "
            f"expected {expected_dimensions[0]}x{expected_dimensions[1]}"
        )
    if _png_is_uniform_color(path):
        raise Web01HarnessError(f"blank or trivial WEB01-K1 screenshot: {path.name}")
    return width, height


def verify_visual_screenshots(visual_dir: Path) -> list[Path]:
    missing = [name for name in MANDATORY_SCREENSHOTS if not (visual_dir / name).is_file()]
    if missing:
        raise Web01HarnessError(f"missing mandatory WEB01-K1 screenshots: {', '.join(missing)}")
    extra = sorted(
        candidate.name
        for candidate in visual_dir.glob("*.png")
        if candidate.name not in MANDATORY_SCREENSHOTS
    )
    if extra:
        raise Web01HarnessError(f"extra WEB01-K1 screenshots are forbidden: {', '.join(extra)}")
    verified: list[Path] = []
    for name in MANDATORY_SCREENSHOTS:
        path = visual_dir / name
        validate_png_screenshot(path, expected_dimensions=MANDATORY_SCREENSHOT_DIMENSIONS[name])
        verified.append(path)
    if len(verified) != 16:
        raise Web01HarnessError(
            f"WEB01-K1 requires exactly 16 screenshots; found {len(verified)} verified files"
        )
    return verified


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


def http_bytes(
    method: str,
    url: str,
    *,
    content: bytes,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=content, method=method)
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
        result = subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise Web01HarnessError(
                f"taskkill failed for pid {proc.pid}: rc={result.returncode} "
                f"stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}"
            )
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            if proc.poll() is None:
                raise Web01HarnessError(
                    f"child pid {proc.pid} still alive after taskkill"
                ) from exc
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            if proc.poll() is None:
                raise Web01HarnessError(
                    f"child pid {proc.pid} still alive after kill"
                ) from exc


def require_clean_restart_stop_diagnosis(diagnosis: dict[str, Any]) -> None:
    if diagnosis.get("fallback_used") is True:
        raise Web01HarnessError("restart refused after graceful-stop fallback")
    if diagnosis.get("marker_present_after_exit") is True:
        raise Web01HarnessError("restart refused while host-running marker is still present")
    child_returncode = diagnosis.get("child_returncode")
    if child_returncode != 0:
        raise Web01HarnessError(f"restart refused after backend stop exit {child_returncode!r}")


def stop_backend_graceful(
    proc: subprocess.Popen[str],
    *,
    home: Path,
    workspace: Path,
    diagnosis_filename: str = GRACEFUL_STOP_DIAGNOSIS_FILENAME,
) -> dict[str, Any]:
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
    (workspace / diagnosis_filename).write_text(
        json.dumps(diagnosis, indent=2) + "\n",
        encoding="utf-8",
    )
    return diagnosis


def require_joint_opt_in() -> None:
    if os.environ.get(JOINT_ENV, "").strip() != JOINT_OPT_IN:
        raise Web01HarnessBlockedError(f"{JOINT_ENV} must equal {JOINT_OPT_IN} for guarded browser specs")
