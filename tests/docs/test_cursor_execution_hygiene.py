from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

import pytest

from conftest import (
    _has_explicit_basetemp,
    _is_tracked_repo_path,
    _unique_default_basetemp,
    _validate_junit_target,
)


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".cursor" / "tools"
POWERSHELL = "powershell.exe"


def _unique_build_junit(name: str) -> Path:
    token = uuid4().hex[:8]
    return ROOT / "build" / "pt" / f"{name}-{token}.xml"


def _seed_git_repo(repo: Path, *tracked_paths: Path) -> None:
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(repo)],
        capture_output=True,
        text=True,
        check=True,
    )
    for tracked_path in tracked_paths:
        tracked_path.parent.mkdir(parents=True, exist_ok=True)
        tracked_path.write_text("<testsuite/>", encoding="utf-8")
        relative = tracked_path.relative_to(repo).as_posix()
        subprocess.run(["git", "add", relative], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=QMTool Test",
            "-c",
            "user.email=qmtool@example.invalid",
            "commit",
            "-m",
            "seed tracked evidence",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


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
    junit = _unique_build_junit("wrapper-smoke")
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


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_wrapper_rejects_junit_path_outside_build(tmp_path: Path) -> None:
    smoke = tmp_path / "test_wrapper_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    junit = ROOT / f"outside-build-{uuid4().hex[:8]}.xml"
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
    assert completed.returncode != 0
    assert "build directory" in (completed.stderr or completed.stdout)
    assert not junit.exists()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_wrapper_rejects_non_xml_and_tracked_junit_targets(tmp_path: Path) -> None:
    smoke = tmp_path / "test_wrapper_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    non_xml = _unique_build_junit("wrapper-nonxml").with_suffix(".txt")

    non_xml_result = _run_powershell(
        TOOLS / "run-pytest-gate.ps1",
        "-GateId",
        "hygiene",
        "-PythonPath",
        sys.executable,
        "-JUnitPath",
        str(non_xml),
        str(smoke),
        "-q",
    )
    assert non_xml_result.returncode != 0
    assert ".xml" in (non_xml_result.stderr or non_xml_result.stdout)
    assert not non_xml.exists()

    tracked_repo = tmp_path / "tracked-xml-repo"
    tracked_repo.mkdir()
    tracked_xml = tracked_repo / "build" / "tracked-evidence.xml"
    _seed_git_repo(tracked_repo, tracked_xml)
    tracked_bytes = tracked_xml.read_bytes()
    tracked_result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(TOOLS / "run-pytest-gate.ps1"),
            "-GateId",
            "hygiene",
            "-PythonPath",
            sys.executable,
            "-JUnitPath",
            str(tracked_xml),
            str(smoke),
            "-q",
        ],
        cwd=tracked_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked_result.returncode != 0
    assert "tracked repository path" in (tracked_result.stderr or tracked_result.stdout)
    assert tracked_xml.read_bytes() == tracked_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
@pytest.mark.parametrize(
    ("extra_arg",),
    [
        ("--junitxml",),
        ("--junitxml=build/pt/forbidden.xml",),
        ("--junit-xml",),
        ("--junit-xml=build/pt/forbidden.xml",),
    ],
)
def test_pytest_gate_wrapper_rejects_junit_aliases_in_pytest_args(
    tmp_path: Path, extra_arg: str
) -> None:
    smoke = tmp_path / "test_wrapper_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    completed = _run_powershell(
        TOOLS / "run-pytest-gate.ps1",
        "-GateId",
        "hygiene",
        "-PythonPath",
        sys.executable,
        str(smoke),
        extra_arg,
        "-q",
    )
    assert completed.returncode != 0
    assert "JUnitPath" in (completed.stderr or completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_wrapper_parameters_are_named_only(tmp_path: Path) -> None:
    smoke = tmp_path / "test_wrapper_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    junit = _unique_build_junit("wrapper-named-only")

    missing_gate_id = _run_powershell(
        TOOLS / "run-pytest-gate.ps1",
        "hygiene",
        "-PythonPath",
        sys.executable,
        "-JUnitPath",
        str(junit),
        str(smoke),
        "-q",
    )
    assert missing_gate_id.returncode != 0

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
    assert junit.is_file()


def test_direct_pytest_rejects_junitxml_on_tracked_xml_file(tmp_path: Path) -> None:
    repo = tmp_path / "tracked-xml-guard"
    repo.mkdir()
    tracked_xml = repo / "build" / "tracked-evidence.xml"
    _seed_git_repo(repo, tracked_xml)
    conftest_source = ROOT / "conftest.py"
    (repo / "conftest.py").write_text(conftest_source.read_text(encoding="utf-8"), encoding="utf-8")
    smoke = repo / "test_direct_tracked_guard.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    original = tracked_xml.read_bytes()
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(smoke),
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(repo),
            "--confcutdir",
            str(repo),
            "--junitxml",
            str(tracked_xml),
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "tracked repository path" in (completed.stderr or completed.stdout)
    assert tracked_xml.read_bytes() == original


def test_python_junit_guard_rejects_tracked_xml_via_helper(tmp_path: Path) -> None:
    repo = tmp_path / "tracked-xml-helper"
    repo.mkdir()
    tracked_xml = repo / "build" / "tracked-evidence.xml"
    _seed_git_repo(repo, tracked_xml)
    assert _is_tracked_repo_path(repo, tracked_xml.resolve())
    with pytest.raises(pytest.UsageError, match="tracked repository path"):
        _validate_junit_target(repo, tracked_xml.resolve())


def test_direct_pytest_from_subdirectory_rejects_tests_local_build_junit(tmp_path: Path) -> None:
    smoke = tmp_path / "test_direct_subdir_guard.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    rogue_name = f"rogue-{uuid4().hex[:8]}.xml"
    tests_build_dir = ROOT / "tests" / "build"
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(smoke),
            "-q",
            "-p",
            "no:cacheprovider",
            "--junitxml",
            f"build/{rogue_name}",
        ],
        cwd=ROOT / "tests",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "build" in (completed.stderr or completed.stdout)
    assert not (tests_build_dir / rogue_name).exists()
    assert not (ROOT / "build" / "pt" / rogue_name).exists()


def test_direct_pytest_from_subdirectory_writes_repo_build_junit(tmp_path: Path) -> None:
    smoke = tmp_path / "test_direct_subdir_ok.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    junit_name = f"direct-subdir-{uuid4().hex[:8]}.xml"
    junit = ROOT / "build" / "pt" / junit_name
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(smoke),
            "-q",
            "-p",
            "no:cacheprovider",
            "--junit-xml",
            f"../build/pt/{junit_name}",
        ],
        cwd=ROOT / "tests",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert junit.is_file()
    assert not (ROOT / "tests" / "build").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction escape guard is Windows-only")
def test_pytest_gate_wrapper_rejects_existing_direct_reparse_target_under_build(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside-direct"
    outside.mkdir()
    token = uuid4().hex[:8]
    direct_junit = ROOT / "build" / f"direct-reparse-{token}.xml"
    mklink = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(direct_junit), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    if mklink.returncode != 0:
        combined = mklink.stderr or mklink.stdout
        pytest.skip(f"cannot create junction in this environment: {combined}")

    smoke = tmp_path / "test_wrapper_direct_reparse_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    try:
        completed = _run_powershell(
            TOOLS / "run-pytest-gate.ps1",
            "-GateId",
            "hygiene",
            "-PythonPath",
            sys.executable,
            "-JUnitPath",
            str(direct_junit.relative_to(ROOT)),
            str(smoke),
            "-q",
        )
        assert completed.returncode != 0
        combined = (completed.stderr or completed.stdout).lower()
        assert "reparse point" in combined or "junction" in combined
        assert not (outside / "sub").exists()
    finally:
        if direct_junit.exists():
            direct_junit.rmdir()


def _snapshot_build_temp_children(directory: Path) -> set[str]:
    if not directory.exists():
        return set()
    return {child.name for child in directory.iterdir()}


def _wrapper_owned_pt_entries(names: set[str]) -> set[str]:
    return {name for name in names if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}-\d{8}T\d+Z-[0-9a-f]{8}", name)}


def _wrapper_owned_ptmp_entries(names: set[str]) -> set[str]:
    return {name for name in names if re.fullmatch(r"\d+-[0-9a-f]{8}", name)}


@pytest.mark.skipif(os.name != "nt", reason="Windows junction escape guard is Windows-only")
def test_pytest_gate_wrapper_rejects_nested_junction_before_creating_artifacts(
    tmp_path: Path,
) -> None:
    pt_dir = ROOT / "build" / "pt"
    ptmp_dir = ROOT / "build" / "ptmp"
    pt_dir.mkdir(parents=True, exist_ok=True)
    ptmp_dir.mkdir(parents=True, exist_ok=True)
    before_pt = _snapshot_build_temp_children(pt_dir)
    before_ptmp = _snapshot_build_temp_children(ptmp_dir)

    outside = tmp_path / "outside"
    outside.mkdir()
    token = uuid4().hex[:8]
    trap_root = ROOT / "build" / "pt" / f"junction-trap-{token}"
    trap_root.mkdir(parents=True, exist_ok=True)
    junction = trap_root / "trap"
    mklink = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    if mklink.returncode != 0:
        combined = mklink.stderr or mklink.stdout
        pytest.skip(f"cannot create junction in this environment: {combined}")

    smoke = tmp_path / "test_wrapper_junction_artifact_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    junit = trap_root / "trap" / "sub" / f"escape-{token}.xml"
    try:
        completed = _run_powershell(
            TOOLS / "run-pytest-gate.ps1",
            "-GateId",
            "hygiene",
            "-PythonPath",
            sys.executable,
            "-JUnitPath",
            str(junit.relative_to(ROOT)),
            str(smoke),
            "-q",
        )
        assert completed.returncode != 0
        combined = (completed.stderr or completed.stdout).lower()
        assert "reparse point" in combined or "junction" in combined
        assert not (outside / "sub").exists()
        assert not (outside / f"escape-{token}.xml").exists()

        after_pt = _snapshot_build_temp_children(pt_dir)
        after_ptmp = _snapshot_build_temp_children(ptmp_dir)
        new_wrapper_pt = _wrapper_owned_pt_entries(after_pt - before_pt)
        new_wrapper_ptmp = _wrapper_owned_ptmp_entries(after_ptmp - before_ptmp)
        assert not new_wrapper_pt
        assert not new_wrapper_ptmp
        assert not (outside / "sub").exists()
        assert not (outside / f"escape-{token}.xml").exists()
    finally:
        if junction.exists():
            junction.rmdir()
        for child in trap_root.iterdir():
            if child.is_dir():
                child.rmdir()
        trap_root.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction escape guard is Windows-only")
def test_pytest_gate_wrapper_rejects_junction_escape_in_build_path(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    token = uuid4().hex[:8]
    trap_root = ROOT / "build" / "pt" / f"junction-trap-{token}"
    trap_root.mkdir(parents=True, exist_ok=True)
    junction = trap_root / "trap"
    mklink = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    if mklink.returncode != 0:
        combined = mklink.stderr or mklink.stdout
        pytest.skip(f"cannot create junction in this environment: {combined}")

    smoke = tmp_path / "test_wrapper_junction_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    junit = trap_root / "trap" / "sub" / f"escape-{token}.xml"
    try:
        completed = _run_powershell(
            TOOLS / "run-pytest-gate.ps1",
            "-GateId",
            "hygiene",
            "-PythonPath",
            sys.executable,
            "-JUnitPath",
            str(junit.relative_to(ROOT)),
            str(smoke),
            "-q",
        )
        assert completed.returncode != 0
        combined = (completed.stderr or completed.stdout).lower()
        assert "reparse point" in combined or "junction" in combined
        assert not (outside / "sub").exists()
        assert not (outside / f"escape-{token}.xml").exists()
    finally:
        if junction.exists():
            junction.rmdir()
        for child in trap_root.iterdir():
            if child.is_dir():
                child.rmdir()
        trap_root.rmdir()


def test_direct_pytest_accepts_build_junit_target(tmp_path: Path) -> None:
    smoke = tmp_path / "test_direct_junit_ok.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    junit = _unique_build_junit("direct-junit")
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(smoke),
            "-q",
            "-p",
            "no:cacheprovider",
            "--junit-xml",
            str(junit),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
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
