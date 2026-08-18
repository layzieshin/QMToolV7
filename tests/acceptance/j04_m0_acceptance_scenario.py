"""J04-M0 full real-process acceptance scenario (test-only, CP08-R2).

Orchestrates the single planned CP08 real-process gate: PG bootstrap, backend process,
two isolated client worker processes, HTTP use-case coverage, backend restart, and an
explicit Word COM live boundary (executed only with separate opt-in at CP08).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from http.client import HTTPResponse
from typing import Any, Callable

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

WORD_COM_LIVE_ENV = "QMTOOL_J04_WORD_COM_LIVE"
WORD_COM_LIVE_OPT_IN = "I_UNDERSTAND_THIS_IS_A_REAL_WORD_COM_RUN"

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
    document_etag: str = ""
    backend_extra_env: dict[str, str] = field(default_factory=dict)
    client1_token_fingerprint: str = ""
    client2_token_fingerprint: str = ""
    pre_restart_tokens: dict[str, str] = field(default_factory=dict)
    bootstrap_admin_password: str = BOOTSTRAP_ADMIN_PASSWORD


def scenario_step_catalog() -> tuple[str, ...]:
    """Ordered step names for the full acceptance run (CP08 contract)."""
    return (
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
        "training_read_receipt",
        "comments_lifecycle_change_requests",
        "backend_restart",
        "persistence_and_session_contract",
        "word_com_live_boundary",
    )


def word_com_boundary_reason() -> str:
    """Explain why Word COM live is not part of CP08-R2 verification."""
    if os.environ.get(WORD_COM_LIVE_ENV, "").strip() != WORD_COM_LIVE_OPT_IN:
        return (
            f"Word COM live requires {WORD_COM_LIVE_ENV}={WORD_COM_LIVE_OPT_IN!r} "
            "and an interactive Windows session; executed only in CP08 step 4/9, not in R2"
        )
    return "Word COM live opt-in set; execution deferred to CP08 gate (R2 implements handler only)"


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
            "signature_required": False,
            "four_eyes_required": False,
        },
        {
            "transition_no": 2,
            "from_status": "IN_REVIEW",
            "to_status": "IN_APPROVAL",
            "required_role": "REVIEWER",
            "decision_policy": "ONE_OF_POOL",
            "signature_required": False,
            "four_eyes_required": False,
        },
        {
            "transition_no": 3,
            "from_status": "IN_APPROVAL",
            "to_status": "APPROVED",
            "required_role": "APPROVER",
            "decision_policy": "ONE_OF_POOL",
            "signature_required": False,
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
        ("editor", "EditorAccept-Secret1", False),
        ("reviewer", "ReviewAccept-Secret1", False),
        ("approver", "ApproveAccept-Secret1", False),
    ):
        _seed_user(client, username=username, password=password, is_qmb=is_qmb)
    ctx.tokens["admin"] = ctx.admin_token
    for role in ("qmb", "editor", "reviewer", "approver"):
        role_client = AcceptanceHttpClient(ctx.harness.backend_url)
        role_client.login(role, {
            "qmb": QMB_PASSWORD,
            "editor": "EditorAccept-Secret1",
            "reviewer": "ReviewAccept-Secret1",
            "approver": "ApproveAccept-Secret1",
        }[role])
        ctx.tokens[role] = role_client._token or ""
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
            "editor",
            "--password",
            "EditorAccept-Secret1",
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
            "reviewer",
            "--password",
            "ReviewAccept-Secret1",
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
        body={"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]},
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


def _step_etag_concurrency_race(ctx: ScenarioContext) -> str:
    if not ctx.document_etag:
        raise ScenarioFailure("document etag missing for concurrency race")
    shared_headers = json.dumps({"If-Match": ctx.document_etag})
    body_a = json.dumps({"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]})
    body_b = json.dumps({"editors": ["observer"], "reviewers": ["reviewer"], "approvers": ["approver"]})
    proc_a = ctx.harness.start_client_worker(
        home=ctx.harness.client1_home,
        label="race-a",
        args=[
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
            shared_headers,
            "--body-json",
            body_a,
        ],
    )
    proc_b = ctx.harness.start_client_worker(
        home=ctx.harness.client2_home,
        label="race-b",
        args=[
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
            shared_headers,
            "--body-json",
            body_b,
        ],
    )
    stdout_a, _ = proc_a.popen.communicate(timeout=90.0)
    stdout_b, _ = proc_b.popen.communicate(timeout=90.0)
    payload_a = json.loads(stdout_a or "{}")
    payload_b = json.loads(stdout_b or "{}")
    statuses = sorted(int(payload_a.get("status", 0)), int(payload_b.get("status", 0)))
    if statuses != [200, 409]:
        raise ScenarioFailure(f"etag race statuses expected [200, 409], got {statuses}")
    return "one winner and one 409 on shared etag"


def _step_artifacts_transport(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    client._token = ctx.tokens["editor"]
    listed = client.request("GET", f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/artifacts")
    if not isinstance(listed, list) or not listed:
        raise ScenarioFailure("artifact list empty")
    row = listed[0]
    if "storage_key" in row:
        raise ScenarioFailure("artifact list leaked storage_key")
    meta = client.request("GET", f"/documents/artifacts/{row['artifact_id']}")
    if isinstance(meta, dict) and "storage_key" in meta:
        raise ScenarioFailure("artifact metadata leaked storage_key")
    return f"artifacts listed count={len(listed)}"


def _step_signature_verify_password(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    client._token = ctx.tokens["editor"]
    status, _headers, imported = client.request_raw(
        "POST",
        "/signature/assets/import-and-activate",
        content=_MINIMAL_PNG,
        headers={
            "Authorization": f"Bearer {ctx.tokens['editor']}",
            "Content-Type": "image/png",
            "X-Filename-Hint": "accept.png",
        },
    )
    if status != 200:
        raise ScenarioFailure(f"signature asset import failed HTTP {status}")
    verify = client.request(
        "POST",
        "/signature/verify-password",
        body={"password": "EditorAccept-Secret1"},
    )
    if not isinstance(verify, dict) or not verify.get("ok"):
        raise ScenarioFailure("signature verify-password failed")
    return "signature asset active and password verified"


def _step_training_read_receipt(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    client._token = ctx.tokens["editor"]
    read = client.request("GET", f"/documents/versions/{ACCEPTANCE_DOC_ID}/1")
    etag = AcceptanceHttpClient.etag_from_version_payload(read)
    edited = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/editing-complete",
        headers=_mutation_headers(ctx.tokens["editor"], etag),
    )[2]
    etag = AcceptanceHttpClient.etag_from_version_payload(edited)
    reviewed = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/review/accept",
        headers=_mutation_headers(ctx.tokens["reviewer"], etag),
    )[2]
    etag = AcceptanceHttpClient.etag_from_version_payload(reviewed)
    approved = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/approval/accept",
        headers=_mutation_headers(ctx.tokens["approver"], etag),
    )[2]
    if not isinstance(approved, dict) or approved.get("state", {}).get("status") != "APPROVED":
        raise ScenarioFailure("approval did not reach APPROVED")
    client._token = ctx.tokens["editor"]
    opened = client.request(
        "POST",
        "/documents/reads/open-released",
        body={"document_id": ACCEPTANCE_DOC_ID, "version": 1, "source": "training"},
    )
    confirmed = client.request(
        "POST",
        "/documents/reads/confirm",
        body={
            "document_id": ACCEPTANCE_DOC_ID,
            "version": 1,
            "source": "j04-acceptance",
        },
    )
    if not isinstance(confirmed, dict) or confirmed.get("user_id") != "editor":
        raise ScenarioFailure("training read receipt missing editor actor")
    return "approved document training read confirmed"


def _step_comments_lifecycle_change_requests(ctx: ScenarioContext) -> str:
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    qmb_token = ctx.tokens["qmb"]
    client._token = qmb_token
    read = client.request("GET", f"/documents/versions/{ACCEPTANCE_DOC_ID}/1")
    etag = AcceptanceHttpClient.etag_from_version_payload(read)
    created_cr = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/change-requests",
        body={"change_id": "CR-J04-1", "reason": "acceptance", "impact_refs": ["TR-1"]},
        headers=_mutation_headers(qmb_token, etag),
    )
    if created_cr[0] != 200:
        raise ScenarioFailure("change request create failed")
    etag = AcceptanceHttpClient.etag_from_version_payload(created_cr[2])
    comment = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/comments",
        body={"context": "PDF_REVIEW", "page_number": 1, "comment_text": "acceptance note"},
        headers=_mutation_headers(qmb_token, etag),
    )
    if comment[0] != 200:
        raise ScenarioFailure("comment create failed")
    etag = AcceptanceHttpClient.etag_from_version_payload(comment[2])
    client._token = ctx.tokens["qmb"]
    archived = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/lifecycle/archive",
        headers=_mutation_headers(ctx.tokens["qmb"], etag),
    )
    if archived[0] != 200:
        raise ScenarioFailure("lifecycle archive failed")
    if archived[2].get("state", {}).get("status") != "ARCHIVED":
        raise ScenarioFailure("document not archived")
    return "change request, comment, and archive verified"


def _step_backend_restart(ctx: ScenarioContext) -> str:
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
    if status != "ARCHIVED":
        raise ScenarioFailure(f"expected ARCHIVED after restart, got {status}")
    me_status, _headers, me = client.request_raw("GET", "/auth/me")
    if me_status != 200 or not isinstance(me, dict) or me.get("username") != "reviewer":
        raise ScenarioFailure("pre-restart reviewer session did not survive backend restart")
    editor_client = AcceptanceHttpClient(ctx.harness.backend_url)
    editor_client._token = ctx.pre_restart_tokens.get("editor") or ctx.tokens.get("editor")
    editor_status, _headers, editor_me = editor_client.request_raw("GET", "/auth/me")
    if editor_status != 200 or editor_me.get("username") != "editor":
        raise ScenarioFailure("pre-restart editor session did not survive backend restart")
    return "document persisted; PG-backed sessions survived restart"


def _step_word_com_live_boundary(ctx: ScenarioContext) -> str:
    reason = word_com_boundary_reason()
    if os.environ.get(WORD_COM_LIVE_ENV, "").strip() != WORD_COM_LIVE_OPT_IN:
        raise ScenarioSkip(reason)
    client = AcceptanceHttpClient(ctx.harness.backend_url)
    qmb_token = ctx.tokens["qmb"]
    client._token = qmb_token
    read = client.request("GET", f"/documents/versions/{ACCEPTANCE_DOC_ID}/1")
    etag = AcceptanceHttpClient.etag_from_version_payload(read)
    docx_stub = b"PK\x03\x04acceptance-docx-stub"
    status, _headers, body = client.request_raw(
        "POST",
        f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/import-docx",
        content=docx_stub,
        headers=_mutation_headers(
            qmb_token,
            etag,
            extra={
                "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            },
        ),
    )
    if status not in (200, 400, 422, 501):
        raise ScenarioFailure(f"unexpected Word COM live HTTP {status}: {body}")
    return f"word com live attempted status={status}"


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
    "training_read_receipt": _step_training_read_receipt,
    "comments_lifecycle_change_requests": _step_comments_lifecycle_change_requests,
    "backend_restart": _step_backend_restart,
    "persistence_and_session_contract": _step_persistence_and_session_contract,
    "word_com_live_boundary": _step_word_com_live_boundary,
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
    if missing:
        raise ScenarioFailure(f"scenario handlers missing for: {missing}")
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
