"""Unit tests for the Slot-2 PostgreSQL live-test runner (no live cluster)."""
from __future__ import annotations

import os
from pathlib import Path

from tests.postgres_destructive_guard import (
    EXPECTED_CLUSTER_MARKER,
    RESET_OPT_IN_VALUE,
    ApprovedDestructiveTarget,
    DestructivePostgresGuardError,
)


def test_runner_injects_reset_only_in_child_env(monkeypatch, tmp_path: Path) -> None:
    from scripts import run_postgres_live_tests as runner

    monkeypatch.delenv("QMTOOL_PG_TEST_RESET", raising=False)
    monkeypatch.setattr(runner, "_ENV_PATH", tmp_path / "missing.env")
    monkeypatch.setattr(
        runner,
        "preflight_isolated_postgres_target",
        lambda: ApprovedDestructiveTarget(
            database="qmtool_j04_destructive_test",
            major_version=18,
            cluster_marker=EXPECTED_CLUSTER_MARKER,
            host="127.0.0.1",
            port="5432",
        ),
    )
    captured: dict[str, str] = {}

    def fake_run(command, cwd=None, env=None, check=False):  # noqa: ANN001
        captured.update(env or {})
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "_cleanup_restore_databases", lambda: None)
    code = runner.main(["tests/modules/usermanagement/test_postgres_schema_live.py"])
    assert code == 0
    assert captured.get("QMTOOL_PG_TEST_RESET") == RESET_OPT_IN_VALUE
    assert os.environ.get("QMTOOL_PG_TEST_RESET") in (None, "")


def test_runner_preflight_failure_does_not_set_reset(monkeypatch, tmp_path: Path) -> None:
    from scripts import run_postgres_live_tests as runner

    monkeypatch.delenv("QMTOOL_PG_TEST_RESET", raising=False)
    monkeypatch.setattr(runner, "_ENV_PATH", tmp_path / "missing.env")

    def fail_preflight():
        raise DestructivePostgresGuardError("QMTOOL_PG_TEST_ADMIN_DSN is required")

    monkeypatch.setattr(runner, "preflight_isolated_postgres_target", fail_preflight)
    called = {"run": False}

    def fake_run(*args, **kwargs):  # noqa: ANN001
        called["run"] = True
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    code = runner.main([])
    assert code == 2
    assert called["run"] is False
    assert os.environ.get("QMTOOL_PG_TEST_RESET") in (None, "")
