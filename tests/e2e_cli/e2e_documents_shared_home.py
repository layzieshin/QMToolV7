"""Isolated QMTOOL_HOME + init + demo users for documents CLI e2e tests."""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_TMP: tempfile.TemporaryDirectory | None = None
_ENV: dict[str, str] | None = None


def _ensure() -> dict[str, str]:
    global _TMP, _ENV
    if _ENV is not None:
        return _ENV
    _TMP = tempfile.TemporaryDirectory()
    env = dict(os.environ)
    env["QMTOOL_HOME"] = str(Path(_TMP.name) / "home")
    init = subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", "init", "--non-interactive", "--admin-password", "admin"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert init.returncode == 0, init.stderr + init.stdout
    login = subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", "login", "--username", "admin", "--password", "admin"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert login.returncode == 0, login.stderr + login.stdout
    for username, password, role in (
        ("user", "user", "User"),
        ("qmb", "qmb", "QMB"),
        ("editor-1", "editor-1", "User"),
    ):
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "interfaces.cli.main",
                "users",
                "create",
                "--username",
                username,
                "--password",
                password,
                "--role",
                role,
            ],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert r.returncode == 0, r.stderr + r.stdout
    subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", "logout"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    _ENV = env
    return _ENV


def run_cli(*args: str, cwd: str | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base = _ensure()
    merged = dict(os.environ)
    merged.update(base)
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", *args],
        text=True,
        capture_output=True,
        cwd=cwd,
        check=False,
        env=merged,
    )


def cleanup() -> None:
    global _TMP, _ENV
    if _TMP is not None:
        _TMP.cleanup()
    _TMP = None
    _ENV = None


atexit.register(cleanup)
