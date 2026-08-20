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
    captured: dict[str, object] = {}

    def fake_run(command, cwd=None, env=None, check=False):  # noqa: ANN001
        captured["env"] = dict(env or {})
        captured["command"] = list(command)
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "_cleanup_restore_databases", lambda: None)
    code = runner.main(["tests/modules/usermanagement/test_postgres_schema_live.py"])
    assert code == 0
    env = captured["env"]
    assert isinstance(env, dict)
    assert env.get("QMTOOL_PG_TEST_RESET") == RESET_OPT_IN_VALUE
    assert os.environ.get("QMTOOL_PG_TEST_RESET") in (None, "")
    command = captured["command"]
    assert isinstance(command, list)
    assert "tests/acceptance/test_j04_m0_realprocess.py" not in command
    pytest_at = command.index("pytest")
    assert command[command.index("-m", pytest_at) + 1] == "postgres"
    assert "-q" in command


def _install_ok_preflight(monkeypatch, runner, tmp_path: Path) -> None:
    monkeypatch.delenv("QMTOOL_PG_TEST_RESET", raising=False)
    monkeypatch.delenv("QMTOOL_J04_FINAL_ACCEPTANCE", raising=False)
    monkeypatch.delenv("QMTOOL_J04_WORD_COM_LIVE", raising=False)
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
    monkeypatch.setattr(runner, "_cleanup_restore_databases", lambda: None)


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


def test_runner_acceptance_injects_reset_only_in_child(monkeypatch, tmp_path: Path) -> None:
    from scripts import run_postgres_live_tests as runner
    from tests.acceptance.j04_m0_realprocess_harness import (
        FINAL_ACCEPTANCE_ENV,
        FINAL_ACCEPTANCE_OPT_IN,
    )

    _install_ok_preflight(monkeypatch, runner, tmp_path)
    monkeypatch.setenv(FINAL_ACCEPTANCE_ENV, FINAL_ACCEPTANCE_OPT_IN)
    basetemp = tmp_path / "fresh-acceptance-basetemp"
    captured: dict[str, object] = {}

    def fake_run(command, cwd=None, env=None, check=False):  # noqa: ANN001
        captured["env"] = dict(env or {})
        captured["command"] = list(command)
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    code = runner.main(
        [
            "--j04-final-acceptance",
            "--basetemp",
            str(basetemp),
        ]
    )
    assert code == 0
    env = captured["env"]
    command = captured["command"]
    assert isinstance(env, dict)
    assert isinstance(command, list)
    assert env.get("QMTOOL_PG_TEST_RESET") == RESET_OPT_IN_VALUE
    assert "QMTOOL_J04_WORD_COM_LIVE" not in env
    assert os.environ.get("QMTOOL_PG_TEST_RESET") in (None, "")
    assert runner.J04_FINAL_ACCEPTANCE_TARGET in command
    pytest_at = command.index("pytest")
    assert command[command.index("-m", pytest_at) + 1] == runner.J04_FINAL_ACCEPTANCE_MARKER
    assert "--basetemp" in command
    assert str(basetemp) in command
    assert "tests/modules/usermanagement/test_postgres_schema_live.py" not in command


def test_runner_acceptance_requires_opt_in_before_pytest(monkeypatch, tmp_path: Path) -> None:
    from scripts import run_postgres_live_tests as runner

    _install_ok_preflight(monkeypatch, runner, tmp_path)
    called = {"run": False}

    def fake_run(*args, **kwargs):  # noqa: ANN001
        called["run"] = True
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    code = runner.main(
        ["--j04-final-acceptance", "--basetemp", str(tmp_path / "fresh")]
    )
    assert code == 4
    assert called["run"] is False
    assert os.environ.get("QMTOOL_PG_TEST_RESET") in (None, "")


def test_runner_acceptance_rejects_existing_basetemp(monkeypatch, tmp_path: Path) -> None:
    from scripts import run_postgres_live_tests as runner
    from tests.acceptance.j04_m0_realprocess_harness import (
        FINAL_ACCEPTANCE_ENV,
        FINAL_ACCEPTANCE_OPT_IN,
    )

    _install_ok_preflight(monkeypatch, runner, tmp_path)
    monkeypatch.setenv(FINAL_ACCEPTANCE_ENV, FINAL_ACCEPTANCE_OPT_IN)
    existing = tmp_path / "already"
    existing.mkdir()
    called = {"run": False}

    def fake_run(*args, **kwargs):  # noqa: ANN001
        called["run"] = True
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    code = runner.main(["--j04-final-acceptance", "--basetemp", str(existing)])
    assert code == 4
    assert called["run"] is False


def test_runner_rejects_loose_acceptance_target(monkeypatch, tmp_path: Path) -> None:
    from scripts import run_postgres_live_tests as runner

    _install_ok_preflight(monkeypatch, runner, tmp_path)
    called = {"run": False}

    def fake_run(*args, **kwargs):  # noqa: ANN001
        called["run"] = True
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    code = runner.main(["tests/acceptance/test_j04_m0_realprocess.py"])
    assert code == 4
    assert called["run"] is False


def test_runner_acceptance_preflight_failure_does_not_start_pytest(
    monkeypatch, tmp_path: Path
) -> None:
    from scripts import run_postgres_live_tests as runner
    from tests.acceptance.j04_m0_realprocess_harness import (
        FINAL_ACCEPTANCE_ENV,
        FINAL_ACCEPTANCE_OPT_IN,
    )

    monkeypatch.delenv("QMTOOL_PG_TEST_RESET", raising=False)
    monkeypatch.setenv(FINAL_ACCEPTANCE_ENV, FINAL_ACCEPTANCE_OPT_IN)
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
    code = runner.main(
        ["--j04-final-acceptance", "--basetemp", str(tmp_path / "fresh")]
    )
    assert code == 2
    assert called["run"] is False
    assert os.environ.get("QMTOOL_PG_TEST_RESET") in (None, "")
