from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4


def _has_explicit_basetemp(args: tuple[str, ...] | list[str]) -> bool:
    return any(arg == "--basetemp" or arg.startswith("--basetemp=") for arg in args)


def _unique_default_basetemp(root: Path, *, pid: int | None = None, token: str | None = None) -> Path:
    process_id = os.getpid() if pid is None else pid
    run_token = uuid4().hex[:8] if token is None else token
    return root / "build" / "pt" / f"{process_id}-{run_token}"


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    """Keep concurrent/default pytest processes out of a shared Windows basetemp."""

    args = tuple(str(arg) for arg in config.invocation_params.args)
    if _has_explicit_basetemp(args):
        return
    basetemp = _unique_default_basetemp(Path(str(config.rootpath)))
    basetemp.parent.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = basetemp
