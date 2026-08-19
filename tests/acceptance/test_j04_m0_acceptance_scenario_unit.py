"""Unit tests for the J04-M0 acceptance scenario (no live PG / no full CP08 run)."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.acceptance.j04_m0_acceptance_scenario import (
    ACCEPTANCE_DOC_ID,
    AcceptanceHttpClient,
    APPROVER_USERNAME,
    APPROVER_PASSWORD,
    BOOTSTRAP_ADMIN_PASSWORD_AFTER_CHANGE,
    EDITOR_USERNAME,
    EDITOR_PASSWORD,
    FORBIDDEN_STEP_NAMES,
    QMB_PASSWORD,
    QMB_USERNAME,
    REQUIRED_STEP_CATALOG,
    REVIEWER_USERNAME,
    REVIEWER_PASSWORD,
    ScenarioContext,
    ScenarioFailure,
    StepStatus,
    capture_authenticated_user_id,
    authenticated_client,
    complete_bootstrap_admin_session,
    build_backend_extra_env,
    evaluate_etag_race_payloads,
    post_acceptance_document_create,
    require_version_success,
    run_acceptance_scenario,
    scenario_step_catalog,
    workflow_role_assignment,
    _STEP_HANDLERS,
    _profile_transitions,
    _sign_intent_body,
    _step_artifacts_transport,
    _step_document_baseline_flow,
    _step_docx_comment_sync,
    _step_etag_concurrency_race,
    _step_pdf_comment_flow,
    _step_persistence_and_session_contract,
    _step_seed_directory_users,
    _step_signed_editing_complete,
    _step_signed_review_approval,
    _step_signature_verify_password,
)
from tests.acceptance.j04_m0_realprocess_harness import (
    HarnessBlockedError,
    J04M0RealProcessHarness,
    allocate_realprocess_workspace,
    closure_evidence_root,
    repo_root,
    require_inside_closure_evidence,
)
from tests.postgres_live_support import LivePostgresEnv


class _BootstrapAuthHandler(BaseHTTPRequestHandler):
    """Simulates first-admin login: 200 token, /auth/me 409 until password change."""

    changed = False
    me_auths: list[str] = []
    unexpected_409 = False

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send(self, status: int, body: bytes | None = None) -> None:
        self.send_response(status)
        if body is None:
            self.end_headers()
            return
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/auth/login":
            self._send(200, b'{"token":"bootstrap-session-token"}')
            return
        if self.path == "/auth/change-password":
            auth = self.headers.get("Authorization", "")
            payload = self._read_json()
            if auth != "Bearer bootstrap-session-token":
                self._send(401, b'{"detail":{"error":"unauthorized"}}')
                return
            if payload.get("new_password") != BOOTSTRAP_ADMIN_PASSWORD_AFTER_CHANGE:
                self._send(400, b'{"detail":{"error":"weak_password"}}')
                return
            type(self).changed = True
            self._send(204)
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/auth/me":
            self.send_response(404)
            self.end_headers()
            return
        auth = self.headers.get("Authorization", "")
        type(self).me_auths.append(auth)
        if auth != "Bearer bootstrap-session-token":
            self._send(401, b'{"detail":{"error":"unauthorized"}}')
            return
        if type(self).unexpected_409:
            self._send(409, b'{"detail":{"error":"user_exists","message":"user already exists"}}')
            return
        if not type(self).changed:
            self._send(
                409,
                b'{"detail":{"error":"password_change_required","message":"password change required"}}',
            )
            return
        self._send(
            200,
            b'{"user_id":"u1","session_id":"s1","request_id":"r1",'
            b'"username":"j04acceptadmin","global_roles":["ADMIN"],'
            b'"is_qmb":false,"authenticated_at":"2026-08-17T00:00:00+00:00"}',
        )


@pytest.fixture
def bootstrap_auth_url() -> str:
    _BootstrapAuthHandler.changed = False
    _BootstrapAuthHandler.me_auths = []
    _BootstrapAuthHandler.unexpected_409 = False
    server = HTTPServer(("127.0.0.1", 0), _BootstrapAuthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


class _HealthOpenApiHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            body = b'{"status":"ok","service":"backend"}'
        elif self.path == "/openapi.json":
            body = b'{"openapi":"3.1.0","paths":{"/health":{}}}'
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def mock_backend_url() -> str:
    server = HTTPServer(("127.0.0.1", 0), _HealthOpenApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_scenario_step_catalog_matches_m0_contract() -> None:
    catalog = scenario_step_catalog()
    assert catalog == REQUIRED_STEP_CATALOG
    assert catalog == (
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
    assert len(catalog) == 18
    assert tuple(_STEP_HANDLERS.keys()) == catalog
    for forbidden in FORBIDDEN_STEP_NAMES:
        assert forbidden not in catalog
        assert forbidden not in _STEP_HANDLERS


def test_forbidden_scope_is_absent_from_handlers_and_live_gate() -> None:
    import inspect

    from tests.acceptance import test_j04_m0_realprocess as live_gate

    handlers_src = "".join(inspect.getsource(handler) for handler in _STEP_HANDLERS.values())
    live_src = inspect.getsource(live_gate.test_j04_m0_full_realprocess_acceptance)
    for token in (
        "/documents/reads/",
        "/change-requests",
        "/lifecycle/archive",
        "read_receipt",
        "word_com_live_boundary",
        "document_release_flow",
        "comments_lifecycle_change_requests",
    ):
        assert token not in handlers_src
    assert "scenario_step_catalog" in live_src
    assert "word_com_live_boundary" not in inspect.getsource(_STEP_HANDLERS["persistence_and_session_contract"])


def test_profile_transitions_require_signatures_for_all_three() -> None:
    transitions = _profile_transitions()
    assert len(transitions) == 3
    assert [item["from_status"] for item in transitions] == ["DRAFT", "IN_REVIEW", "IN_APPROVAL"]
    assert [item["to_status"] for item in transitions] == ["IN_REVIEW", "IN_APPROVAL", "APPROVED"]
    assert all(item["signature_required"] is True for item in transitions)


def test_sign_intent_body_requires_password_argument() -> None:
    import inspect

    signature = inspect.signature(_sign_intent_body)
    assert list(signature.parameters) == ["password"]
    assert signature.parameters["password"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        _sign_intent_body()  # type: ignore[call-arg]
    payload = _sign_intent_body(EDITOR_PASSWORD)
    assert payload["sign_intent"]["password"] == EDITOR_PASSWORD
    assert payload["sign_intent"]["password"] is not None
    from tests.acceptance.j04_m0_acceptance_scenario import _activate_signature_asset

    editing_src = inspect.getsource(_step_signed_editing_complete)
    review_src = inspect.getsource(_step_signed_review_approval)
    activate_src = inspect.getsource(_activate_signature_asset)
    assert "EDITOR_PASSWORD" in editing_src
    assert "REVIEWER_PASSWORD" in review_src
    assert "APPROVER_PASSWORD" in review_src
    assert "X-Signature-Password" in activate_src
    assert "password: None" not in editing_src
    assert "password: None" not in review_src


def test_build_backend_extra_env_uses_runtime_dsn_only() -> None:
    env = LivePostgresEnv(
        admin_dsn="postgresql://admin:secret@127.0.0.1:5432/qmtool_j04_destructive_test",
        migrator_dsn="postgresql://migrator:secret@127.0.0.1:5432/qmtool_j04_destructive_test",
        runtime_dsn="postgresql://runtime:secret@127.0.0.1:5432/qmtool_j04_destructive_test",
        migrator_password="migrator-secret",
        runtime_password="runtime-secret",
    )
    backend_env = build_backend_extra_env(env)
    assert backend_env["QMTOOL_PG_DSN"] == env.runtime_dsn
    assert backend_env["QMTOOL_PG_DSN"] != env.admin_dsn
    assert backend_env["QMTOOL_BOOTSTRAP_ADMIN_USERNAME"]


def test_acceptance_http_client_reads_health_and_openapi(mock_backend_url: str) -> None:
    client = AcceptanceHttpClient(mock_backend_url)
    health = client.request("GET", "/health", auth=False)
    openapi = client.request("GET", "/openapi.json", auth=False)
    assert health["status"] == "ok"
    assert "paths" in openapi


def test_bootstrap_admin_session_completes_password_change_then_me_200(
    bootstrap_auth_url: str,
) -> None:
    client = AcceptanceHttpClient(bootstrap_auth_url)
    me, password = complete_bootstrap_admin_session(client)
    assert me["username"] == "j04acceptadmin"
    assert password == BOOTSTRAP_ADMIN_PASSWORD_AFTER_CHANGE
    assert client._token == "bootstrap-session-token"
    assert _BootstrapAuthHandler.me_auths
    assert all(item == "Bearer bootstrap-session-token" for item in _BootstrapAuthHandler.me_auths)
    assert _BootstrapAuthHandler.changed is True


def test_bootstrap_admin_session_rejects_unexpected_409(bootstrap_auth_url: str) -> None:
    _BootstrapAuthHandler.unexpected_409 = True
    client = AcceptanceHttpClient(bootstrap_auth_url)
    with pytest.raises(ScenarioFailure, match="bootstrap admin /auth/me failed status=409"):
        complete_bootstrap_admin_session(client)


def test_etag_from_version_payload_reads_etag_and_last_event_id() -> None:
    assert AcceptanceHttpClient.etag_from_version_payload({"etag": "abc"}) == "abc"
    assert AcceptanceHttpClient.etag_from_version_payload({"state": {"last_event_id": "evt-1"}}) == "evt-1"


def test_require_version_success_reports_403_forbidden_not_missing_etag() -> None:
    payload = {"detail": {"error": "forbidden", "message": "effective QMB or delegated create permission required"}}
    with pytest.raises(ScenarioFailure, match="status=403") as exc_info:
        require_version_success(403, payload, action="POST /documents/versions/create")
    message = str(exc_info.value)
    assert "error=forbidden" in message
    assert "version payload missing etag" not in message


class _DocumentCreateHandler(BaseHTTPRequestHandler):
    create_auths: list[str] = []

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/documents/versions/create":
            self.send_response(404)
            self.end_headers()
            return
        auth = self.headers.get("Authorization", "")
        type(self).create_auths.append(auth)
        if auth == "Bearer qmb-session-token":
            body = b'{"etag":"etag-qmb","state":{"status":"DRAFT"}}'
            self.send_response(200)
        else:
            body = b'{"detail":{"error":"forbidden","message":"effective QMB or delegated create permission required"}}'
            self.send_response(403)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def document_create_url() -> str:
    _DocumentCreateHandler.create_auths = []
    server = HTTPServer(("127.0.0.1", 0), _DocumentCreateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_acceptance_document_create_with_qmb_token_returns_etag(document_create_url: str) -> None:
    client = AcceptanceHttpClient(document_create_url)
    client._token = "qmb-session-token"
    created = post_acceptance_document_create(client)
    assert created["etag"] == "etag-qmb"
    assert _DocumentCreateHandler.create_auths == ["Bearer qmb-session-token"]


def test_acceptance_document_create_with_admin_token_surfaces_403(document_create_url: str) -> None:
    client = AcceptanceHttpClient(document_create_url)
    client._token = "admin-session-token"
    with pytest.raises(ScenarioFailure, match="status=403") as exc_info:
        post_acceptance_document_create(client)
    message = str(exc_info.value)
    assert "error=forbidden" in message
    assert "version payload missing etag" not in message
    assert _DocumentCreateHandler.create_auths == ["Bearer admin-session-token"]


EDITOR_USER_ID = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
REVIEWER_USER_ID = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
APPROVER_USER_ID = "cccccccc-3333-4333-8333-cccccccccccc"
QMB_USER_ID = "dddddddd-4444-4444-8444-dddddddddddd"
_ROLE_USER_IDS = {
    EDITOR_USERNAME: EDITOR_USER_ID,
    REVIEWER_USERNAME: REVIEWER_USER_ID,
    APPROVER_USERNAME: APPROVER_USER_ID,
    QMB_USERNAME: QMB_USER_ID,
}


def test_document_baseline_and_docx_import_use_seeded_qmb_not_bootstrap_admin() -> None:
    import inspect

    baseline = inspect.getsource(_step_document_baseline_flow)
    docx = inspect.getsource(_step_docx_comment_sync)
    assert 'tokens["qmb"]' in baseline
    assert 'tokens["admin"]' not in baseline
    assert 'tokens["qmb"]' in docx
    assert 'tokens["admin"]' not in docx


class _FakeRaceHarness:
    """In-process stand-in for start_client_worker; does not spawn OS processes."""

    def __init__(self, tmp_path: Path, responses: list[dict[str, Any]]) -> None:
        self.client1_home = tmp_path / "client1-home"
        self.client2_home = tmp_path / "client2-home"
        self.client1_home.mkdir(parents=True, exist_ok=True)
        self.client2_home.mkdir(parents=True, exist_ok=True)
        self._responses = list(responses)
        self.worker_calls: list[dict[str, Any]] = []

    def start_client_worker(self, *, home, args, label, extra_env=None):
        self.worker_calls.append({"home": home, "args": list(args), "label": label})
        payload = json.dumps(self._responses.pop(0))
        popen = SimpleNamespace(communicate=lambda timeout=None: (payload, ""), returncode=0)
        return SimpleNamespace(popen=popen)


def _race_ctx(tmp_path: Path, responses: list[dict[str, Any]]) -> tuple[ScenarioContext, _FakeRaceHarness]:
    harness = _FakeRaceHarness(tmp_path, responses)
    ctx = ScenarioContext(harness=harness)  # type: ignore[arg-type]
    ctx.document_etag = "etag-race-1"
    ctx.user_ids.update(_ROLE_USER_IDS)
    return ctx, harness


def _assert_assignment_uses_user_ids_not_usernames(body: dict[str, Any]) -> None:
    values = list(body.get("editors", [])) + list(body.get("reviewers", [])) + list(
        body.get("approvers", [])
    )
    assert body == {
        "editors": [EDITOR_USER_ID],
        "reviewers": [REVIEWER_USER_ID],
        "approvers": [APPROVER_USER_ID],
    }
    assert EDITOR_USERNAME not in values
    assert REVIEWER_USERNAME not in values
    assert APPROVER_USERNAME not in values


def _assert_user_id_qmb_race_args(harness: _FakeRaceHarness) -> None:
    expected = workflow_role_assignment(_ROLE_USER_IDS)
    assert len(harness.worker_calls) == 2
    for call in harness.worker_calls:
        args = call["args"]
        assert "--username" in args
        assert args[args.index("--username") + 1] == QMB_USERNAME
        assert args[args.index("--password") + 1] == QMB_PASSWORD
        body = json.loads(args[args.index("--body-json") + 1])
        assert body == expected
        _assert_assignment_uses_user_ids_not_usernames(body)


@pytest.mark.parametrize(
    "responses",
    (
        [{"status": 200}, {"status": 409}],
        [{"status": 409}, {"status": 200}],
    ),
)
def test_etag_concurrency_race_accepts_either_winner_order(
    tmp_path: Path, responses: list[dict[str, Any]]
) -> None:
    ctx, harness = _race_ctx(tmp_path, responses)
    detail = _step_etag_concurrency_race(ctx)
    assert detail == "one winner and one 409 on shared etag"
    _assert_user_id_qmb_race_args(harness)


def test_etag_concurrency_race_rejects_two_winners(tmp_path: Path) -> None:
    ctx, harness = _race_ctx(tmp_path, [{"status": 200}, {"status": 200}])
    with pytest.raises(ScenarioFailure, match=r"got \[200, 200\]"):
        _step_etag_concurrency_race(ctx)
    _assert_user_id_qmb_race_args(harness)


def test_evaluate_etag_race_payloads_sorts_two_statuses_as_one_iterable() -> None:
    assert evaluate_etag_race_payloads({"status": 409}, {"status": 200}) == (
        "one winner and one 409 on shared etag"
    )


def test_workflow_role_assignment_uses_user_ids_never_usernames() -> None:
    body = workflow_role_assignment(_ROLE_USER_IDS)
    _assert_assignment_uses_user_ids_not_usernames(body)


def test_workflow_role_assignment_requires_all_role_user_ids() -> None:
    with pytest.raises(ScenarioFailure, match="role user_id missing"):
        workflow_role_assignment({EDITOR_USERNAME: EDITOR_USER_ID})


class _AuthMeHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/auth/me":
            self.send_response(404)
            self.end_headers()
            return
        if self.headers.get("Authorization") != "Bearer role-session-token":
            body = b'{"detail":{"error":"unauthorized"}}'
            self.send_response(401)
        else:
            body = (
                b'{"user_id":"'
                + EDITOR_USER_ID.encode("ascii")
                + b'","username":"editor","global_roles":[]}'
            )
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def auth_me_url() -> str:
    server = HTTPServer(("127.0.0.1", 0), _AuthMeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_capture_authenticated_user_id_reads_me_not_username(auth_me_url: str) -> None:
    client = AcceptanceHttpClient(auth_me_url)
    client._token = "role-session-token"
    user_id = capture_authenticated_user_id(client, expected_username=EDITOR_USERNAME)
    assert user_id == EDITOR_USER_ID
    assert user_id != EDITOR_USERNAME


def test_capture_authenticated_user_id_rejects_username_mismatch(auth_me_url: str) -> None:
    client = AcceptanceHttpClient(auth_me_url)
    client._token = "role-session-token"
    with pytest.raises(ScenarioFailure, match="username expected 'reviewer'"):
        capture_authenticated_user_id(client, expected_username=REVIEWER_USERNAME)


class _DirectorySeedHandler(BaseHTTPRequestHandler):
    """Seed users, then login + /auth/me with user_ids distinct from usernames."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/users":
            self._send(201, b'{"ok":true}')
            return
        if self.path == "/auth/login":
            username = str(self._read_json().get("username", ""))
            token = f"token-{username}"
            self._send(200, json.dumps({"token": token}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/auth/me":
            self.send_response(404)
            self.end_headers()
            return
        auth = self.headers.get("Authorization", "")
        username = auth.removeprefix("Bearer token-")
        user_id = _ROLE_USER_IDS.get(username, "")
        if not user_id:
            self._send(401, b'{"detail":{"error":"unauthorized"}}')
            return
        self._send(
            200,
            json.dumps({"user_id": user_id, "username": username}).encode("utf-8"),
        )


@pytest.fixture
def directory_seed_url() -> str:
    server = HTTPServer(("127.0.0.1", 0), _DirectorySeedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_seed_directory_users_stores_user_ids_from_auth_me(
    tmp_path: Path, directory_seed_url: str
) -> None:
    harness = SimpleNamespace(backend_url=directory_seed_url)
    ctx = ScenarioContext(harness=harness)  # type: ignore[arg-type]
    ctx.admin_token = "admin-session-token"
    detail = _step_seed_directory_users(ctx)
    assert detail == "directory users seeded and login verified"
    assert ctx.user_ids[EDITOR_USERNAME] == EDITOR_USER_ID
    assert ctx.user_ids[REVIEWER_USERNAME] == REVIEWER_USER_ID
    assert ctx.user_ids[APPROVER_USERNAME] == APPROVER_USER_ID
    assert ctx.user_ids[QMB_USERNAME] == QMB_USER_ID
    assert ctx.user_ids[EDITOR_USERNAME] != EDITOR_USERNAME


class _BaselineAssignHandler(BaseHTTPRequestHandler):
    assign_bodies: list[dict[str, Any]] = []

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send_version(self) -> None:
        body = b'{"etag":"etag-next","state":{"status":"IN_PROGRESS"}}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path.endswith("/workflow/assign-roles"):
            type(self).assign_bodies.append(self._read_json())
            self._send_version()
            return
        if (
            self.path == "/documents/versions/create"
            or self.path.endswith("/import-pdf")
            or self.path.endswith("/workflow/start")
        ):
            self._send_version()
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture
def baseline_assign_url() -> str:
    _BaselineAssignHandler.assign_bodies = []
    server = HTTPServer(("127.0.0.1", 0), _BaselineAssignHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_baseline_and_race_requests_send_user_ids_never_usernames(
    tmp_path: Path, baseline_assign_url: str
) -> None:
    race_harness = _FakeRaceHarness(tmp_path, [{"status": 200}, {"status": 409}])
    race_harness.backend_url = baseline_assign_url  # type: ignore[attr-defined]
    ctx = ScenarioContext(harness=race_harness)  # type: ignore[arg-type]
    ctx.tokens[QMB_USERNAME] = "qmb-session-token"
    ctx.user_ids.update(_ROLE_USER_IDS)
    _step_document_baseline_flow(ctx)
    _step_etag_concurrency_race(ctx)

    assert _BaselineAssignHandler.assign_bodies
    baseline_body = _BaselineAssignHandler.assign_bodies[0]
    expected = workflow_role_assignment(_ROLE_USER_IDS)
    assert baseline_body == expected
    _assert_assignment_uses_user_ids_not_usernames(baseline_body)
    _assert_user_id_qmb_race_args(race_harness)


def _workflow_ctx(backend_url: str) -> ScenarioContext:
    ctx = ScenarioContext(harness=SimpleNamespace(backend_url=backend_url))  # type: ignore[arg-type]
    ctx.tokens.update(
        {
            EDITOR_USERNAME: "editor-token",
            REVIEWER_USERNAME: "reviewer-token",
            APPROVER_USERNAME: "approver-token",
            QMB_USERNAME: "qmb-token",
        }
    )
    ctx.user_ids.update(_ROLE_USER_IDS)
    return ctx


class _JsonHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _send_json(self, status: int, body: Any) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_bytes(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_token(self) -> str:
        return self.headers.get("Authorization", "").removeprefix("Bearer ")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


class _ArtifactTransportHandler(_JsonHandler):
    listed_sha = "a" * 64
    pdf_bytes = b"%PDF-1.4 artifact-body\n%%EOF\n"
    leaked = False

    def do_GET(self) -> None:  # noqa: N802
        if self.path == f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/artifacts":
            row = {
                "artifact_id": "art-source-1",
                "sha256": type(self).listed_sha,
                "artifact_type": "SOURCE_PDF",
            }
            if type(self).leaked:
                row["storage_key"] = "objects/ab/secret.pdf"
            self._send_json(200, [row])
            return
        if self.path == "/documents/artifacts/art-source-1":
            self._send_json(200, {"artifact_id": "art-source-1", "sha256": type(self).listed_sha})
            return
        if self.path == "/documents/artifacts/art-source-1/content":
            import hashlib

            digest = hashlib.sha256(type(self).pdf_bytes).hexdigest()
            self._send_bytes(
                200,
                type(self).pdf_bytes,
                {
                    "Content-Type": "application/pdf",
                    "ETag": digest,
                    "X-Content-SHA256": digest,
                },
            )
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture
def artifact_transport_url() -> str:
    import hashlib

    _ArtifactTransportHandler.leaked = False
    _ArtifactTransportHandler.pdf_bytes = b"%PDF-1.4 artifact-body\n%%EOF\n"
    _ArtifactTransportHandler.listed_sha = hashlib.sha256(_ArtifactTransportHandler.pdf_bytes).hexdigest()
    server = HTTPServer(("127.0.0.1", 0), _ArtifactTransportHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_artifacts_transport_checks_content_hash_etag_and_length(artifact_transport_url: str) -> None:
    import hashlib
    import inspect

    ctx = _workflow_ctx(artifact_transport_url)
    detail = _step_artifacts_transport(ctx)
    digest = hashlib.sha256(_ArtifactTransportHandler.pdf_bytes).hexdigest()
    assert ctx.source_artifact_id == "art-source-1"
    assert ctx.source_artifact_sha256 == digest
    assert digest[:16] in detail
    source = inspect.getsource(_step_artifacts_transport)
    assert "/documents/artifacts/" in source
    assert "/content" in source
    assert "X-Content-SHA256" in source
    assert "Content-Length" in source
    assert "hashlib.sha256" in source


def test_artifacts_transport_rejects_storage_key_leak(artifact_transport_url: str) -> None:
    _ArtifactTransportHandler.leaked = True
    ctx = _workflow_ctx(artifact_transport_url)
    with pytest.raises(ScenarioFailure, match="storage_key"):
        _step_artifacts_transport(ctx)


class _SignatureVerifyHandler(_JsonHandler):
    actors: list[str] = []
    verified: list[str] = []
    header_passwords: list[tuple[str, str]] = []

    def do_POST(self) -> None:  # noqa: N802
        token = self._auth_token()
        if self.path == "/signature/assets/import-and-activate":
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length:
                self.rfile.read(length)
            header_password = self.headers.get("X-Signature-Password", "")
            type(self).actors.append(token)
            type(self).header_passwords.append((token, header_password))
            expected = {
                "editor-token": EDITOR_PASSWORD,
                "reviewer-token": REVIEWER_PASSWORD,
                "approver-token": APPROVER_PASSWORD,
            }.get(token)
            if header_password != expected:
                self._send_json(400, {"detail": {"error": "password_required"}})
                return
            self._send_json(200, {"ok": True})
            return
        if self.path == "/signature/verify-password":
            type(self).verified.append(token)
            body = self._read_json()
            expected = {
                "editor-token": EDITOR_PASSWORD,
                "reviewer-token": REVIEWER_PASSWORD,
                "approver-token": APPROVER_PASSWORD,
            }.get(token)
            if body.get("password") != expected:
                self._send_json(400, {"ok": False})
                return
            self._send_json(200, {"ok": True})
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture
def signature_verify_url() -> str:
    _SignatureVerifyHandler.actors = []
    _SignatureVerifyHandler.verified = []
    _SignatureVerifyHandler.header_passwords = []
    server = HTTPServer(("127.0.0.1", 0), _SignatureVerifyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_signature_verify_password_activates_editor_reviewer_approver(
    signature_verify_url: str,
) -> None:
    ctx = _workflow_ctx(signature_verify_url)
    detail = _step_signature_verify_password(ctx)
    assert "editor" in detail and "reviewer" in detail and "approver" in detail
    assert _SignatureVerifyHandler.actors == [
        "editor-token",
        "reviewer-token",
        "approver-token",
    ]
    assert _SignatureVerifyHandler.verified == [
        "editor-token",
        "reviewer-token",
        "approver-token",
    ]
    assert _SignatureVerifyHandler.header_passwords == [
        ("editor-token", EDITOR_PASSWORD),
        ("reviewer-token", REVIEWER_PASSWORD),
        ("approver-token", APPROVER_PASSWORD),
    ]


class _SignedEditingHandler(_JsonHandler):
    actor_sequence: list[tuple[str, str]] = []
    passwords: list[tuple[str, object]] = []
    saw_empty_intent = False

    def do_GET(self) -> None:  # noqa: N802
        if self.path != f"/documents/versions/{ACCEPTANCE_DOC_ID}/1":
            self.send_response(404)
            self.end_headers()
            return
        type(self).actor_sequence.append(("GET version", self._auth_token()))
        self._send_json(200, {"etag": "etag-progress", "state": {"status": "IN_PROGRESS"}})

    def do_POST(self) -> None:  # noqa: N802
        token = self._auth_token()
        if self.path != f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/editing-complete":
            self.send_response(404)
            self.end_headers()
            return
        body = self._read_json()
        intent = body.get("sign_intent") if isinstance(body, dict) else None
        password = intent.get("password") if isinstance(intent, dict) else None
        type(self).actor_sequence.append(("editing-complete", token))
        type(self).passwords.append((token, password))
        if not intent:
            type(self).saw_empty_intent = True
            self._send_json(400, {"detail": {"error": "validation_error"}})
            return
        if password != EDITOR_PASSWORD:
            self._send_json(400, {"detail": {"error": "password_required"}})
            return
        self._send_json(200, {"etag": "etag-review", "state": {"status": "IN_REVIEW"}})


@pytest.fixture
def signed_editing_url() -> str:
    _SignedEditingHandler.actor_sequence = []
    _SignedEditingHandler.passwords = []
    _SignedEditingHandler.saw_empty_intent = False
    server = HTTPServer(("127.0.0.1", 0), _SignedEditingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_signed_editing_complete_fail_closed_then_reaches_in_review(signed_editing_url: str) -> None:
    ctx = _workflow_ctx(signed_editing_url)
    detail = _step_signed_editing_complete(ctx)
    assert "IN_REVIEW" in detail
    assert _SignedEditingHandler.saw_empty_intent is True
    assert _SignedEditingHandler.actor_sequence == [
        ("GET version", "editor-token"),
        ("editing-complete", "editor-token"),
        ("editing-complete", "editor-token"),
    ]
    assert _SignedEditingHandler.passwords == [
        ("editor-token", None),
        ("editor-token", EDITOR_PASSWORD),
    ]
    assert ctx.document_etag == "etag-review"
    assert _sign_intent_body(EDITOR_PASSWORD)["sign_intent"]["password"] == EDITOR_PASSWORD


class _SignedReviewHandler(_JsonHandler):
    actor_sequence: list[tuple[str, str]] = []
    passwords: list[tuple[str, object]] = []
    review_status = 200

    def do_GET(self) -> None:  # noqa: N802
        if self.path == f"/documents/versions/{ACCEPTANCE_DOC_ID}/1":
            type(self).actor_sequence.append(("GET version", self._auth_token()))
            self._send_json(200, {"etag": "etag-review", "state": {"status": "IN_REVIEW"}})
            return
        if self.path == f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/artifacts":
            type(self).actor_sequence.append(("GET artifacts", self._auth_token()))
            self._send_json(
                200,
                [
                    {"artifact_id": "a1", "artifact_type": "SIGNED_PDF"},
                    {"artifact_id": "a2", "artifact_type": "RELEASED_PDF"},
                ],
            )
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        token = self._auth_token()
        body = self._read_json()
        intent = body.get("sign_intent") if isinstance(body, dict) else None
        password = intent.get("password") if isinstance(intent, dict) else None
        expected = {
            "reviewer-token": REVIEWER_PASSWORD,
            "approver-token": APPROVER_PASSWORD,
        }.get(token)
        if self.path == f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/review/accept":
            type(self).actor_sequence.append(("review/accept", token))
            type(self).passwords.append((token, password))
            if type(self).review_status != 200:
                self._send_json(
                    type(self).review_status,
                    {"detail": {"error": "forbidden", "message": "reviewer required"}},
                )
                return
            if not intent:
                self._send_json(400, {"detail": {"error": "validation_error"}})
                return
            if password != expected:
                self._send_json(400, {"detail": {"error": "password_required"}})
                return
            self._send_json(200, {"etag": "etag-approval", "state": {"status": "IN_APPROVAL"}})
            return
        if self.path == f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/workflow/approval/accept":
            type(self).actor_sequence.append(("approval/accept", token))
            type(self).passwords.append((token, password))
            if not intent:
                self._send_json(400, {"detail": {"error": "validation_error"}})
                return
            if password != expected:
                self._send_json(400, {"detail": {"error": "password_required"}})
                return
            self._send_json(200, {"etag": "etag-approved", "state": {"status": "APPROVED"}})
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture
def signed_review_url() -> str:
    _SignedReviewHandler.actor_sequence = []
    _SignedReviewHandler.passwords = []
    _SignedReviewHandler.review_status = 200
    server = HTTPServer(("127.0.0.1", 0), _SignedReviewHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_signed_review_approval_uses_reviewer_then_approver(signed_review_url: str) -> None:
    ctx = _workflow_ctx(signed_review_url)
    detail = _step_signed_review_approval(ctx)
    assert "APPROVED" in detail
    assert "SIGNED_PDF" in detail and "RELEASED_PDF" in detail
    assert _SignedReviewHandler.actor_sequence == [
        ("GET version", "reviewer-token"),
        ("review/accept", "reviewer-token"),
        ("approval/accept", "approver-token"),
        ("GET artifacts", "approver-token"),
    ]
    assert ctx.document_etag == "etag-approved"
    assert _SignedReviewHandler.passwords == [
        ("reviewer-token", REVIEWER_PASSWORD),
        ("approver-token", APPROVER_PASSWORD),
    ]


def test_signed_review_approval_surfaces_review_forbidden_with_action(signed_review_url: str) -> None:
    _SignedReviewHandler.review_status = 403
    ctx = _workflow_ctx(signed_review_url)
    with pytest.raises(
        ScenarioFailure,
        match=r"POST /documents/versions/.*/workflow/review/accept failed status=403 error=forbidden",
    ):
        _step_signed_review_approval(ctx)
    assert ("review/accept", "reviewer-token") in _SignedReviewHandler.actor_sequence
    assert ("approval/accept", "approver-token") not in _SignedReviewHandler.actor_sequence


class _CommentFlowHandler(_JsonHandler):
    pdf_created = 0
    sync_calls = 0
    version_etag = "etag-review"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == f"/documents/versions/{ACCEPTANCE_DOC_ID}/1":
            self._send_json(
                200,
                {"etag": type(self).version_etag, "state": {"status": "IN_REVIEW"}},
            )
            return
        if self.path.startswith(f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/comments"):
            if "PDF_REVIEW" in self.path:
                self._send_json(200, [{"comment_id": "pdf-1", "context": "PDF_REVIEW"}])
                return
            self._send_json(200, [{"comment_id": "docx-1", "context": "DOCX_EDIT"}])
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == f"/documents/versions/{ACCEPTANCE_DOC_ID}/1/comments":
            body = self._read_json()
            type(self).pdf_created += 1
            assert body.get("context") == "PDF_REVIEW"
            type(self).version_etag = "etag-after-pdf"
            self._send_json(200, {"comment_id": "pdf-1", "context": "PDF_REVIEW"})
            return
        if self.path.endswith("/import-docx"):
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length:
                self.rfile.read(length)
            type(self).version_etag = "etag-after-docx"
            self._send_json(200, {"etag": "etag-after-docx", "state": {"status": "IN_REVIEW"}})
            return
        if self.path.endswith("/comments/sync-docx"):
            type(self).sync_calls += 1
            self._send_json(200, [{"comment_id": "docx-1", "context": "DOCX_EDIT"}])
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture
def comment_flow_url() -> str:
    _CommentFlowHandler.pdf_created = 0
    _CommentFlowHandler.sync_calls = 0
    _CommentFlowHandler.version_etag = "etag-review"
    server = HTTPServer(("127.0.0.1", 0), _CommentFlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_pdf_and_docx_comments_stay_separate_and_docx_sync_is_idempotent(
    comment_flow_url: str,
) -> None:
    ctx = _workflow_ctx(comment_flow_url)
    pdf_detail = _step_pdf_comment_flow(ctx)
    docx_detail = _step_docx_comment_sync(ctx)
    assert ctx.pdf_comment_id == "pdf-1"
    assert ctx.docx_comment_id == "docx-1"
    assert ctx.pdf_comment_id != ctx.docx_comment_id
    assert "PDF_REVIEW" in pdf_detail
    assert "idempotent" in docx_detail
    assert _CommentFlowHandler.pdf_created == 1
    assert _CommentFlowHandler.sync_calls == 2


class _PersistenceHandler(_JsonHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == f"/documents/versions/{ACCEPTANCE_DOC_ID}/1":
            self._send_json(200, {"etag": "etag-approved", "state": {"status": "APPROVED"}})
            return
        if self.path == "/auth/me":
            token = self._auth_token()
            username = "reviewer" if token == "reviewer-token" else "editor"
            self._send_json(200, {"username": username, "user_id": "u"})
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture
def persistence_url() -> str:
    server = HTTPServer(("127.0.0.1", 0), _PersistenceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_persistence_contract_expects_approved_not_archived(persistence_url: str) -> None:
    import inspect

    ctx = _workflow_ctx(persistence_url)
    ctx.pre_restart_tokens = dict(ctx.tokens)
    ctx.pre_restart_etag = "etag-approved"
    detail = _step_persistence_and_session_contract(ctx)
    assert "APPROVED" in detail
    source = inspect.getsource(_step_persistence_and_session_contract)
    assert "APPROVED" in source
    assert "ARCHIVED" not in source
    restart_src = inspect.getsource(_STEP_HANDLERS["backend_restart"])
    assert "APPROVED" in restart_src
    assert "ARCHIVED" not in restart_src


def test_authenticated_client_keeps_bound_token() -> None:
    client = authenticated_client("reviewer-token", "http://example.invalid")
    assert client._token == "reviewer-token"


def test_harness_stop_process_only_terminates_requested_label(tmp_path: Path) -> None:
    import subprocess
    import sys

    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    sleeper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    keeper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    harness._register_process(sleeper, label="backend")
    harness._register_process(keeper, label="client-a")
    harness.stop_process("backend")
    assert sleeper.poll() is not None
    assert keeper.poll() is None
    harness.cleanup()


def test_run_acceptance_scenario_stops_on_precondition_failure(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    results = run_acceptance_scenario(harness)
    assert results[0].name == "preconditions"
    assert results[0].status == StepStatus.FAIL
    assert len(results) == 1
    summary_path = tmp_path / "ws" / "logs" / "acceptance-scenario-summary.json"
    assert summary_path.is_file()
    assert ACCEPTANCE_DOC_ID in summary_path.read_text(encoding="utf-8") or "preconditions" in summary_path.read_text(
        encoding="utf-8"
    )


def test_scenario_context_initializes_for_orchestrator(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    ctx = ScenarioContext(harness=harness)
    assert ctx.harness.client1_home != ctx.harness.client2_home
    assert ctx.user_ids == {}


def test_allocate_realprocess_workspace_is_unique_and_inside_closure(tmp_path: Path) -> None:
    first = allocate_realprocess_workspace()
    second = allocate_realprocess_workspace()
    root = closure_evidence_root()
    tmp_resolved = tmp_path.resolve()
    assert first != second
    assert first.name != second.name
    for workspace in (first, second):
        assert workspace.is_dir()
        assert workspace.resolve().is_relative_to(root)
        assert not workspace.resolve().is_relative_to(tmp_resolved)
        assert "cp08-realprocess-ws" in workspace.parts


def test_require_inside_closure_evidence_rejects_paths_outside_build() -> None:
    with pytest.raises(HarnessBlockedError, match="must resolve under"):
        require_inside_closure_evidence(repo_root() / "modules")
    with pytest.raises(HarnessBlockedError, match="must resolve under"):
        require_inside_closure_evidence(repo_root() / "tests")
    allowed = closure_evidence_root() / "cp08-realprocess-ws" / "probe"
    assert require_inside_closure_evidence(allowed) == allowed.resolve()


def test_acceptance_http_client_timeout_before_headers_reports_method_and_path() -> None:
    import unittest.mock as mock
    import urllib.error

    client = AcceptanceHttpClient("http://127.0.0.1:19999")
    client._token = "test-token"
    timeout_exc = urllib.error.URLError(TimeoutError("timed out"))
    with mock.patch("urllib.request.urlopen", side_effect=timeout_exc):
        with pytest.raises(ScenarioFailure) as exc_info:
            client.request("GET", "/some/path")
    msg = str(exc_info.value)
    assert "GET" in msg
    assert "/some/path" in msg
    assert "vor Response-Headern" in msg
    assert "password" not in msg.lower()
    assert "Authorization" not in msg
    assert "Bearer" not in msg


def test_acceptance_http_client_timeout_phase_label_before_headers_via_urlerror() -> None:
    import unittest.mock as mock
    import urllib.error

    client = AcceptanceHttpClient("http://127.0.0.1:19999")
    client._token = "test-token"
    # OSError wrapping with "timed out" in message is the other common shape
    inner = OSError("timed out")
    timeout_exc = urllib.error.URLError(inner)
    with mock.patch("urllib.request.urlopen", side_effect=timeout_exc):
        with pytest.raises(ScenarioFailure, match="vor Response-Headern"):
            client.request("POST", "/action", body={"x": 1})


def test_acceptance_http_client_timeout_direct_raises_before_headers() -> None:
    import unittest.mock as mock

    client = AcceptanceHttpClient("http://127.0.0.1:19999")
    client._token = "test-token"
    with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        with pytest.raises(ScenarioFailure, match="vor Response-Headern"):
            client.request("GET", "/check")


def test_acceptance_http_client_no_retry_on_timeout() -> None:
    import unittest.mock as mock
    import urllib.error

    client = AcceptanceHttpClient("http://127.0.0.1:19999")
    client._token = "tok"
    call_count = 0
    timeout_exc = urllib.error.URLError(TimeoutError("timed out"))

    def once_then_nothing(req, timeout=None):
        nonlocal call_count
        call_count += 1
        raise timeout_exc

    with mock.patch("urllib.request.urlopen", side_effect=once_then_nothing):
        with pytest.raises(ScenarioFailure):
            client.request("GET", "/once")
    assert call_count == 1, f"expected exactly 1 request, got {call_count}"


def test_acceptance_http_client_timeout_during_body_read_reports_method_path_and_no_secrets() -> None:
    import unittest.mock as mock

    class _FakeResponse:
        """Fake HTTP response whose read() raises TimeoutError."""

        status = 200
        headers: dict[str, str] = {}

        def read(self) -> bytes:
            raise TimeoutError("socket timed out during body read")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    call_count = 0

    def fake_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        return _FakeResponse()

    client = AcceptanceHttpClient("http://127.0.0.1:19999")
    client._token = "secret-bearer-token"
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(ScenarioFailure) as exc_info:
            client.request("POST", "/documents/versions/DOC-1/1/comments", body={"password": "request-body-secret"})

    msg = str(exc_info.value)
    assert "POST" in msg
    assert "/documents/versions/DOC-1/1/comments" in msg
    assert "beim Lesen des Response-Bodys" in msg
    # no tokens, auth headers, or request body values in the message
    assert "secret-bearer-token" not in msg
    assert "Authorization" not in msg
    assert "Bearer" not in msg
    assert "request-body-secret" not in msg
    assert "password" not in msg.lower()
    # exactly one request, no retry
    assert call_count == 1, f"expected exactly 1 urlopen call, got {call_count}"


def test_full_gate_test_does_not_use_tmp_path_parameter() -> None:
    import inspect

    from tests.acceptance.test_j04_m0_realprocess import test_j04_m0_full_realprocess_acceptance

    parameters = inspect.signature(test_j04_m0_full_realprocess_acceptance).parameters
    assert "tmp_path" not in parameters
    source = inspect.getsource(test_j04_m0_full_realprocess_acceptance)
    assert "allocate_realprocess_workspace" in source
    body = source.split('"""', 2)[-1]
    assert "tmp_path" not in body
