"""WEB01-K1 Slot-2 live product slice (PIS-WEB01 + visual evidence)."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

from src.backend import bootstrap as backend_bootstrap
from src.backend import service_host as service_host_mod
from tests.acceptance.web01_realprocess_harness import (
    BOOTSTRAP_PASSWORD,
    CONFLICT_DOCUMENT_ID,
    DETAIL_READY_FILENAME,
    FIXTURE_WEB01_APPROVER_PASS,
    FIXTURE_WEB01_EDITOR_PASS,
    FIXTURE_WEB01_REVIEWER_PASS,
    HANDSHAKE_CONFLICT_STALE,
    HANDSHAKE_MAINTENANCE,
    HANDSHAKE_MAINTENANCE_EXIT,
    HANDSHAKE_PIS_ROLES,
    HANDSHAKE_RESTART,
    LOGIN_PASSWORD,
    MAINTENANCE_EXIT_REQUEST_FILENAME,
    MAINTENANCE_REQUEST_FILENAME,
    PIS_DOCUMENT_READY_FILENAME,
    FINAL_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
    RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
    RESTART_REQUEST_FILENAME,
    Web01HarnessBlockedError,
    Web01HandshakeTracker,
    Web01RealProcessHarness,
    actor_user_id,
    allocate_k1_visual_dir,
    allocate_k1_workspace,
    bearer_token,
    copy_playwright_json_report,
    redact_log_text,
    verify_visual_screenshots,
)
from tests.postgres_destructive_guard import RESET_OPT_IN_VALUE, TEST_RESET_ENV, preflight_isolated_postgres_target
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
    pytest.fail("QMTOOL_WEB01_NODE_EXE or node on PATH is required for WEB01-K1 live test")


def test_web01_product_slice_pis_and_visual_evidence(
    monkeypatch: pytest.MonkeyPatch,
    live_postgres_env: LivePostgresEnv,
) -> None:
    if os.environ.get(TEST_RESET_ENV) != RESET_OPT_IN_VALUE:
        pytest.fail(
            "WEB01-K1 live test requires scripts/run_postgres_live_tests.py "
            "Slot-2 preflight and child-only RESET injection"
        )
    preflight = preflight_isolated_postgres_target()
    assert preflight.database == "qmtool_j04_destructive_test"
    assert FORBIDDEN_BACKEND not in sys.modules
    assert service_host_mod.build_backend_container is backend_bootstrap.build_backend_container

    dist_dir = REPO_ROOT / "webclient" / "dist"
    if not (dist_dir / "index.html").is_file():
        pytest.fail("webclient/dist is missing; npm run build must precede the WEB01-K1 live gate")

    workspace = allocate_k1_workspace()
    visual_dir = allocate_k1_visual_dir()
    extra_secrets = (
        BOOTSTRAP_PASSWORD,
        LOGIN_PASSWORD,
        FIXTURE_WEB01_EDITOR_PASS,
        FIXTURE_WEB01_REVIEWER_PASS,
        FIXTURE_WEB01_APPROVER_PASS,
        live_postgres_env.runtime_password,
        live_postgres_env.migrator_password,
        live_postgres_env.runtime_dsn,
        live_postgres_env.migrator_dsn,
        live_postgres_env.admin_dsn,
    )
    node_exe = _resolve_node_executable()

    harness = Web01RealProcessHarness(workspace=workspace, extra_secrets=extra_secrets)
    handshake_tracker = Web01HandshakeTracker()
    try:
        harness.provision_postgres(live_postgres_env)
        harness.start_backend(
            live_env=live_postgres_env,
            dist_dir=dist_dir,
            run_fixture_initialization=True,
        )
        harness.seed_synthetic_users()
        harness.activate_role_signature_assets()

        editor_id = actor_user_id(
            harness.base_url,
            bearer_token(harness.base_url, "web01_editor", FIXTURE_WEB01_EDITOR_PASS),
        )
        reviewer_id = actor_user_id(
            harness.base_url,
            bearer_token(harness.base_url, "web01_reviewer", FIXTURE_WEB01_REVIEWER_PASS),
        )
        approver_id = actor_user_id(
            harness.base_url,
            bearer_token(harness.base_url, "web01_approver", FIXTURE_WEB01_APPROVER_PASS),
        )
        conflict_fixture = harness.create_planned_document(CONFLICT_DOCUMENT_ID)
        harness.assign_document_roles(
            conflict_fixture,
            editor_id=editor_id,
            reviewer_id=reviewer_id,
            approver_id=approver_id,
        )

        harness.run_playwright_product_slice_spec(
            fixture=conflict_fixture,
            visual_dir=visual_dir,
            node_exe=node_exe,
        )

        deadline = time.monotonic() + 900.0
        while harness.playwright is not None and harness.playwright.poll() is None:
            if time.monotonic() > deadline:
                pytest.fail("timeout waiting for WEB01-K1 Playwright product slice")
            handshake_tracker.try_process(
                HANDSHAKE_PIS_ROLES,
                marker_path=workspace / PIS_DOCUMENT_READY_FILENAME,
                handler=lambda: harness.assign_pis_roles_from_handshake(
                    editor_id=editor_id,
                    reviewer_id=reviewer_id,
                    approver_id=approver_id,
                ),
            )
            handshake_tracker.try_process(
                HANDSHAKE_CONFLICT_STALE,
                marker_path=workspace / DETAIL_READY_FILENAME,
                handler=lambda: (
                    harness.bump_document_etag_via_assign_roles(conflict_fixture),
                    harness.write_stale_mutation_complete(),
                ),
            )
            handshake_tracker.try_process(
                HANDSHAKE_MAINTENANCE,
                marker_path=workspace / MAINTENANCE_REQUEST_FILENAME,
                handler=harness.enter_degraded_maintenance,
            )
            handshake_tracker.try_process(
                HANDSHAKE_MAINTENANCE_EXIT,
                marker_path=workspace / MAINTENANCE_EXIT_REQUEST_FILENAME,
                handler=harness.complete_maintenance_exit_handshake,
            )
            handshake_tracker.try_process(
                HANDSHAKE_RESTART,
                marker_path=workspace / RESTART_REQUEST_FILENAME,
                handler=lambda: (
                    harness.restart_backend_process(live_env=live_postgres_env, dist_dir=dist_dir),
                    harness.write_restart_complete(),
                ),
            )
            time.sleep(0.25)

        harness.wait_playwright(timeout=720.0)
        copy_playwright_json_report(workspace, visual_dir)
        screenshots = verify_visual_screenshots(visual_dir)
        assert len(screenshots) == 16
        assert handshake_tracker.is_complete(HANDSHAKE_PIS_ROLES)
        assert handshake_tracker.is_complete(HANDSHAKE_CONFLICT_STALE)
        assert handshake_tracker.is_complete(HANDSHAKE_MAINTENANCE)
        assert handshake_tracker.is_complete(HANDSHAKE_MAINTENANCE_EXIT)
        assert handshake_tracker.is_complete(HANDSHAKE_RESTART)
    finally:
        harness.cleanup(diagnosis_filename=FINAL_GRACEFUL_STOP_DIAGNOSIS_FILENAME)
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
    for diagnosis_name in (
        RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
        FINAL_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
    ):
        diagnosis = workspace / diagnosis_name
        assert diagnosis.is_file(), f"missing graceful-stop diagnosis evidence: {diagnosis_name}"
        payload = json.loads(diagnosis.read_text(encoding="utf-8"))
        assert payload.get("fallback_used") is not True
        assert payload.get("marker_present_after_exit") is not True
        assert payload.get("child_returncode") == 0
