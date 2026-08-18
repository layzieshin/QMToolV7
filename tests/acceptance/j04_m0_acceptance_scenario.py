"""J04-M0 full real-process acceptance scenario (test-only).

Orchestrates the planned CP08 real-process gate for M0 document release:
PG bootstrap, backend process, two isolated client workers, signed workflow
to APPROVED, artifact content transport, PDF/DOCX comments, backend restart.
Training, reads, change requests, archive, and Word COM conversion are out of
this catalog.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from http.client import HTTPResponse
from io import BytesIO
from typing import Any, Callable
from zipfile import ZipFile

from modules.usermanagement import postgres_schema as pgs
from tests.acceptance.j04_m0_realprocess_harness import (
    HarnessBlockedError,
    HarnessStartupError,
    J04M0RealProcessHarness,
    assert_backend_port_free,
    redact_log_text,
    require_final_acceptance_opt_in,
)
from tests.postgres_destructive_guard import (
    DestructivePostgresGuardError,
    preflight_isolated_postgres_target,
)
from tests.postgres_live_support import LivePostgresEnv, prepare_live_environment

ACCEPTANCE_DOC_ID = "J04-ACCEPT-DOC"
ACCEPTANCE_PROFILE_CODE = "j04_accept_flow_profile"
BOOTSTRAP_ADMIN_USERNAME = "j04acceptadmin"
BOOTSTRAP_ADMIN_PASSWORD = "J04Accept-Admin-Secret-1"
BOOTSTRAP_ADMIN_PASSWORD_AFTER_CHANGE = "J04Accept-Admin-Secret-2"
QMB_USERNAME = "qmb"
QMB_PASSWORD = "QmbAccept-Secret-01"
EDITOR_USERNAME = "editor"
EDITOR_PASSWORD = "EditorAccept-Secret1"
REVIEWER_USERNAME = "reviewer"
REVIEWER_PASSWORD = "ReviewAccept-Secret1"
APPROVER_USERNAME = "approver"
APPROVER_PASSWORD = "ApproveAccept-Secret1"
DIRECTORY_ROLE_PASSWORDS = {
    QMB_USERNAME: QMB_PASSWORD,
    EDITOR_USERNAME: EDITOR_PASSWORD,
    REVIEWER_USERNAME: REVIEWER_PASSWORD,
    APPROVER_USERNAME: APPROVER_PASSWORD,
}
WORKFLOW_ASSIGNMENT_ROLES = (EDITOR_USERNAME, REVIEWER_USERNAME, APPROVER_USERNAME)
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
REQUIRED_STEP_CATALOG = (
    "preconditions",
    "pg_bootstrap",
    "backend_start",
    "health_and_openapi",
    "bootstrap_admin_login",
    "seed_directory_users",
    "seed_workflow_profile",
    "client_process_sessions",
    "document_baseline_flow",
    "etag_concurrency_race",
    "artifacts_transport",
    "signature_verify_password",
    "signed_editing_complete",
    "pdf_comment_flow",
    "docx_comment_sync",
    "signed_review_approval",
    "backend_restart",
    "persistence_and_session_contract",
)
FORBIDDEN_STEP_NAMES = (
    "document_release_flow",
    "comments_lifecycle_change_requests",
    "word_com_live_boundary",
)

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


class ScenarioSkip(RuntimeError):
    """Expected skip for an optional/boundary step."""


class ScenarioFailure(RuntimeError):
    """Hard failure for a required acceptance step."""


class StepStatus(str, Enum):
    PASS = "pass"
    SKIP = "skip"
    FAIL = "fail"


@dataclass(frozen=True)
class ScenarioStepResult:
    name: str
    status: StepStatus
    detail: str = ""


@dataclass
class ScenarioContext:
    harness: J04M0RealProcessHarness
    pg_env: LivePostgresEnv | None = None
    admin_token: str = ""
    tokens: dict[str, str] = field(default_factory=dict)
    user_ids: dict[str, str] = field(default_factory=dict)
    document_etag: str = ""
    backend_extra_env: dict[str, str] = field(default_factory=dict)
    client1_token_fingerprint: str = ""
    client2_token_fingerprint: str = ""
    pre_restart_tokens: dict[str, str] = field(default_factory=dict)
    bootstrap_admin_password: str = BOOTSTRAP_ADMIN_PASSWORD
    source_artifact_id: str = ""
    source_artifact_sha256: str = ""
    pre_restart_etag: str = ""
    pre_restart_status: str = ""
    pdf_comment_id: str = ""
    docx_comment_id: str = ""


def scenario_step_catalog() -> tuple[str, ...]:
    """Ordered step names for the M0 real-process acceptance run."""
    return REQUIRED_STEP_CATALOG


def build_backend_extra_env(pg_env: LivePostgresEnv) -> dict[str, str]:
    env: dict[str, str] = {
        "QMTOOL_LICENSE_MODE": "dev",
        "QMTOOL_PG_DSN": pg_env.runtime_dsn,
        "QMTOOL_PG_REQUIRED": "1",
        "QMTOOL_BOOTSTRAP_ADMIN_USERNAME": BOOTSTRAP_ADMIN_USERNAME,
        "QMTOOL_BOOTSTRAP_ADMIN_PASSWORD": BOOTSTRAP_ADMIN_PASSWORD,
    }
    reset = os.environ.get("QMTOOL_PG_TEST_RESET", "").strip()
    if reset:
        env["QMTOOL_PG_TEST_RESET"] = reset
    expected_db = os.environ.get("QMTOOL_PG_TEST_EXPECTED_DATABASE", "").strip()
    if expected_db:
        env["QMTOOL_PG_TEST_EXPECTED_DATABASE"] = expected_db
    return env


class AcceptanceHttpClient:
    """Minimal urllib client for orchestrator-side backend HTTP (test-only)."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token: str | None = None

    def login(self, username: str, password: str) -> dict[str, Any]:
        payload = self.request(
            "POST",
            "/auth/login",
            body={"username": username, "password": password},
            auth=False,
        )
        token = str(payload.get("token", "")).strip()
        if not token:
            raise ScenarioFailure("login response missing token")
        self._token = token
        return payload

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        auth: bool = True,
    ) -> Any:
        url = f"{self._base_url}{path}"
        req_headers = dict(headers or {})
        if auth:
            if not self._token:
                raise ScenarioFailure("HTTP client is not authenticated")
            req_headers["Authorization"] = f"Bearer {self._token}"
        data: bytes | None = None
        if content is not None:
            data = content
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=30.0) as response:
                return self._parse_response(response)
        except urllib.error.HTTPError as exc:
            parsed = self._parse_response(exc)
            raise ScenarioFailure(
                f"{method.upper()} {path} failed with HTTP {exc.code}: "
                f"{redact_log_text(json.dumps(parsed, ensure_ascii=True)[:500])}"
            ) from exc

    def request_raw(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        auth: bool = True,
    ) -> tuple[int, dict[str, str], Any]:
        url = f"{self._base_url}{path}"
        req_headers = dict(headers or {})
        if auth:
            if not self._token:
                raise ScenarioFailure("HTTP client is not authenticated")
            req_headers["Authorization"] = f"Bearer {self._token}"
        data: bytes | None = None
        if content is not None:
            data = content
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=30.0) as response:
                return response.status, dict(response.headers), self._parse_response(response)
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), self._parse_response(exc)

    def request_bytes(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        auth: bool = True,
    ) -> tuple[int, dict[str, str], bytes]:
        url = f"{self._base_url}{path}"
        req_headers = dict(headers or {})
        if auth:
            if not self._token:
                raise ScenarioFailure("HTTP client is not authenticated")
            req_headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(url, headers=req_headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=30.0) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    @staticmethod
    def _parse_response(response: HTTPResponse) -> Any:
        raw = response.read()
        if not raw:
            return None
        text = raw.decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    @staticmethod
    def etag_from_version_payload(payload: Any) -> str:
        if not isinstance(payload, dict):
            raise ScenarioFailure("version payload is not a JSON object")
        etag = str(payload.get("etag", "")).strip()
        if etag:
            return etag
        state = payload.get("state")
        if isinstance(state, dict):
            etag = str(state.get("last_event_id") or "").strip()
            if etag:
                return etag
        raise ScenarioFailure("version payload missing etag")


def _header_value(headers: dict[str, str], name: str) -> str:
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return str(value)
    return ""


def _assert_no_server_paths(payload: Any, *, where: str) -> None:
    try:
        text = json.dumps(payload, ensure_ascii=True)
    except TypeError:
        text = str(payload)
    lowered = text.lower()
    if "storage_key" in lowered:
        raise ScenarioFailure(f"{where} leaked storage_key")
    if ":\\" in text or "/storage/" in lowered or "\\storage\\" in lowered:
        raise ScenarioFailure(f"{where} leaked a server filesystem path")


def _http_error_code(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("error", "")).strip()
    return ""


def _redact_http_payload(payload: Any) -> str:
    if payload is None:
        return ""
    try:
        text = json.dumps(payload, ensure_ascii=True)
    except TypeError:
        text = str(payload)
    return redact_log_text(text[:500])


def require_version_success(status: int, payload: Any, *, action: str) -> dict[str, Any]:
    """Reject non-200 version responses before reading etag from the payload."""
    if status != 200 or not isinstance(payload, dict):
        raise ScenarioFailure(
            f"{action} failed status={status} error={_http_error_code(payload)} "
            f"body={_redact_http_payload(payload)}"
        )
    return payload


def complete_bootstrap_admin_session(client: AcceptanceHttpClient) -> tuple[dict[str, Any], str]:
    """Login, complete first-admin password change if required, then GET /auth/me.

    Product bootstrap sets ``must_change_password=True``. Login still returns 200
    with a session token; ``GET /auth/me`` is 409 until ``POST /auth/change-password``.
    """
    client.login(BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_PASSWORD)
    password = BOOTSTRAP_ADMIN_PASSWORD
    status, _headers, payload = client.request_raw("GET", "/auth/me")
    if status == 409 and _http_error_code(payload) == "password_change_required":
        change_status, _change_headers, change_body = client.request_raw(
            "POST",
            "/auth/change-password",
            body={"new_password": BOOTSTRAP_ADMIN_PASSWORD_AFTER_CHANGE},
        )
        if change_status != 204:
            raise ScenarioFailure(
                "bootstrap admin password change failed "
                f"status={change_status} body={_redact_http_payload(change_body)}"
            )
        password = BOOTSTRAP_ADMIN_PASSWORD_AFTER_CHANGE
        status, _headers, payload = client.request_raw("GET", "/auth/me")
    if status != 200 or not isinstance(payload, dict):
        raise ScenarioFailure(
            "bootstrap admin /auth/me failed "
            f"status={status} body={_redact_http_payload(payload)}"
        )
    return payload, password


def capture_authenticated_user_id(
    client: AcceptanceHttpClient, *, expected_username: str
) -> str:
    """Read ``user_id`` from ``GET /auth/me`` after a role login; validate username."""
    status, _headers, payload = client.request_raw("GET", "/auth/me")
    if status != 200 or not isinstance(payload, dict):
        raise ScenarioFailure(
            f"/auth/me failed for {expected_username} "
            f"status={status} body={_redact_http_payload(payload)}"
        )
    if payload.get("username") != expected_username:
        raise ScenarioFailure(
            f"/auth/me username expected {expected_username!r}, got {payload.get('username')!r}"
        )
    user_id = str(payload.get("user_id") or "").strip()
    if not user_id:
        raise ScenarioFailure(f"/auth/me missing user_id for {expected_username}")
    return user_id


def authenticated_client(token: str, base_url: str) -> AcceptanceHttpClient:
    """Create a scenario client pinned to one already-authenticated actor token."""
    client = AcceptanceHttpClient(base_url)
    client._token = token
    return client


def workflow_role_assignment(user_ids: dict[str, str]) -> dict[str, list[str]]:
    """Build assign-roles bodies from stored user_ids, never from login usernames."""
    missing = [
        role for role in WORKFLOW_ASSIGNMENT_ROLES if not str(user_ids.get(role) or "").strip()
    ]
    if missing:
        raise ScenarioFailure(
            "role user_id missing for workflow assignment: " + ", ".join(missing)
        )
    return {
        "editors": [user_ids[EDITOR_USERNAME]],
        "reviewers": [user_ids[REVIEWER_USERNAME]],
        "approvers": [user_ids[APPROVER_USERNAME]],
    }


def _mutation_headers(token: str, etag: str, *, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}", "If-Match": etag}
    if extra:
        headers.update(extra)
    return headers


def _run_worker(
    harness: J04M0RealProcessHarness,
    *,
    home,
    label: str,
    args: list[str],
    timeout: float = 60.0,
) -> dict[str, Any]:
    managed = harness.start_client_worker(home=home, args=args, label=label)
    stdout, _stderr = managed.popen.communicate(timeout=timeout)
    text = stdout or ""
    if managed.popen.returncode not in (0, None):
        harness.write_log(f"{label}-failed.log", text)
        raise ScenarioFailure(f"worker {label} exited {managed.popen.returncode}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        harness.write_log(f"{label}-invalid-json.log", text)
        raise ScenarioFailure(f"worker {label} returned invalid JSON") from exc
    if not payload.get("ok"):
        raise ScenarioFailure(f"worker {label} reported failure: {payload.get('error', payload)}")
    return payload


def _profile_transitions() -> list[dict[str, object]]:
    return [
        {
            "transition_no": 1,
            "from_status": "DRAFT",
            "to_status": "IN_REVIEW",
            "required_role": "EDITOR",
            "decision_policy": "ONE_OF_POOL",
            "signature_required": True,
            "four_eyes_required": False,
        },
        {
            "transition_no": 2,
            "from_status": "IN_REVIEW",
            "to_status": "IN_APPROVAL",
            "required_role": "REVIEWER",
            "decision_policy": "ONE_OF_POOL",
            "signature_required": True,
            "four_eyes_required": False,
        },
        {
            "transition_no": 3,
            "from_status": "IN_APPROVAL",
            "to_status": "APPROVED",
            "required_role": "APPROVER",
            "decision_policy": "ONE_OF_POOL",
            "signature_required": True,
            "four_eyes_required": False,
        },
    ]


def _step_preconditions(ctx: ScenarioContext) -> str:
    require_final_acceptance_opt_in()
    assert_backend_port_free()
    if not os.environ.get("QMTOOL_PG_TEST_ADMIN_DSN", "").strip():
        raise ScenarioFailure("QMTOOL_PG_TEST_ADMIN_DSN is required for the full acceptance run")
    approved = preflight_isolated_postgres_target()
    return f"port free; pg preflight ok major={approved.major_version}"


def _step_pg_bootstrap(ctx: ScenarioContext) -> str:
    ctx.pg_env = prepare_live_environment()
    pgs.migrate_usermanagement_schema(ctx.pg_env.migrator_dsn)
    ctx.backend_extra_env = build_backend_extra_env(ctx.pg_env)
    return "isolated PG schema migrated"


def _step_backend_start(ctx: ScenarioContext) -> str:
    ctx.harness.start_backend(extra_env=ctx.backend_extra_env)
    health = ctx.harness.wait_for_health()
    return f"backend ready status={health.get('status')}"


def _step_health_and_openapi(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    health = client.request("GET", "/health", auth=False)
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise ScenarioFailure("health payload unexpected")
    openapi = client.request("GET", "/openapi.json", auth=False)
    if not isinstance(openapi, dict) or "paths" not in openapi:
        raise ScenarioFailure("openapi.json missing paths")
    return "health and dev openapi reachable"


def _step_bootstrap_admin_login(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    me, password = complete_bootstrap_admin_session(client)
    ctx.admin_token = client._token or ""
    ctx.bootstrap_admin_password = password
    return f"bootstrap admin session user={me.get('username')}"


def _seed_user(client: AcceptanceHttpClient, *, username: str, password: str, is_qmb: bool = False) -> None:
    status, _headers, _body = client.request_raw(
        "POST",
        "/users",
        body={
            "username": username,
            "password": password,
            "role": "User",
            "is_qmb": is_qmb,
            "must_change_password": False,
        },
    )
    if status not in (201, 409):
        raise ScenarioFailure(f"create user {username} failed with HTTP {status}")


def _step_seed_directory_users(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    client._token = ctx.admin_token
    for username, password, is_qmb in (
        (QMB_USERNAME, QMB_PASSWORD, True),
        (EDITOR_USERNAME, EDITOR_PASSWORD, False),
        (REVIEWER_USERNAME, REVIEWER_PASSWORD, False),
        (APPROVER_USERNAME, APPROVER_PASSWORD, False),
    ):
        _seed_user(client, username=username, password=password, is_qmb=is_qmb)
    ctx.tokens["admin"] = ctx.admin_token
    for role, password in DIRECTORY_ROLE_PASSWORDS.items():
        role_client = AcceptanceHttpClient(ctx.harness.backend_url)
        role_client.login(role, password)
        ctx.tokens[role] = role_client._token or ""
        ctx.user_ids[role] = capture_authenticated_user_id(
            role_client, expected_username=role
        )
    return "directory users seeded and login verified"


def _step_seed_workflow_profile(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    client._token = ctx.tokens["qmb"]
    status, _headers, body = client.request_raw(
        "POST",
        "/documents/workflow-profiles/definitions",
        body={
            "payload": {
                "profile_code": ACCEPTANCE_PROFILE_CODE,
                "label": "J04 Acceptance Flow",
                "control_class": "CONTROLLED",
                "requires_editors": True,
                "requires_reviewers": True,
                "requires_approvers": True,
                "allows_content_changes": True,
                "release_evidence_mode": "WORKFLOW",
                "transitions": _profile_transitions(),
            },
            "change_reason": "j04-acceptance-seed",
        },
    )
    if status not in (200, 409):
        raise ScenarioFailure(f"workflow profile seed failed HTTP {status}")
    code = body.get("profile_code") if isinstance(body, dict) else ACCEPTANCE_PROFILE_CODE
    return f"workflow profile ready code={code}"


def _step_client_process_sessions(ctx: ScenarioContext) -> str:
    login_a = _run_worker(
        ctx.harness,
        home=ctx.harness.client1_home,
        label="client1-login",
        args=[
            "--action",
            "login",
            "--username",
            EDITOR_USERNAME,
            "--password",
            EDITOR_PASSWORD,
        ],
    )
    login_b = _run_worker(
        ctx.harness,
        home=ctx.harness.client2_home,
        label="client2-login",
        args=[
            "--action",
            "login",
            "--username",
            REVIEWER_USERNAME,
            "--password",
            REVIEWER_PASSWORD,
        ],
    )
    ctx.client1_token_fingerprint = str(login_a.get("token_fingerprint", ""))
    ctx.client2_token_fingerprint = str(login_b.get("token_fingerprint", ""))
    if login_a.get("home") == login_b.get("home"):
        raise ScenarioFailure("client workers share the same QMTOOL_HOME")
    if not ctx.client1_token_fingerprint or ctx.client1_token_fingerprint == ctx.client2_token_fingerprint:
        raise ScenarioFailure("client workers did not establish distinct sessions")
    return "two client processes with distinct homes and token fingerprints"


def post_acceptance_document_create(client: AcceptanceHttpClient) -> dict[str, Any]:
    """Create the acceptance document version; fail closed on non-200 responses."""
    status, _headers, payload = client.request_raw(
        "POST",
        "/documents/versions/create",
        body={
            "document_id": ACCEPTANCE_DOC_ID,
            "version": 1,
            "title": ACCEPTANCE_DOC_ID,
            "doc_type": "OTHER",
            "control_class": "CONTROLLED",
            "workflow_profile_id": ACCEPTANCE_PROFILE_CODE,
        },
    )
    return require_version_success(
        status, payload, action="POST /documents/versions/create"
    )


def _step_document_baseline_flow(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    qmb_token = ctx.tokens["qmb"]
    client._token = qmb_token
    created = post_acceptance_document_create(client)
    etag = AcceptanceHttpClient.etag_from_version_payload(created)
    status, _headers, imported = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/import-pdf",
        content=_MINIMAL_PDF,
        headers=_mutation_headers(qmb_token, etag, extra={"Content-Type": "application/pdf"}),
    )
    etag = AcceptanceHttpClient.etag_from_version_payload(
        require_version_success(
            status, imported, action=f"POST /documents/versions/{ACCEPTANCE_DOC_ID}/1/import-pdf"
        )
    )
    status, _headers, assigned = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/assign-roles",
        body=workflow_role_assignment(ctx.user_ids),
        headers=_mutation_headers(qmb_token, etag),
    )
    etag = AcceptanceHttpClient.etag_from_version_payload(
        require_version_success(
            status,
            assigned,
            action=f"POST /documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/assign-roles",
        )
    )
    status, _headers, started = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/start",
        body={"profile_id": ACCEPTANCE_PROFILE_CODE},
        headers=_mutation_headers(qmb_token, etag),
    )
    ctx.document_etag = AcceptanceHttpClient.etag_from_version_payload(
        require_version_success(
            status,
            started,
            action=f"POST /documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/start",
        )
    )
    return f"document {ACCEPTANCE_DOC_ID} in progress etag={ctx.document_etag[:16]}..."


def evaluate_etag_race_payloads(payload_a: Any, payload_b: Any) -> str:
    """Require exactly one HTTP 200 and one HTTP 409 from the two race workers."""
    statuses = sorted(
        [
            int(payload_a.get("status", 0) if isinstance(payload_a, dict) else 0),
            int(payload_b.get("status", 0) if isinstance(payload_b, dict) else 0),
        ]
    )
    if statuses != [200, 409]:
        raise ScenarioFailure(f"etag race statuses expected [200, 409], got {statuses}")
    return "one winner and one 409 on shared etag"


def _etag_race_worker_args(*, etag: str, body: dict[str, object]) -> list[str]:
    return [
        "--action",
        "http",
        "--username",
        QMB_USERNAME,
        "--password",
        QMB_PASSWORD,
        "--method",
        "POST",
        "--path",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/assign-roles",
        "--headers-json",
        json.dumps({"If-Match": etag}),
        "--body-json",
        json.dumps(body),
    ]


def _step_etag_concurrency_race(ctx: ScenarioContext) -> str:
    if not ctx.document_etag:
        raise ScenarioFailure("document etag missing for concurrency race")
    assignment = workflow_role_assignment(ctx.user_ids)
    args_a = _etag_race_worker_args(etag=ctx.document_etag, body=assignment)
    args_b = _etag_race_worker_args(etag=ctx.document_etag, body=dict(assignment))
    proc_a = ctx.harness.start_client_worker(
        home=ctx.harness.client1_home,
        label="race-a",
        args=args_a,
    )
    proc_b = ctx.harness.start_client_worker(
        home=ctx.harness.client2_home,
        label="race-b",
        args=args_b,
    )
    stdout_a, _ = proc_a.popen.communicate(timeout=90.0)
    stdout_b, _ = proc_b.popen.communicate(timeout=90.0)
    payload_a = json.loads(stdout_a or "{}")
    payload_b = json.loads(stdout_b or "{}")
    return evaluate_etag_race_payloads(payload_a, payload_b)


def _refresh_document_etag(client: AcceptanceHttpClient) -> str:
    payload = client.request("GET", f"/documents/versions/{ACCEPTANCE_DOC_ID}/1")
    return AcceptanceHttpClient.etag_from_version_payload(payload)


def _sign_intent_body(password: str) -> dict[str, object]:
    return {
        "sign_intent": {
            "placement": {"page_index": 0, "x": 72.0, "y": 72.0, "target_width": 120.0},
            "layout": {
                "show_signature": True,
                "show_name": True,
                "show_date": True,
                "name_position": "above",
                "date_position": "below",
            },
            "password": password,
            "reason": "J04_M0_ACCEPTANCE",
        }
    }


def _comments_docx_bytes() -> bytes:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:comments xmlns:w="{ns}">'
        '<w:comment w:id="1" w:author="Editor" w:date="2026-08-18T00:00:00Z">'
        "<w:p><w:r><w:t>acceptance native comment</w:t></w:r></w:p>"
        "</w:comment></w:comments>"
    )
    buf = BytesIO()
    with ZipFile(buf, "w") as zf:
        zf.writestr("word/comments.xml", xml)
    return buf.getvalue()


def _activate_signature_asset(client: AcceptanceHttpClient, *, token: str, username: str, password: str) -> None:
    status, _headers, _body = client.request_raw(
        "POST",
        "/signature/assets/import-and-activate",
        content=_MINIMAL_PNG,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/png",
            "X-Filename-Hint": f"accept-{username}.png",
            "X-Signature-Password": password,
        },
    )
    if status != 200:
        raise ScenarioFailure(f"signature asset import failed for {username} HTTP {status}")
    verify = client.request(
        "POST",
        "/signature/verify-password",
        body={"password": password},
    )
    if not isinstance(verify, dict) or not verify.get("ok"):
        raise ScenarioFailure(f"signature verify-password failed for {username}")


def _step_artifacts_transport(ctx: ScenarioContext) -> str:
    client = authenticated_client(ctx.tokens["editor"], ctx.harness.backend_url)
    listed = client.request("GET", f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/artifacts")
    if not isinstance(listed, list) or not listed:
        raise ScenarioFailure("artifact list empty")
    row = listed[0]
    if not isinstance(row, dict):
        raise ScenarioFailure("artifact list row is not an object")
    _assert_no_server_paths(listed, where="artifact list")
    artifact_id = str(row.get("artifact_id") or "").strip()
    listed_sha = str(row.get("sha256") or "").strip()
    if not artifact_id or not listed_sha:
        raise ScenarioFailure("artifact list missing artifact_id or sha256")
    meta = client.request("GET", f"/documents/artifacts/{artifact_id}")
    _assert_no_server_paths(meta, where="artifact metadata")
    status, headers, content = client.request_bytes(
        "GET",
        f"/documents/artifacts/{artifact_id}/content",
    )
    if status != 200:
        raise ScenarioFailure(f"artifact content download failed HTTP {status}")
    digest = hashlib.sha256(content).hexdigest()
    header_sha = _header_value(headers, "X-Content-SHA256")
    header_etag = _header_value(headers, "ETag").strip('"')
    header_length = _header_value(headers, "Content-Length")
    if header_sha != listed_sha or header_sha != digest:
        raise ScenarioFailure(
            f"artifact SHA-256 mismatch listed={listed_sha} header={header_sha} body={digest}"
        )
    if header_etag != listed_sha:
        raise ScenarioFailure(f"artifact ETag expected {listed_sha}, got {header_etag}")
    if header_length and int(header_length) != len(content):
        raise ScenarioFailure(
            f"artifact Content-Length expected {len(content)}, got {header_length}"
        )
    _assert_no_server_paths(dict(headers), where="artifact content headers")
    ctx.source_artifact_id = artifact_id
    ctx.source_artifact_sha256 = digest
    return f"artifact content verified id={artifact_id} sha256={digest[:16]}..."


def _step_signature_verify_password(ctx: ScenarioContext) -> str:
    for username, password in DIRECTORY_ROLE_PASSWORDS.items():
        if username == QMB_USERNAME:
            continue
        client = authenticated_client(ctx.tokens[username], ctx.harness.backend_url)
        _activate_signature_asset(
            client,
            token=ctx.tokens[username],
            username=username,
            password=password,
        )
    return "editor, reviewer, and approver signature assets active and verified"


def _step_signed_editing_complete(ctx: ScenarioContext) -> str:
    editor_client = authenticated_client(ctx.tokens["editor"], ctx.harness.backend_url)
    etag = _refresh_document_etag(editor_client)
    denied_status, _headers, denied_payload = editor_client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/editing-complete",
        body={},
        headers={"If-Match": etag},
    )
    if denied_status != 400:
        raise ScenarioFailure(
            "editing-complete without sign-intent must fail closed, "
            f"got status={denied_status} body={_redact_http_payload(denied_payload)}"
        )
    edited_status, _headers, edited_payload = editor_client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/editing-complete",
        body=_sign_intent_body(EDITOR_PASSWORD),
        headers={"If-Match": etag},
    )
    edited = require_version_success(
        edited_status,
        edited_payload,
        action=f"POST /documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/editing-complete",
    )
    if edited.get("state", {}).get("status") != "IN_REVIEW":
        raise ScenarioFailure(
            f"signed editing-complete did not reach IN_REVIEW, got {edited.get('state')}"
        )
    ctx.document_etag = AcceptanceHttpClient.etag_from_version_payload(edited)
    return "signed editing-complete fail-closed then reached IN_REVIEW"


def _step_pdf_comment_flow(ctx: ScenarioContext) -> str:
    reviewer_client = authenticated_client(ctx.tokens["reviewer"], ctx.harness.backend_url)
    etag = _refresh_document_etag(reviewer_client)
    status, _headers, payload = reviewer_client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/comments",
        body={
            "context": "PDF_REVIEW",
            "page_number": 1,
            "comment_text": "acceptance pdf review note",
        },
        headers=_mutation_headers(ctx.tokens["reviewer"], etag),
    )
    if status != 200 or not isinstance(payload, dict):
        raise ScenarioFailure(
            f"PDF comment create failed status={status} body={_redact_http_payload(payload)}"
        )
    comment_id = str(payload.get("comment_id") or "").strip()
    if not comment_id:
        raise ScenarioFailure("PDF comment create missing comment_id")
    listed = reviewer_client.request(
        "GET",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/comments?context=PDF_REVIEW",
    )
    if not isinstance(listed, list) or not any(
        isinstance(row, dict) and row.get("comment_id") == comment_id for row in listed
    ):
        raise ScenarioFailure("PDF_REVIEW comment list missing the created comment")
    ctx.pdf_comment_id = comment_id
    ctx.document_etag = _refresh_document_etag(reviewer_client)
    return f"PDF_REVIEW comment created id={comment_id}"


def _step_docx_comment_sync(ctx: ScenarioContext) -> str:
    qmb_client = authenticated_client(ctx.tokens["qmb"], ctx.harness.backend_url)
    etag = _refresh_document_etag(qmb_client)
    imported_status, _headers, imported_payload = qmb_client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/import-docx",
        content=_comments_docx_bytes(),
        headers=_mutation_headers(
            ctx.tokens["qmb"],
            etag,
            extra={"Content-Type": DOCX_CONTENT_TYPE},
        ),
    )
    imported = require_version_success(
        imported_status,
        imported_payload,
        action=f"POST /documents/versions/{ACCEPTANCE_DOC_ID}/1/import-docx",
    )
    etag = AcceptanceHttpClient.etag_from_version_payload(imported)
    editor_client = authenticated_client(ctx.tokens["editor"], ctx.harness.backend_url)
    first_status, _headers, first_payload = editor_client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/comments/sync-docx",
        headers=_mutation_headers(ctx.tokens["editor"], etag),
    )
    if first_status != 200 or not isinstance(first_payload, list) or not first_payload:
        raise ScenarioFailure(
            f"DOCX comment sync failed status={first_status} "
            f"body={_redact_http_payload(first_payload)}"
        )
    first_id = str(first_payload[0].get("comment_id") or "").strip()
    if not first_id:
        raise ScenarioFailure("DOCX comment sync missing comment_id")
    if ctx.pdf_comment_id and first_id == ctx.pdf_comment_id:
        raise ScenarioFailure("DOCX sync reused the PDF_REVIEW comment_id")
    second_status, _headers, second_payload = editor_client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/comments/sync-docx",
        headers=_mutation_headers(ctx.tokens["editor"], etag),
    )
    if second_status != 200 or not isinstance(second_payload, list):
        raise ScenarioFailure(
            f"idempotent DOCX comment sync failed status={second_status} "
            f"body={_redact_http_payload(second_payload)}"
        )
    if len(second_payload) != len(first_payload) or str(
        second_payload[0].get("comment_id") or ""
    ) != first_id:
        raise ScenarioFailure("DOCX comment sync was not idempotent")
    reviewer_client = authenticated_client(ctx.tokens["reviewer"], ctx.harness.backend_url)
    pdf_listed = reviewer_client.request(
        "GET",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/comments?context=PDF_REVIEW",
    )
    if ctx.pdf_comment_id and isinstance(pdf_listed, list):
        pdf_ids = {
            str(row.get("comment_id") or "")
            for row in pdf_listed
            if isinstance(row, dict)
        }
        if first_id in pdf_ids:
            raise ScenarioFailure("DOCX comment appeared in PDF_REVIEW listing")
    ctx.docx_comment_id = first_id
    ctx.document_etag = _refresh_document_etag(editor_client)
    return f"DOCX_EDIT comment sync idempotent id={first_id}"


def _assert_artifact_types(listed: Any, *, required: tuple[str, ...]) -> None:
    if not isinstance(listed, list):
        raise ScenarioFailure("artifact list is not an array")
    types = {
        str(row.get("artifact_type") or "")
        for row in listed
        if isinstance(row, dict)
    }
    missing = [name for name in required if name not in types]
    if missing:
        raise ScenarioFailure(f"artifact types missing {missing}; have {sorted(types)}")


def _step_signed_review_approval(ctx: ScenarioContext) -> str:
    reviewer_client = authenticated_client(ctx.tokens["reviewer"], ctx.harness.backend_url)
    etag = _refresh_document_etag(reviewer_client)
    reviewed_status, _headers, reviewed_payload = reviewer_client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/review/accept",
        body=_sign_intent_body(REVIEWER_PASSWORD),
        headers={"If-Match": etag},
    )
    reviewed = require_version_success(
        reviewed_status,
        reviewed_payload,
        action=f"POST /documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/review/accept",
    )
    if reviewed.get("state", {}).get("status") != "IN_APPROVAL":
        raise ScenarioFailure(
            f"signed review did not reach IN_APPROVAL, got {reviewed.get('state')}"
        )
    etag = AcceptanceHttpClient.etag_from_version_payload(reviewed)
    approver_client = authenticated_client(ctx.tokens["approver"], ctx.harness.backend_url)
    approved_status, _headers, approved_payload = approver_client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/approval/accept",
        body=_sign_intent_body(APPROVER_PASSWORD),
        headers={"If-Match": etag},
    )
    approved = require_version_success(
        approved_status,
        approved_payload,
        action=f"POST /documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/approval/accept",
    )
    if approved.get("state", {}).get("status") != "APPROVED":
        raise ScenarioFailure(
            f"signed approval did not reach APPROVED, got {approved.get('state')}"
        )
    ctx.document_etag = AcceptanceHttpClient.etag_from_version_payload(approved)
    listed = approver_client.request(
        "GET", f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/artifacts"
    )
    _assert_artifact_types(listed, required=("SIGNED_PDF", "RELEASED_PDF"))
    return "signed review/approval reached APPROVED with SIGNED_PDF and RELEASED_PDF"


def _step_backend_restart(ctx: ScenarioContext) -> str:
    probe = authenticated_client(ctx.tokens["reviewer"], ctx.harness.backend_url)
    persisted = probe.request("GET", f"/documents/versions/{ACCEPTANCE_DOC_ID}/1")
    ctx.pre_restart_etag = AcceptanceHttpClient.etag_from_version_payload(persisted)
    ctx.pre_restart_status = str(
        persisted.get("state", {}).get("status") if isinstance(persisted, dict) else ""
    )
    if ctx.pre_restart_status != "APPROVED":
        raise ScenarioFailure(
            f"expected APPROVED before restart, got {ctx.pre_restart_status}"
        )
    ctx.pre_restart_tokens = dict(ctx.tokens)
    ctx.harness.stop_process("backend")
    assert_backend_port_free()
    ctx.harness.start_backend(extra_env=ctx.backend_extra_env)
    ctx.harness.wait_for_health()
    return "backend process restarted on same backend home"


def _step_persistence_and_session_contract(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    client._token = ctx.pre_restart_tokens.get("reviewer") or ctx.tokens.get("reviewer")
    if not client._token:
        raise ScenarioFailure("reviewer token missing for persistence check")
    persisted = client.request("GET", f"/documents/versions/{ACCEPTANCE_DOC_ID}/1")
    status = persisted.get("state", {}).get("status") if isinstance(persisted, dict) else None
    etag = AcceptanceHttpClient.etag_from_version_payload(persisted)
    if status != "APPROVED":
        raise ScenarioFailure(f"expected APPROVED after restart, got {status}")
    if etag != ctx.pre_restart_etag:
        raise ScenarioFailure("document etag changed across backend restart")
    me_status, _headers, me = client.request_raw("GET", "/auth/me")
    if me_status != 200 or not isinstance(me, dict) or me.get("username") != "reviewer":
        raise ScenarioFailure("pre-restart reviewer session did not survive backend restart")
    editor_client = AcceptanceHttpClient(ctx.harness.backend_url)
    editor_client._token = ctx.pre_restart_tokens.get("editor") or ctx.tokens.get("editor")
    editor_status, _headers, editor_me = editor_client.request_raw("GET", "/auth/me")
    if editor_status != 200 or editor_me.get("username") != "editor":
        raise ScenarioFailure("pre-restart editor session did not survive backend restart")
    return "document persisted in APPROVED; PG-backed sessions survived restart"


_STEP_HANDLERS: dict[str, Callable[[ScenarioContext], str]] = {
    "preconditions": _step_preconditions,
    "pg_bootstrap": _step_pg_bootstrap,
    "backend_start": _step_backend_start,
    "health_and_openapi": _step_health_and_openapi,
    "bootstrap_admin_login": _step_bootstrap_admin_login,
    "seed_directory_users": _step_seed_directory_users,
    "seed_workflow_profile": _step_seed_workflow_profile,
    "client_process_sessions": _step_client_process_sessions,
    "document_baseline_flow": _step_document_baseline_flow,
    "etag_concurrency_race": _step_etag_concurrency_race,
    "artifacts_transport": _step_artifacts_transport,
    "signature_verify_password": _step_signature_verify_password,
    "signed_editing_complete": _step_signed_editing_complete,
    "pdf_comment_flow": _step_pdf_comment_flow,
    "docx_comment_sync": _step_docx_comment_sync,
    "signed_review_approval": _step_signed_review_approval,
    "backend_restart": _step_backend_restart,
    "persistence_and_session_contract": _step_persistence_and_session_contract,
}


def _run_step(name: str, handler: Callable[[ScenarioContext], str], ctx: ScenarioContext) -> ScenarioStepResult:
    try:
        detail = handler(ctx)
        ctx.harness.write_log(f"step-{name}.log", detail)
        return ScenarioStepResult(name, StepStatus.PASS, detail)
    except ScenarioSkip as exc:
        return ScenarioStepResult(name, StepStatus.SKIP, str(exc))
    except (ScenarioFailure, HarnessBlockedError, HarnessStartupError, DestructivePostgresGuardError) as exc:
        ctx.harness.write_log(f"step-{name}-fail.log", redact_log_text(str(exc)))
        return ScenarioStepResult(name, StepStatus.FAIL, str(exc))
    except Exception as exc:  # noqa: BLE001
        ctx.harness.write_log(f"step-{name}-fail.log", redact_log_text(str(exc)))
        return ScenarioStepResult(name, StepStatus.FAIL, type(exc).__name__)


def run_acceptance_scenario(harness: J04M0RealProcessHarness) -> list[ScenarioStepResult]:
    """Execute the ordered CP08 acceptance scenario against a prepared harness."""
    catalog = scenario_step_catalog()
    missing = [name for name in catalog if name not in _STEP_HANDLERS]
    extra = [name for name in _STEP_HANDLERS if name not in catalog]
    if missing:
        raise ScenarioFailure(f"scenario handlers missing for: {missing}")
    if extra:
        raise ScenarioFailure(f"scenario handlers outside catalog: {extra}")
    ctx = ScenarioContext(harness=harness)
    results: list[ScenarioStepResult] = []
    for name in catalog:
        result = _run_step(name, _STEP_HANDLERS[name], ctx)
        results.append(result)
        if result.status == StepStatus.FAIL:
            break
    summary = json.dumps(
        [{"name": r.name, "status": r.status.value, "detail": r.detail} for r in results],
        ensure_ascii=True,
        indent=2,
    )
    harness.write_log("acceptance-scenario-summary.json", summary)
    return results
