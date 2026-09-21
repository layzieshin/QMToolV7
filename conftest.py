from __future__ import annotations

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest


def _has_explicit_basetemp(args: tuple[str, ...] | list[str]) -> bool:
    return any(arg == "--basetemp" or arg.startswith("--basetemp=") for arg in args)


def _unique_default_basetemp(root: Path, *, pid: int | None = None, token: str | None = None) -> Path:
    process_id = os.getpid() if pid is None else pid
    run_token = uuid4().hex[:8] if token is None else token
    return root / "build" / "pt" / f"{process_id}-{run_token}"


def _resolve_junit_target(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _is_tracked_repo_path(repo_root: Path, target: Path) -> bool:
    try:
        relative = target.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative.as_posix()],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _validate_junit_target(repo_root: Path, target: Path) -> None:
    build_root = (repo_root / "build").resolve()
    resolved = target.resolve()
    if resolved.suffix.lower() != ".xml":
        raise pytest.UsageError(f"JUnit output must use a .xml extension: {resolved}")
    if _is_tracked_repo_path(repo_root, resolved):
        raise pytest.UsageError(
            f"JUnit output must not target a tracked repository path: {resolved}"
        )
    try:
        resolved.relative_to(build_root)
    except ValueError:
        raise pytest.UsageError(
            f"--junitxml/--junit-xml must target a .xml file under {build_root}, not {resolved}"
        )


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    """Keep concurrent/default pytest processes out of a shared Windows basetemp."""

    repo_root = Path(str(config.rootpath))
    xmlpath = getattr(config.option, "xmlpath", None)
    if xmlpath:
        _validate_junit_target(repo_root, _resolve_junit_target(repo_root, str(xmlpath)))

    args = tuple(str(arg) for arg in config.invocation_params.args)
    if _has_explicit_basetemp(args):
        return
    basetemp = _unique_default_basetemp(repo_root)
    basetemp.parent.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = basetemp
