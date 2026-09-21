from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from conftest import _has_explicit_basetemp, _unique_default_basetemp


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".cursor" / "tools"
POWERSHELL = "powershell.exe"


def _run_powershell(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *args,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_default_basetemp_is_short_unique_and_explicit_override_is_preserved() -> None:
    assert not _has_explicit_basetemp(["tests/docs", "-q"])
    assert _has_explicit_basetemp(["--basetemp", "build/custom"])
    assert _has_explicit_basetemp(["--basetemp=build/custom"])

    first = _unique_default_basetemp(ROOT, pid=123, token="aaaaaaaa")
    second = _unique_default_basetemp(ROOT, pid=123, token="bbbbbbbb")
    assert first == ROOT / "build" / "pt" / "123-aaaaaaaa"
    assert second == ROOT / "build" / "pt" / "123-bbbbbbbb"
    assert first != second


def test_direct_pytest_process_uses_unique_repository_local_default(tmp_path: Path) -> None:
    smoke = tmp_path / "test_direct_default.py"
    smoke.write_text(
        "from pathlib import Path\n"
        "def test_default(pytestconfig):\n"
        "    path = Path(str(pytestconfig.option.basetemp))\n"
        "    assert path.parent.name == 'pt'\n"
        "    assert path.parent.parent.name == 'build'\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", str(smoke), "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


@pytest.mark.skipif(os.name != "nt", reason="PowerShell execution-host contract is Windows-only")
def test_execution_host_preflight_accepts_python_temp_roundtrip() -> None:
    completed = _run_powershell(
        TOOLS / "assert-execution-host.ps1",
        "-TargetRoot",
        str(ROOT),
        "-PythonPath",
        sys.executable,
        "-RequirePythonTemp",
        "-Json",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "READY"
    assert payload["checks"]["registered_worktree"] == "PASS"
    assert payload["checks"]["python_temp_roundtrip"] == "PASS"


@pytest.mark.skipif(os.name != "nt", reason="PowerShell execution-host contract is Windows-only")
def test_execution_host_preflight_rejects_disabled_cursor_proxy_without_repairing_it() -> None:
    env = dict(os.environ)
    env["HTTP_PROXY"] = "http://127.0.0.1:9"
    completed = _run_powershell(
        TOOLS / "assert-execution-host.ps1",
        "-TargetRoot",
        str(ROOT),
        "-RequireCursorCli",
        "-Json",
        env=env,
    )
    assert completed.returncode == 3
    payload = json.loads(completed.stdout)
    assert payload["status"] == "EXECUTION_HOST_REQUIRED"
    assert any(item["code"] == "CURSOR_NETWORK_BLOCKED" for item in payload["failures"])
    assert "127.0.0.1:9" not in completed.stdout


@pytest.mark.skipif(os.name != "nt", reason="PowerShell execution-host contract is Windows-only")
def test_execution_host_preflight_rejects_existing_git_index_lock(tmp_path: Path) -> None:
    repo = tmp_path / "locked-repo"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(repo)],
        capture_output=True,
        text=True,
        check=True,
    )
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=QMTool Test",
            "-c",
            "user.email=qmtool@example.invalid",
            "commit",
            "-m",
            "seed",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    (repo / ".git" / "index.lock").write_text("locked\n", encoding="utf-8")

    completed = _run_powershell(
        TOOLS / "assert-execution-host.ps1",
        "-TargetRoot",
        str(repo),
        "-RequireGitWrite",
        "-Json",
    )
    assert completed.returncode == 3
    payload = json.loads(completed.stdout)
    assert any(item["code"] == "GIT_INDEX_LOCKED" for item in payload["failures"])


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_wrapper_uses_unique_owned_paths(tmp_path: Path) -> None:
    smoke = tmp_path / "test_wrapper_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    junit = tmp_path / "wrapper.xml"
    completed = _run_powershell(
        TOOLS / "run-pytest-gate.ps1",
        "-GateId",
        "hygiene",
        "-PythonPath",
        sys.executable,
        "-JUnitPath",
        str(junit),
        str(smoke),
        "-q",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "QMTOOL_PYTEST_BASETEMP=" in completed.stdout
    assert "QMTOOL_PYTEST_PROCESS_TEMP=" in completed.stdout
    assert junit.is_file()


def test_cursor_launcher_is_synchronous_and_does_not_weaken_host_controls() -> None:
    launcher = (TOOLS / "invoke-cursor-agent.ps1").read_text(encoding="utf-8")
    preflight = (TOOLS / "assert-execution-host.ps1").read_text(encoding="utf-8")
    assert "Start-Process" not in launcher
    assert "RequireCursorCli" in launcher
    assert "& $cursor.Source @arguments" in launcher
    assert "SetEnvironmentVariable" not in launcher
    assert "Remove-Item Env:" not in launcher
    assert "SetEnvironmentVariable" not in preflight


def test_autonomous_rules_require_preflight_and_gate_wrapper() -> None:
    workflow = (ROOT / ".cursor" / "rules" / "00-agent-workflow.mdc").read_text(encoding="utf-8")
    skill = (ROOT / ".cursor" / "skills" / "execute-work-package" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for text in (workflow, skill, agents):
        assert "assert-execution-host.ps1" in text
        assert "run-pytest-gate.ps1" in text
    assert "EXECUTION_HOST_REQUIRED" in workflow
    assert "invoke-cursor-agent.ps1" in workflow
    setup = (ROOT / ".cursor" / "setup-worktree-windows.ps1").read_text(encoding="utf-8")
    assert "assert-execution-host.ps1" in setup
    assert setup.count("RequireGitWrite") == 2
    assert "RequirePythonTemp" in setup
    system = (ROOT / "docs" / "CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md").read_text(
        encoding="utf-8"
    )
    assert "## Execution host and temporary paths" in system
    assert "invoke-cursor-agent.ps1" in system
    assert "build/pt/<pid>-<token>" in system
