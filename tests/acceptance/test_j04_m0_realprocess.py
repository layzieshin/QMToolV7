"""J04-M0 full real-process acceptance gate (CP08 only).

This module is intentionally excluded from CP05 runs via the ``j04_final_acceptance``
marker and explicit opt-in environment variable.
"""
from __future__ import annotations

import os

import pytest

from tests.acceptance.j04_m0_realprocess_harness import (
    FINAL_ACCEPTANCE_ENV,
    FINAL_ACCEPTANCE_OPT_IN,
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

    Implemented for CP08; must not execute during CP05 harness bring-up.
    """
    _require_opt_in()
    if os.environ.get("QMTOOL_PG_TEST_ADMIN_DSN", "").strip() == "":
        pytest.skip("QMTOOL_PG_TEST_ADMIN_DSN is required for the full acceptance run")

    workspace = tmp_path / "j04-final-acceptance"
    with J04M0RealProcessHarness(workspace=workspace) as harness:
        harness.start_backend(
            extra_env={
                "QMTOOL_LICENSE_MODE": "dev",
                "QMTOOL_PG_TEST_RESET": os.environ.get("QMTOOL_PG_TEST_RESET", ""),
                "QMTOOL_PG_TEST_EXPECTED_DATABASE": os.environ.get(
                    "QMTOOL_PG_TEST_EXPECTED_DATABASE",
                    "qmtool_j04_destructive_test",
                ),
            }
        )
        harness.wait_for_health()
        pytest.skip("full acceptance scenario orchestration is completed in CP08")
