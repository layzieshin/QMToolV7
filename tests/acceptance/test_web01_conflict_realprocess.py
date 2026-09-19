"""WEB01-H Slot-2 live conflict proof (production ServiceHost + Chromium)."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from src.backend import bootstrap as backend_bootstrap
from src.backend import service_host as service_host_mod
from tests.acceptance.web01_realprocess_harness import (
    BOOTSTRAP_PASSWORD,
    LOGIN_PASSWORD,
    Web01HarnessBlockedError,
    Web01RealProcessHarness,
    allocate_web01_workspace,
    redact_log_text,
)
from tests.postgres_destructive_guard import RESET_OPT_IN_VALUE, TEST_RESET_ENV
from tests.postgres_live_support import LivePostgresEnv, cleanup_live_environment

pytestmark = pytest.mark.postgres

REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_BACKEND = "tests.backend.web00_browser_smoke_backend"


def _resolve_node_executable() -> Path:
    raw = os.environ.get("QMTOOL_WEB01_NODE_EXE", "").strip()
    if raw:
        candidate = Path(raw)
        if candidate.is_file():
            return candidate
    discovered = shutil.which("node")
    if discovered:
        return Path(discovered)
    pytest.fail("QMTOOL_WEB01_NODE_EXE or node on PATH is required for WEB01 conflict live test")


def test_web01_conflict_live_browser_proof(
    monkeypatch: pytest.MonkeyPatch,
    live_postgres_env: LivePostgresEnv,
) -> None:
    if os.environ.get(TEST_RESET_ENV) != RESET_OPT_IN_VALUE:
        pytest.fail(
            "WEB01 conflict live test requires scripts/run_postgres_live_tests.py "
            "Slot-2 preflight and child-only RESET injection"
        )
    assert FORBIDDEN_BACKEND not in sys.modules
    assert service_host_mod.build_backend_container is backend_bootstrap.build_backend_container

    dist_dir = REPO_ROOT / "webclient" / "dist"
    if not (dist_dir / "index.html").is_file():
        pytest.fail("webclient/dist is missing; npm run build must precede the WEB01-H live gate")

    workspace = allocate_web01_workspace()
    extra_secrets = (
        BOOTSTRAP_PASSWORD,
        LOGIN_PASSWORD,
        live_postgres_env.runtime_password,
        live_postgres_env.migrator_password,
        live_postgres_env.runtime_dsn,
        live_postgres_env.migrator_dsn,
        live_postgres_env.admin_dsn,
    )
    node_exe = _resolve_node_executable()
    document_id = "DOC-WEB01-H-409"

    harness = Web01RealProcessHarness(workspace=workspace, extra_secrets=extra_secrets)
    try:
        harness.provision_postgres(live_postgres_env)
        harness.start_backend(live_env=live_postgres_env, dist_dir=dist_dir)
        fixture = harness.create_planned_document(document_id)
        harness.run_playwright_conflict_spec(fixture=fixture, node_exe=node_exe)

        harness.wait_for_detail_ready()
        harness.bump_document_etag_via_assign_roles(fixture)
        harness.write_stale_mutation_complete()
        harness.wait_playwright()

        json_report = workspace / "browser-smoke-playwright.json"
        if not json_report.is_file():
            alt = workspace / "test-results.json"
            assert alt.is_file(), "Playwright JSON reporter output is missing"
    finally:
        harness.cleanup()
        for name in ("platform.log", "audit.log"):
            source = harness.home / "storage" / "platform" / "logs" / name
            if source.is_file():
                original = source.read_text(encoding="utf-8", errors="replace")
                redacted = redact_log_text(original)
                for secret in extra_secrets:
                    if secret:
                        redacted = redacted.replace(secret, "<redacted>")
                target = workspace / "redacted-host-logs" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(redacted, encoding="utf-8")
        cleanup_live_environment(admin_dsn=live_postgres_env.admin_dsn)

    assert FORBIDDEN_BACKEND not in sys.modules
    diagnosis = workspace / "graceful-stop-diagnosis.json"
    if diagnosis.is_file():
        payload = json.loads(diagnosis.read_text(encoding="utf-8"))
        assert payload.get("fallback_used") is not True
