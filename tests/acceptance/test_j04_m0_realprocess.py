"""J04-M0 full real-process acceptance gate (CP08 only).

This module is intentionally excluded from CP05 runs via the ``j04_final_acceptance``
marker and explicit opt-in environment variable.
"""
from __future__ import annotations

import os

import pytest

from tests.acceptance.j04_m0_acceptance_scenario import (
    StepStatus,
    run_acceptance_scenario,
    scenario_step_catalog,
)
from tests.acceptance.j04_m0_realprocess_harness import (
    HarnessBlockedError,
    J04M0RealProcessHarness,
    allocate_realprocess_workspace,
    require_final_acceptance_opt_in,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.j04_final_acceptance,
]


def _require_opt_in() -> None:
    try:
        require_final_acceptance_opt_in()
    except HarnessBlockedError as exc:
        pytest.skip(str(exc))


def test_j04_m0_full_realprocess_acceptance() -> None:
    """Single planned full acceptance run through signed APPROVED and restart.

    Workspace is allocated under ``build/j04-m0-closure/`` (never a pytest session temp dir).
    Word COM conversion is not a catalog step.
    """
    _require_opt_in()
    if os.environ.get("QMTOOL_PG_TEST_ADMIN_DSN", "").strip() == "":
        pytest.skip("QMTOOL_PG_TEST_ADMIN_DSN is required for the full acceptance run")

    workspace = allocate_realprocess_workspace()
    with J04M0RealProcessHarness(workspace=workspace) as harness:
        results = run_acceptance_scenario(harness)

    failures = [result for result in results if result.status == StepStatus.FAIL]
    assert failures == [], [f"{item.name}: {item.detail}" for item in failures]
    names = [result.name for result in results]
    assert names == list(scenario_step_catalog())
    assert all(result.status == StepStatus.PASS for result in results)
    assert "word_com_live_boundary" not in names
    assert "comments_lifecycle_change_requests" not in names
    assert "document_release_flow" not in names
