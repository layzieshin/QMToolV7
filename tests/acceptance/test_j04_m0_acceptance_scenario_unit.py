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
    BOOTSTRAP_ADMIN_PASSWORD_AFTER_CHANGE,
    EDITOR_USERNAME,
    QMB_PASSWORD,
    QMB_USERNAME,
    REVIEWER_USERNAME,
    ScenarioContext,
    ScenarioFailure,
    StepStatus,
    WORD_COM_LIVE_ENV,
    WORD_COM_LIVE_OPT_IN,
    capture_authenticated_user_id,
    complete_bootstrap_admin_session,
    build_backend_extra_env,
    evaluate_etag_race_payloads,
    post_acceptance_document_create,
    require_version_success,
    require_editor_read_receipt,
    run_acceptance_scenario,
    scenario_step_catalog,
    word_com_boundary_reason,
    workflow_role_assignment,
    _step_document_baseline_flow,
    _step_etag_concurrency_race,
    _step_seed_directory_users,
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


def test_scenario_step_catalog_matches_cp08_contract() -> None:
    catalog = scenario_step_catalog()
    assert catalog[0] == "preconditions"
    assert "etag_concurrency_race" in catalog
    assert "word_com_live_boundary" in catalog[-1:]
    assert len(catalog) == 17


def test_word_com_boundary_defaults_to_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(WORD_COM_LIVE_ENV, raising=False)
    reason = word_com_boundary_reason()
    assert WORD_COM_LIVE_OPT_IN in reason
    assert "interactive Windows session" in reason


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


def test_document_baseline_and_race_use_seeded_qmb_not_bootstrap_admin() -> None:
    import inspect

    from tests.acceptance.j04_m0_acceptance_scenario import (
        _step_document_baseline_flow,
        _step_comments_lifecycle_change_requests,
        _step_word_com_live_boundary,
    )

    baseline = inspect.getsource(_step_document_baseline_flow)
    comments = inspect.getsource(_step_comments_lifecycle_change_requests)
    word = inspect.getsource(_step_word_com_live_boundary)
    assert 'tokens["qmb"]' in baseline
    assert 'tokens["admin"]' not in baseline
    assert 'tokens["qmb"]' in comments
    assert 'tokens["admin"]' not in comments
    assert 'tokens["qmb"]' in word
    assert 'tokens["admin"]' not in word


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


def test_training_read_receipt_matches_user_id_not_username() -> None:
    require_editor_read_receipt({"user_id": EDITOR_USER_ID}, _ROLE_USER_IDS)
    with pytest.raises(ScenarioFailure, match="training read receipt missing editor actor"):
        require_editor_read_receipt({"user_id": EDITOR_USERNAME}, _ROLE_USER_IDS)


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


def test_full_gate_test_does_not_use_tmp_path_parameter() -> None:
    import inspect

    from tests.acceptance.test_j04_m0_realprocess import test_j04_m0_full_realprocess_acceptance

    parameters = inspect.signature(test_j04_m0_full_realprocess_acceptance).parameters
    assert "tmp_path" not in parameters
    source = inspect.getsource(test_j04_m0_full_realprocess_acceptance)
    assert "allocate_realprocess_workspace" in source
    body = source.split('"""', 2)[-1]
    assert "tmp_path" not in body
