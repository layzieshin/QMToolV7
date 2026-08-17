"""Unit tests for the J04-M0 acceptance scenario (no live PG / no full CP08 run)."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from tests.acceptance.j04_m0_acceptance_scenario import (
    ACCEPTANCE_DOC_ID,
    AcceptanceHttpClient,
    ScenarioContext,
    StepStatus,
    WORD_COM_LIVE_ENV,
    WORD_COM_LIVE_OPT_IN,
    build_backend_extra_env,
    run_acceptance_scenario,
    scenario_step_catalog,
    word_com_boundary_reason,
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
