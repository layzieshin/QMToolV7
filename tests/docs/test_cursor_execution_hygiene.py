from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
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
GATE_RUNNER = TOOLS / "run-pytest-gate.ps1"
JUNIT_GATE_OWNER_VALIDATION_EXIT = 91
_BOUNDED_SUBPROCESS_TIMEOUT_SECONDS = 120.0
_BOUNDED_TASKKILL_TIMEOUT_SECONDS = 15.0
_BOUNDED_POST_KILL_COMMUNICATE_TIMEOUT_SECONDS = 15.0


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


def _terminate_process_tree(pid: int) -> None:
    if os.name != "nt":
        raise AssertionError("process-tree cleanup is only implemented for Windows launcher/gate tests")
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_BOUNDED_TASKKILL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        pass


def _communicate_after_kill(proc: subprocess.Popen[str]) -> tuple[str, str]:
    try:
        return proc.communicate(timeout=_BOUNDED_POST_KILL_COMMUNICATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            return proc.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            return "", ""


def _run_subprocess_bounded(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    timeout_seconds: float = _BOUNDED_SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(proc.pid)
        stdout, stderr = _communicate_after_kill(proc)
        raise AssertionError(
            f"subprocess timed out after {timeout_seconds}s: {' '.join(command)}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


def _run_powershell(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return _run_subprocess_bounded(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *args,
        ],
        env=env,
    )


def _run_pytest_gate(
    tmp_path: Path,
    *,
    smoke: Path,
    junit: Path,
    python_path: Path | None = None,
    gate_id: str = "hygiene",
) -> subprocess.CompletedProcess[str]:
    return _run_powershell(
        GATE_RUNNER,
        "-GateId",
        gate_id,
        "-PythonPath",
        str(python_path or Path(sys.executable)),
        "-JUnitPath",
        str(junit),
        str(smoke),
        "-q",
    )


def _invoke_junit_gate_owner(
    tmp_path: Path,
    junit: Path,
    pytest_exit: int,
) -> subprocess.CompletedProcess[str]:
    gate_path = GATE_RUNNER.resolve()
    junit_path = junit.resolve()
    harness = tmp_path / "invoke_junit_gate_owner.ps1"
    harness.write_text(
        f". '{gate_path}' -GateId hygiene\n"
        f"$code = Get-JUnitGateExitCode -JUnitPath '{junit_path}' -PytestExitCode {pytest_exit}\n"
        "exit $code\n",
        encoding="utf-8",
    )
    return _run_subprocess_bounded(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
    )


def _assert_cursor_agent_resolves_to_fixture(env: dict[str, str], expected_fixture: Path) -> None:
    completed = _run_subprocess_bounded(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "(Get-Command cursor-agent -ErrorAction Stop).Source",
        ],
        env=env,
        timeout_seconds=30.0,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    resolved = Path(completed.stdout.strip()).resolve()
    expected = expected_fixture.resolve()
    assert resolved == expected, (
        "cursor-agent must resolve to the test fixture before launcher invocation; "
        f"expected={expected} resolved={resolved}"
    )


def test_default_basetemp_is_short_unique_and_explicit_override_is_preserved() -> None:
    assert not _has_explicit_basetemp(["tests/docs", "-q"])
    assert _has_explicit_basetemp(["--basetemp", "build/custom"])
    assert _has_explicit_basetemp(["--basetemp=build/custom"])

    first_token = "a" * 8
    second_token = "b" * 8
    first = _unique_default_basetemp(ROOT, pid=123, token=first_token)
    second = _unique_default_basetemp(ROOT, pid=123, token=second_token)
    assert first == ROOT / "build" / "pt" / f"123-{first_token}"
    assert second == ROOT / "build" / "pt" / "123-bbbbbbbb"
    assert first != second


def test_direct_pytest_preserves_basetemp_from_pytest_addopts(tmp_path: Path) -> None:
    smoke = tmp_path / "test_addopts_basetemp.py"
    custom_basetemp = tmp_path / "custom-basetemp"
    custom_basetemp_posix = custom_basetemp.as_posix()
    smoke.write_text(
        "from pathlib import Path\n"
        "def test_basetemp(pytestconfig):\n"
        f"    assert Path(str(pytestconfig.option.basetemp)).resolve() == Path(r'{custom_basetemp}').resolve()\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTEST_ADDOPTS"] = f"--basetemp={custom_basetemp_posix}"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", str(smoke), "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


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
@pytest.mark.parametrize(
    ("proxy_name", "proxy_value"),
    [
        ("HTTP_PROXY", "http://127.0.0.1:9"),
        ("ALL_PROXY", "socks5://127.0.0.1:9"),
    ],
)
def test_execution_host_preflight_rejects_disabled_cursor_proxy_without_repairing_it(
    proxy_name: str,
    proxy_value: str,
) -> None:
    env = dict(os.environ)
    env[proxy_name] = proxy_value
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
def test_execution_host_preflight_accepts_git_metadata_write_probe() -> None:
    completed = _run_powershell(
        TOOLS / "assert-execution-host.ps1",
        "-TargetRoot",
        str(ROOT),
        "-RequireGitWrite",
        "-Json",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "READY"
    assert payload["checks"]["git_worktree_metadata_writable"] == "PASS"


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


@pytest.mark.skipif(os.name != "nt", reason="Windows dangling junction guard is Windows-only")
def test_pytest_gate_wrapper_rejects_dangling_junction_target_under_build(
    tmp_path: Path,
) -> None:
    pt_dir = ROOT / "build" / "pt"
    ptmp_dir = ROOT / "build" / "ptmp"
    pt_dir.mkdir(parents=True, exist_ok=True)
    ptmp_dir.mkdir(parents=True, exist_ok=True)
    before_pt = _snapshot_build_temp_children(pt_dir)
    before_ptmp = _snapshot_build_temp_children(ptmp_dir)

    token = uuid4().hex[:8]
    target_dir = tmp_path / f"dangling-target-{token}"
    target_dir.mkdir()
    dangling_junction = ROOT / "build" / f"dangling-reparse-{token}.xml"
    mklink = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(dangling_junction), str(target_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if mklink.returncode != 0:
        combined = mklink.stderr or mklink.stdout
        pytest.skip(f"cannot create junction in this environment: {combined}")

    target_dir.rmdir()
    assert not dangling_junction.exists()
    assert os.path.lexists(dangling_junction)

    smoke = tmp_path / "test_dangling_junction_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    outside_escape = target_dir.parent / f"escape-{token}.xml"
    try:
        completed = _run_powershell(
            TOOLS / "run-pytest-gate.ps1",
            "-GateId",
            "hygiene",
            "-PythonPath",
            sys.executable,
            "-JUnitPath",
            str(dangling_junction.relative_to(ROOT)),
            str(smoke),
            "-q",
        )
        assert completed.returncode != 0
        combined = (completed.stderr or completed.stdout).lower()
        assert "reparse point" in combined or "junction" in combined
        assert not outside_escape.exists()

        after_pt = _snapshot_build_temp_children(pt_dir)
        after_ptmp = _snapshot_build_temp_children(ptmp_dir)
        new_wrapper_pt = _wrapper_owned_pt_entries(after_pt - before_pt)
        new_wrapper_ptmp = _wrapper_owned_ptmp_entries(after_ptmp - before_ptmp)
        assert not new_wrapper_pt
        assert not new_wrapper_ptmp
    finally:
        if os.path.lexists(dangling_junction):
            dangling_junction.rmdir()


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
    assert "$coordinatorModel" in launcher
    assert "agent-system.json" in launcher
    assert "--" in launcher
    assert "Invoke-CursorAgentProcess" in launcher
    assert "$startInfo.WorkingDirectory" in launcher
    assert "[switch]$Interactive" in launcher
    assert "[switch]$AutoReview" in launcher
    assert "$WorkPackage" in launcher
    assert "QMTOOL_WORKFLOW_STATE_PATH" in launcher
    assert "QMTOOL_RUNTIME_LOG_PATH" in launcher
    assert "GIT_DIR" in launcher
    assert "ReparsePoint" in launcher
    assert "GetFullPath" in launcher
    assert "launch_correlation_id" in launcher
    assert "$ResumeSession" in launcher
    assert "$promptText" in launcher
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
    assert "Codex implementation entry" in agents
    assert "Codex implementation entry" in system
    assert "build/codex-cursor-entry" in system
    assert "binding label only" in agents
    assert "not an atomic exclusive-writer lock" in system


def _launcher_mock_env(tmp_path: Path, *, exit_code: int = 0) -> tuple[dict[str, str], Path, Path]:
    mock_dir = tmp_path / "bin"
    mock_dir.mkdir()
    args_log = tmp_path / "argv.log"
    capture_script = mock_dir / "capture_argv.py"
    capture_script.write_text(
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "log = Path(os.environ['QMTOOL_MOCK_ARGV_LOG'])\n"
        "log.parent.mkdir(parents=True, exist_ok=True)\n"
        "args = sys.argv[1:]\n"
        "payload = {'argv': args, 'cwd': os.getcwd()}\n"
        "if '--' in args:\n"
        "    split = args.index('--')\n"
        "    payload['prompt_args'] = args[split + 1 :]\n"
        "log.write_text(json.dumps(payload) + '\\n', encoding='utf-8')\n"
        f"raise SystemExit(int(os.environ.get('QMTOOL_MOCK_EXIT_CODE', '{exit_code}')))\n",
        encoding="utf-8",
    )
    mock_agent = mock_dir / "cursor-agent.ps1"
    mock_agent.write_text(
        "$payload = @{ argv = @($args); cwd = (Get-Location).Path }\n"
        "$dash = [Array]::IndexOf([object[]]@($args), '--')\n"
        "if ($dash -ge 0 -and $dash -lt ($args.Length - 1)) {\n"
        "    $payload.prompt_args = @($args[($dash + 1)..($args.Length - 1)])\n"
        "}\n"
        "$json = $payload | ConvertTo-Json -Compress\n"
        "[System.IO.File]::WriteAllText(\n"
        "    $env:QMTOOL_MOCK_ARGV_LOG,\n"
        '    $json + [Environment]::NewLine,\n'
        "    [System.Text.UTF8Encoding]::new($false)\n"
        ")\n"
        "exit [int]$env:QMTOOL_MOCK_EXIT_CODE\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    pathext = env.get("PATHEXT", ".COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC;")
    if not pathext.upper().startswith(".PS1"):
        env["PATHEXT"] = ".PS1;" + pathext
    env["PATH"] = str(mock_dir) + os.pathsep + env.get("PATH", "")
    env["QMTOOL_MOCK_ARGV_LOG"] = str(args_log)
    env["QMTOOL_MOCK_EXIT_CODE"] = str(exit_code)
    _assert_cursor_agent_resolves_to_fixture(env, mock_agent)
    return env, args_log, mock_agent


def _create_isolated_fresh_entry_repo(
    tmp_path: Path,
    *,
    branch: str = "feature/entry-test",
    workflow_status: str = "IDLE",
    human_gate: bool = False,
    workflow_bytes: bytes | None = None,
    work_package_in_state: str | None = None,
) -> dict[str, object]:
    repo = tmp_path / "entry-repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch", branch, str(repo)],
        capture_output=True,
        text=True,
        check=True,
    )
    tools = repo / ".cursor" / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    shutil.copy(TOOLS / "invoke-cursor-agent.ps1", tools / "invoke-cursor-agent.ps1")
    shutil.copy(TOOLS / "assert-execution-host.ps1", tools / "assert-execution-host.ps1")
    cursor_dir = repo / ".cursor"
    shutil.copy(ROOT / ".cursor" / "agent-system.json", cursor_dir / "agent-system.json")
    (repo / ".gitignore").write_text(
        "build/\n.cursor/runtime/workflow-state.json\n",
        encoding="utf-8",
    )
    for relative in (
        ".gitignore",
        ".cursor/tools/invoke-cursor-agent.ps1",
        ".cursor/tools/assert-execution-host.ps1",
        ".cursor/agent-system.json",
    ):
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
            "seed fresh-entry fixture",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    current_branch = subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    runtime = cursor_dir / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    state_path = runtime / "workflow-state.json"
    if workflow_bytes is not None:
        state_path.write_bytes(workflow_bytes)
    else:
        state = json.loads(
            (ROOT / ".cursor" / "runtime" / "workflow-state.template.json").read_text(
                encoding="utf-8"
            )
        )
        state["status"] = workflow_status
        state["human_gate"] = human_gate
        if work_package_in_state is not None:
            state["work_package"] = work_package_in_state
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return {
        "repo": repo,
        "branch": current_branch,
        "head": head,
        "launcher": tools / "invoke-cursor-agent.ps1",
        "state_path": state_path,
    }


def _invoke_launcher(
    env: dict[str, str],
    *,
    prompt: str | None = None,
    prompt_path: Path | None = None,
    force: bool = False,
    auto_review: bool = False,
    work_package: str | None = None,
    expected_branch: str | None = None,
    expected_head: str | None = None,
    prompt_as_separate_arg: bool = False,
    interactive: bool = False,
    resume_session: str | None = None,
    resume_flag_only: bool = False,
    target_root: Path = ROOT,
    launcher_path: Path | None = None,
    cwd: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    args = [
        POWERSHELL,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(launcher_path or (TOOLS / "invoke-cursor-agent.ps1")),
        "-TargetRoot",
        str(target_root),
    ]
    if prompt_path is not None:
        args.append("-PromptPath")
        args.append(str(prompt_path))
    elif prompt is not None:
        if prompt_as_separate_arg or prompt.endswith("\\"):
            args.extend(["-Prompt", prompt])
        else:
            args.append("-Prompt:" + prompt)
    if force:
        args.append("-Force")
    if auto_review:
        args.append("-AutoReview")
    if work_package is not None:
        args.extend(["-WorkPackage", work_package])
    if expected_branch is not None:
        args.extend(["-ExpectedBranch", expected_branch])
    if expected_head is not None:
        args.extend(["-ExpectedHead", expected_head])
    if interactive:
        args.append("-Interactive")
    if resume_flag_only or resume_session is not None:
        args.append("-ResumeSession")
        if resume_session is not None:
            args.append(resume_session)
    return _run_subprocess_bounded(args, env=env, cwd=cwd)


def _launcher_argv_payload(captured: str) -> dict[str, object]:
    return json.loads(captured.strip())


def _launcher_prompt_after_double_dash(captured: str) -> str:
    payload = _launcher_argv_payload(captured)
    prompt_args = payload.get("prompt_args")
    assert isinstance(prompt_args, list), payload
    assert prompt_args, payload
    if len(prompt_args) == 1:
        return str(prompt_args[0])
    return "\n".join(str(part) for part in prompt_args)


def _extract_powershell_function(source: str, name: str) -> str:
    marker = f"function {name} {{"
    start = source.find(marker)
    if start < 0:
        raise AssertionError(f"missing PowerShell function: {name}")
    depth = 0
    for index in range(start + len(marker) - 1, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1] + "\n"
    raise AssertionError(f"unterminated PowerShell function: {name}")


def _launcher_child_cwd(captured: str) -> str:
    payload = _launcher_argv_payload(captured)
    cwd = payload.get("cwd")
    assert isinstance(cwd, str), payload
    return cwd


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
@pytest.mark.parametrize(
    ("interactive", "resume_session", "resume_flag_only"),
    [
        (False, None, False),
        (True, None, False),
        (False, "session-chat-abc", False),
    ],
    ids=("default", "interactive", "resume"),
)
def test_cursor_launcher_child_cwd_matches_target_from_foreign_parent_cwd(
    tmp_path: Path,
    interactive: bool,
    resume_session: str | None,
    resume_flag_only: bool,
) -> None:
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path, exit_code=7)
    foreign_cwd = tmp_path / "foreign-parent"
    foreign_cwd.mkdir()
    completed = _invoke_launcher(
        env,
        prompt="cwd probe",
        interactive=interactive,
        resume_session=resume_session,
        resume_flag_only=resume_flag_only,
        cwd=foreign_cwd,
    )
    assert completed.returncode == 7, completed.stderr or completed.stdout
    captured = args_log.read_text(encoding="utf-8")
    child_cwd = Path(_launcher_child_cwd(captured)).resolve()
    assert child_cwd == ROOT.resolve()
    argv = _launcher_argv_payload(captured)["argv"]
    assert "--workspace" in argv
    workspace_index = argv.index("--workspace")
    assert Path(argv[workspace_index + 1]).resolve() == ROOT.resolve()
    assert "--model" in argv
    assert "composer-2.5" in argv
    if interactive:
        assert "--print" not in argv
        assert "--output-format" not in argv
    else:
        assert "--print" in argv
        assert "--output-format" in argv
        assert "text" in argv
    if resume_session is not None:
        assert "--resume" in argv
        assert resume_session in argv


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_invokes_mock_agent_with_single_prompt_argument(tmp_path: Path) -> None:
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    prompt = "inline prompt with spaces"
    completed = _invoke_launcher(env, prompt=prompt)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    captured = args_log.read_text(encoding="utf-8")
    argv = _launcher_argv_payload(captured)["argv"]
    assert "--model" in argv
    assert "composer-2.5" in argv
    assert _launcher_prompt_after_double_dash(captured) == prompt


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_reads_prompt_file_and_preserves_leading_dash(tmp_path: Path) -> None:
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    prompt_path = tmp_path / "prompt.txt"
    prompt = "-leading dash and spaces\nsecond line"
    prompt_path.write_text(prompt, encoding="utf-8")
    completed = _invoke_launcher(env, prompt_path=prompt_path)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    captured = args_log.read_text(encoding="utf-8")
    prompt_after = _launcher_prompt_after_double_dash(captured)
    assert prompt_after.startswith("-leading dash and spaces")
    assert prompt_path.read_text(encoding="utf-8") == prompt


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_inline_prompt_preserves_leading_dash(tmp_path: Path) -> None:
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    prompt = "-leading dash and spaces"
    completed = _invoke_launcher(env, prompt=prompt)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    captured = args_log.read_text(encoding="utf-8")
    assert _launcher_prompt_after_double_dash(captured) == prompt


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_native_argument_quoting_round_trips_windows_argv(tmp_path: Path) -> None:
    launcher = (TOOLS / "invoke-cursor-agent.ps1").read_text(encoding="utf-8")
    helper_script = tmp_path / "format-native-arg.ps1"
    helper_script.write_text(
        _extract_powershell_function(launcher, "Format-NativeCommandArgument")
        + "Add-Type @'\n"
        + "using System;\n"
        + "using System.Runtime.InteropServices;\n"
        + "using System.Text;\n"
        + "public static class NativeArgv {\n"
        + "  [DllImport(\"shell32.dll\", CharSet = CharSet.Unicode)]\n"
        + "  private static extern IntPtr CommandLineToArgvW(string lpCmdLine, out int pNumArgs);\n"
        + "  [DllImport(\"kernel32.dll\")] private static extern IntPtr LocalFree(IntPtr hMem);\n"
        + "  public static string[] Parse(string commandLine) {\n"
        + "    int argc; IntPtr argv = CommandLineToArgvW(commandLine, out argc);\n"
        + "    if (argv == IntPtr.Zero) { throw new InvalidOperationException(\"parse failed\"); }\n"
        + "    try {\n"
        + "      string[] args = new string[argc];\n"
        + "      IntPtr[] ptrs = new IntPtr[argc];\n"
        + "      Marshal.Copy(argv, ptrs, 0, argc);\n"
        + "      for (int i = 0; i < argc; i++) { args[i] = Marshal.PtrToStringUni(ptrs[i]); }\n"
        + "      return args;\n"
        + "    } finally { LocalFree(argv); }\n"
        + "  }\n"
        + "}\n"
        + "'@\n"
        + "$cases = @(\n"
        + "  '-leading dash and spaces`nsecond line',\n"
        + "  'say \"hello\" exactly',\n"
        + "  'path with spaces\\',\n"
        + "  'quote \"and\" newline`nterminal\\'\n"
        + ")\n"
        + "foreach ($expected in $cases) {\n"
        + "  $quoted = Format-NativeCommandArgument $expected\n"
        + "  $parsed = [NativeArgv]::Parse('dummy.exe ' + $quoted)\n"
        + "  if ($parsed.Count -ne 2 -or $parsed[1] -ne $expected) {\n"
        + "    Write-Error \"round-trip failed for: $expected -> $($parsed -join '|')\"\n"
        + "    exit 4\n"
        + "  }\n"
        + "}\n",
        encoding="utf-8",
    )
    helper = _run_subprocess_bounded(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper_script),
        ],
    )
    assert helper.returncode == 0, helper.stderr or helper.stdout


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_auto_review_switch_and_exit_passthrough(tmp_path: Path) -> None:
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path, exit_code=7)
    completed = _invoke_launcher(env, prompt="auto review off")
    assert completed.returncode == 7, completed.stderr or completed.stdout
    captured = args_log.read_text(encoding="utf-8")
    assert "--auto-review" not in _launcher_argv_payload(captured)["argv"]

    args_log.unlink()
    completed_auto_review = _invoke_launcher(env, prompt="auto review on", auto_review=True)
    assert completed_auto_review.returncode == 7, completed_auto_review.stderr or completed_auto_review.stdout
    captured_auto_review = args_log.read_text(encoding="utf-8")
    assert "--auto-review" in _launcher_argv_payload(captured_auto_review)["argv"]
    assert "--force" not in _launcher_argv_payload(captured_auto_review)["argv"]


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_rejects_auto_review_with_force_before_child(tmp_path: Path) -> None:
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    completed = _invoke_launcher(env, prompt="mutually exclusive", force=True, auto_review=True)
    assert completed.returncode != 0
    assert "AutoReview cannot be combined with Force" in (completed.stderr or completed.stdout)
    assert not args_log.exists()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_partial_binding_before_child(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="partial binding",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "must be supplied together" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_protected_main_branch(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="protected branch",
        work_package="codex-cursor-entry",
        expected_branch="main",
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "protected branch" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_non_immutable_head_before_child(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="branch name head",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["branch"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "40-character commit SHA" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_branch_and_head_mismatch_before_child(
    tmp_path: Path,
) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    branch = str(meta["branch"])
    head = str(meta["head"])
    state_bytes = meta["state_path"].read_bytes()
    wrong_branch = _invoke_launcher(
        env,
        prompt="wrong branch",
        work_package="codex-cursor-entry",
        expected_branch="feature/does-not-exist",
        expected_head=head,
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert wrong_branch.returncode != 0
    assert "ExpectedBranch mismatch" in (wrong_branch.stderr or wrong_branch.stdout)
    assert not args_log.exists()

    wrong_head = _invoke_launcher(
        env,
        prompt="wrong head",
        work_package="codex-cursor-entry",
        expected_branch=branch,
        expected_head="0" * 40,
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert wrong_head.returncode != 0
    assert "Git command failed" in (wrong_head.stderr or wrong_head.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_dirty_worktree_before_child(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    dirty_marker = meta["repo"] / "tracked-dirty.txt"
    dirty_marker.write_text("dirty\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(meta["repo"]), "add", "tracked-dirty.txt"],
        check=True,
    )
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="dirty target",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "clean worktree" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_active_workflow_before_child(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path, workflow_status="RUNNING")
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="active workflow",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "workflow status: RUNNING" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_human_gate_before_child(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path, human_gate=True)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="human gate",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "human_gate" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_malformed_workflow_before_child(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path, workflow_bytes=b"{not-json")
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="malformed workflow",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "valid workflow-state.json" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_conflicting_idle_ownership_before_child(
    tmp_path: Path,
) -> None:
    meta = _create_isolated_fresh_entry_repo(
        tmp_path,
        work_package_in_state="WP-OLD",
    )
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="conflicting ownership",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "conflicting work_package ownership" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_resume_combination_before_child(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="resume plus fresh entry",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        resume_session="session-chat-abc",
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "cannot be combined with ResumeSession" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_redirected_runtime_owner_before_child(
    tmp_path: Path,
) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    redirected_state = tmp_path / "foreign-workflow-state.json"
    redirected_state.write_text('{"status":"IDLE"}', encoding="utf-8")
    env["QMTOOL_WORKFLOW_STATE_PATH"] = str(redirected_state)
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="redirected runtime owner",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "QMTOOL_WORKFLOW_STATE_PATH" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_redirected_git_dir_before_child(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    env["GIT_DIR"] = str(tmp_path / "foreign-git-dir")
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="redirected git dir",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode != 0
    assert "GIT_DIR" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="Windows parent-junction guard is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_parent_junction_runtime_before_child(
    tmp_path: Path,
) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    repo = meta["repo"]
    state_path = meta["state_path"]
    state_bytes = state_path.read_bytes()
    outside_runtime = tmp_path / "outside-runtime"
    outside_runtime.mkdir()
    (outside_runtime / "workflow-state.json").write_bytes(state_bytes)
    runtime_dir = repo / ".cursor" / "runtime"
    state_path.unlink()
    runtime_dir.rmdir()
    junction = runtime_dir
    mklink = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside_runtime)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert mklink.returncode == 0, mklink.stderr or mklink.stdout
    try:
        completed = _invoke_launcher(
            env,
            prompt="parent junction runtime",
            work_package="codex-cursor-entry",
            expected_branch=str(meta["branch"]),
            expected_head=str(meta["head"]),
            target_root=repo,
            launcher_path=meta["launcher"],
        )
        assert completed.returncode != 0
        assert "reparse-point redirected canonical" in (completed.stderr or completed.stdout)
        assert not args_log.exists()
        assert (outside_runtime / "workflow-state.json").read_bytes() == state_bytes
    finally:
        if junction.exists():
            junction.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_rejects_redirected_launcher_before_child(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    foreign_tools = tmp_path / "foreign-tools"
    foreign_tools.mkdir()
    shutil.copy(TOOLS / "invoke-cursor-agent.ps1", foreign_tools / "invoke-cursor-agent.ps1")
    shutil.copy(TOOLS / "assert-execution-host.ps1", foreign_tools / "assert-execution-host.ps1")
    state_bytes = meta["state_path"].read_bytes()
    completed = _invoke_launcher(
        env,
        prompt="redirected launcher",
        work_package="codex-cursor-entry",
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=foreign_tools / "invoke-cursor-agent.ps1",
    )
    assert completed.returncode != 0
    assert "canonical invoke-cursor-agent.ps1" in (completed.stderr or completed.stdout)
    assert not args_log.exists()
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_fresh_entry_launches_child_and_records_journal(tmp_path: Path) -> None:
    meta = _create_isolated_fresh_entry_repo(tmp_path)
    env, args_log, mock_agent = _launcher_mock_env(tmp_path, exit_code=7)
    work_package = "codex-cursor-entry"
    journal = meta["repo"] / "build" / "codex-cursor-entry" / work_package / "execution-journal.md"
    state_bytes = meta["state_path"].read_bytes()
    config = json.loads((meta["repo"] / ".cursor" / "agent-system.json").read_text(encoding="utf-8"))
    coordinator_model = config["routing"]["coordinator_model"]
    completed = _invoke_launcher(
        env,
        prompt="fresh entry probe",
        work_package=work_package,
        expected_branch=str(meta["branch"]),
        expected_head=str(meta["head"]),
        target_root=meta["repo"],
        launcher_path=meta["launcher"],
    )
    assert completed.returncode == 7, completed.stderr or completed.stdout
    captured = args_log.read_text(encoding="utf-8")
    prompt_after = _launcher_prompt_after_double_dash(captured)
    assert "CODEX_ENTRY_BINDING" in prompt_after
    assert work_package in prompt_after
    assert str(meta["branch"]) in prompt_after
    assert str(meta["head"]) in prompt_after
    assert "binding label only" in prompt_after
    child_cwd = Path(_launcher_child_cwd(captured)).resolve()
    assert child_cwd == Path(meta["repo"]).resolve()
    argv = _launcher_argv_payload(captured)["argv"]
    model_index = argv.index("--model")
    assert argv[model_index + 1] == coordinator_model
    assert journal.is_file()
    journal_text = journal.read_text(encoding="utf-8")
    assert "## ENTRY_START" in journal_text
    assert "## ENTRY_RESULT" in journal_text
    assert "launch_correlation_id:" in journal_text
    assert "launcher-generated; not a native Cursor task/session id" in journal_text
    assert "child_exit_code: 7" in journal_text
    assert "child_executable:" in journal_text
    assert "child_working_directory:" in journal_text
    assert str(meta["repo"]) in journal_text
    child_executable_line = next(
        line for line in journal_text.splitlines() if line.startswith("- child_executable:")
    )
    assert Path(POWERSHELL).name.lower() in child_executable_line.lower()
    assert "native_cursor_task_session: unknown" in journal_text
    assert "package_result: unverified" in journal_text
    assert meta["state_path"].read_bytes() == state_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_force_switch_and_exit_passthrough(tmp_path: Path) -> None:
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path, exit_code=7)
    completed = _invoke_launcher(env, prompt="force off")
    assert completed.returncode == 7, completed.stderr or completed.stdout
    captured = args_log.read_text(encoding="utf-8")
    assert "--force" not in _launcher_argv_payload(captured)["argv"]

    args_log.unlink()
    completed_force = _invoke_launcher(env, prompt="force on", force=True)
    assert completed_force.returncode == 7, completed_force.stderr or completed_force.stdout
    captured_force = args_log.read_text(encoding="utf-8")
    assert "--force" in _launcher_argv_payload(captured_force)["argv"]


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_preflight_failure_skips_child(tmp_path: Path) -> None:
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    env["HTTP_PROXY"] = "http://127.0.0.1:9"
    completed = _invoke_launcher(env, prompt="should not run")
    assert completed.returncode == 3
    assert not args_log.exists()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_model_matches_coordinator_config(tmp_path: Path) -> None:
    config = json.loads((ROOT / ".cursor" / "agent-system.json").read_text(encoding="utf-8"))
    coordinator_model = config["routing"]["coordinator_model"]
    launcher = (TOOLS / "invoke-cursor-agent.ps1").read_text(encoding="utf-8")
    assert "agent-system.json" in launcher
    assert "coordinator_model" in launcher
    assert "$coordinatorModel" in launcher
    assert "ArgumentList" in launcher
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    completed = _invoke_launcher(env, prompt="model probe")
    assert completed.returncode == 0, completed.stderr or completed.stdout
    argv = _launcher_argv_payload(args_log.read_text(encoding="utf-8"))["argv"]
    model_index = argv.index("--model")
    assert argv[model_index + 1] == coordinator_model


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_inline_prompt_preserves_embedded_quotes(tmp_path: Path) -> None:
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    prompt = 'say "hello" exactly'
    completed = _invoke_launcher(env, prompt=prompt)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    captured = args_log.read_text(encoding="utf-8")
    assert _launcher_prompt_after_double_dash(captured) == prompt


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_passes_with_valid_junit(tmp_path: Path) -> None:
    smoke = tmp_path / "test_gate_pass.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    junit = _unique_build_junit("gate-owner-pass")
    completed = _run_pytest_gate(tmp_path, smoke=smoke, junit=junit)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert junit.is_file()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_preserves_nonzero_pytest_exit(tmp_path: Path) -> None:
    smoke = tmp_path / "test_gate_fail.py"
    smoke.write_text("def test_smoke():\n    assert False\n", encoding="utf-8")
    junit = _unique_build_junit("gate-owner-pytest-fail")
    completed = _run_pytest_gate(tmp_path, smoke=smoke, junit=junit)
    assert completed.returncode == 1, completed.stderr or completed.stdout
    assert junit.is_file()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_rejects_missing_junit(tmp_path: Path) -> None:
    junit = _unique_build_junit("gate-owner-missing")
    completed = _invoke_junit_gate_owner(tmp_path, junit, 0)
    assert completed.returncode == JUNIT_GATE_OWNER_VALIDATION_EXIT
    assert "missing JUnit" in (completed.stderr or completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_rejects_malformed_junit(tmp_path: Path) -> None:
    junit = _unique_build_junit("gate-owner-malformed")
    junit.parent.mkdir(parents=True, exist_ok=True)
    junit.write_text("<broken", encoding="utf-8")
    completed = _invoke_junit_gate_owner(tmp_path, junit, 0)
    assert completed.returncode == JUNIT_GATE_OWNER_VALIDATION_EXIT
    assert "malformed JUnit" in (completed.stderr or completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_rejects_zero_test_junit(tmp_path: Path) -> None:
    junit = _unique_build_junit("gate-owner-zero-tests")
    junit.parent.mkdir(parents=True, exist_ok=True)
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuite tests="0" failures="0" errors="0"></testsuite>',
        encoding="utf-8",
    )
    completed = _invoke_junit_gate_owner(tmp_path, junit, 0)
    assert completed.returncode == JUNIT_GATE_OWNER_VALIDATION_EXIT
    assert "zero tests" in (completed.stderr or completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_rejects_failure_junit(tmp_path: Path) -> None:
    junit = _unique_build_junit("gate-owner-failure")
    junit.parent.mkdir(parents=True, exist_ok=True)
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuite tests="1" failures="1" errors="0"></testsuite>',
        encoding="utf-8",
    )
    completed = _invoke_junit_gate_owner(tmp_path, junit, 0)
    assert completed.returncode == JUNIT_GATE_OWNER_VALIDATION_EXIT
    assert "failures=1" in (completed.stderr or completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_rejects_error_junit(tmp_path: Path) -> None:
    junit = _unique_build_junit("gate-owner-error")
    junit.parent.mkdir(parents=True, exist_ok=True)
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuite tests="1" failures="0" errors="1"></testsuite>',
        encoding="utf-8",
    )
    completed = _invoke_junit_gate_owner(tmp_path, junit, 0)
    assert completed.returncode == JUNIT_GATE_OWNER_VALIDATION_EXIT
    assert "errors=1" in (completed.stderr or completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_rejects_missing_required_counters(tmp_path: Path) -> None:
    junit = _unique_build_junit("gate-owner-missing-counters")
    junit.parent.mkdir(parents=True, exist_ok=True)
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?><testsuite tests="1"></testsuite>',
        encoding="utf-8",
    )
    completed = _invoke_junit_gate_owner(tmp_path, junit, 0)
    assert completed.returncode == JUNIT_GATE_OWNER_VALIDATION_EXIT
    assert "missing failures counter" in (completed.stderr or completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_rejects_nonnumeric_counters(tmp_path: Path) -> None:
    junit = _unique_build_junit("gate-owner-nonnumeric-counters")
    junit.parent.mkdir(parents=True, exist_ok=True)
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuite tests="abc" failures="0" errors="0"></testsuite>',
        encoding="utf-8",
    )
    completed = _invoke_junit_gate_owner(tmp_path, junit, 0)
    assert completed.returncode == JUNIT_GATE_OWNER_VALIDATION_EXIT
    assert "invalid tests counter" in (completed.stderr or completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_rejects_negative_counters(tmp_path: Path) -> None:
    junit = _unique_build_junit("gate-owner-negative-counters")
    junit.parent.mkdir(parents=True, exist_ok=True)
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuite tests="-1" failures="0" errors="0"></testsuite>',
        encoding="utf-8",
    )
    completed = _invoke_junit_gate_owner(tmp_path, junit, 0)
    assert completed.returncode == JUNIT_GATE_OWNER_VALIDATION_EXIT
    assert "negative tests counter" in (completed.stderr or completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_wrapper_rejects_preexisting_junit_target(tmp_path: Path) -> None:
    smoke = tmp_path / "test_stale_junit_smoke.py"
    smoke.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    junit = _unique_build_junit("gate-stale-junit")
    junit.parent.mkdir(parents=True, exist_ok=True)
    stale_bytes = (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<testsuite tests="1" failures="0" errors="0"></testsuite>'
    )
    junit.write_bytes(stale_bytes)
    completed = _run_pytest_gate(tmp_path, smoke=smoke, junit=junit)
    assert completed.returncode != 0
    assert "must not exist before the gate run" in (completed.stderr or completed.stdout)
    assert junit.read_bytes() == stale_bytes


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gate wrapper is Windows-only")
def test_pytest_gate_owner_preserves_nonzero_pytest_exit_without_junit(tmp_path: Path) -> None:
    junit = _unique_build_junit("gate-owner-pytest-nonzero")
    completed = _invoke_junit_gate_owner(tmp_path, junit, 1)
    assert completed.returncode == 1


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_mock_resolution_guard_rejects_wrong_fixture_path(tmp_path: Path) -> None:
    wrong_dir = tmp_path / "wrong-bin"
    expected_dir = tmp_path / "expected-bin"
    wrong_dir.mkdir()
    expected_dir.mkdir()
    wrong_agent = wrong_dir / "cursor-agent.cmd"
    expected_agent = expected_dir / "cursor-agent.cmd"
    wrong_agent.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    expected_agent.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = str(wrong_dir) + os.pathsep + env.get("PATH", "")
    with pytest.raises(AssertionError, match="cursor-agent must resolve to the test fixture"):
        _assert_cursor_agent_resolves_to_fixture(env, expected_agent)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher contract is Windows-only")
def test_cursor_launcher_argument_list_preserves_terminal_backslash_quotes_and_newlines(
    tmp_path: Path,
) -> None:
    launcher = (TOOLS / "invoke-cursor-agent.ps1").read_text(encoding="utf-8")
    env, args_log, _mock_agent = _launcher_mock_env(tmp_path)
    prompt = 'quote "and" newline\nterminal\\'
    harness = tmp_path / "argument-list-smoke.ps1"
    harness.write_text(
        _extract_powershell_function(launcher, "Format-NativeCommandArgument")
        + _extract_powershell_function(launcher, "Invoke-CursorAgentProcess")
        + f'$env:QMTOOL_MOCK_ARGV_LOG = "{args_log.as_posix()}"\n'
        + f'$env:QMTOOL_MOCK_EXIT_CODE = "0"\n'
        + f'$capture = "{(tmp_path / "bin" / "capture_argv.py")}"\n'
        + f'$python = "{sys.executable}"\n'
        + '$prompt = "quote `"and`" newline`nterminal\\"\n'
        + "$args = @($capture,'--print','--output-format','text','--workspace','"
        + str(ROOT).replace("\\", "\\\\")
        + "','--model','composer-2.5','--',$prompt)\n"
        + "$result = Invoke-CursorAgentProcess -Executable $python -ArgumentList $args -WorkingDirectory '"
        + str(ROOT).replace("\\", "\\\\")
        + "'\n"
        + "exit $result.ExitCode\n",
        encoding="utf-8",
    )
    completed = _run_subprocess_bounded(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        env=env,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    captured = args_log.read_text(encoding="utf-8")
    assert _launcher_prompt_after_double_dash(captured) == prompt
