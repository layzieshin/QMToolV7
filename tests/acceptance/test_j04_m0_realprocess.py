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
)
from tests.acceptance.j04_m0_realprocess_harness import (
    HarnessBlockedError,
    J04M0RealProcessHarness,
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


def test_j04_m0_full_realprocess_acceptance(tmp_path) -> None:  # noqa: ANN001
    """Single planned full acceptance run (health, sessions, ETag, artifacts, restart, Word COM).

    Implemented in CP08-R2; executes only with explicit opt-in and isolated PG preconditions.
    """
    _require_opt_in()
    if os.environ.get("QMTOOL_PG_TEST_ADMIN_DSN", "").strip() == "":
        pytest.skip("QMTOOL_PG_TEST_ADMIN_DSN is required for the full acceptance run")

    workspace = tmp_path / "j04-final-acceptance"
    with J04M0RealProcessHarness(workspace=workspace) as harness:
        results = run_acceptance_scenario(harness)

    failures = [result for result in results if result.status == StepStatus.FAIL]
    assert failures == [], [f"{item.name}: {item.detail}" for item in failures]

    word_step = next(result for result in results if result.name == "word_com_live_boundary")
    if os.environ.get("QMTOOL_J04_WORD_COM_LIVE", "").strip() != "I_UNDERSTAND_THIS_IS_A_REAL_WORD_COM_RUN":
        assert word_step.status == StepStatus.SKIP
