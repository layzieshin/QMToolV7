"""Deterministic real-process orchestration for J04-M0 final acceptance (test-only).

Not a product entrypoint. Starts ``python -m src.backend`` on the canonical port,
tracks only self-spawned PIDs, and redacts logs written under ``build/j04-m0-closure/``.
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
BACKEND_MODULE = "src.backend"
FINAL_ACCEPTANCE_ENV = "QMTOOL_J04_FINAL_ACCEPTANCE"
FINAL_ACCEPTANCE_OPT_IN = "I_UNDERSTAND_THIS_IS_A_REAL_ACCEPTANCE_RUN"
CLOSURE_EVIDENCE_RELATIVE = ("build", "j04-m0-closure")
REALPROCESS_WORKSPACE_PREFIX = "cp08-realprocess-ws"

_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
_TOKEN_JSON_RE = re.compile(r'("token"\s*:\s*")[^"]+(")', re.IGNORECASE)
_PG_DSN_RE = re.compile(r"postgresql://[^\s\"']+", re.IGNORECASE)
_PASSWORD_KV_RE = re.compile(r"(password=)([^\s\"']+)", re.IGNORECASE)
_SECRET_ENV_RE = re.compile(
    r"(QMTOOL_PG_TEST_ADMIN_DSN|QMTOOL_PG_DSN|QMTOOL_PG_PASSWORD)(=)([^\s\"']+)",
    re.IGNORECASE,
)


class HarnessError(RuntimeError):
    """Base harness failure."""


class HarnessBlockedError(HarnessError):
    """Precondition blocked the harness (foreign listener, missing opt-in, etc.)."""


class HarnessStartupError(HarnessError):
    """Managed process failed to become ready."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def closure_evidence_root() -> Path:
    """Resolved gitignored evidence root for J04-M0 closure runs."""
    return (repo_root().joinpath(*CLOSURE_EVIDENCE_RELATIVE)).resolve()


def require_inside_closure_evidence(path: Path) -> Path:
    """Reject any path that does not resolve under ``build/j04-m0-closure``."""
    resolved = Path(path).resolve()
    root = closure_evidence_root()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HarnessBlockedError(
            f"workspace must resolve under {root}; rejected {resolved}"
        ) from exc
    return resolved


def allocate_realprocess_workspace() -> Path:
    """Create a unique, never-reused realprocess workspace under the closure root.

    Layout: ``build/j04-m0-closure/cp08-realprocess-ws/<UTC-timestamp>-<uuid>/``.
    Does not delete existing paths. Evidence remains for later inspection.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{stamp}-{uuid.uuid4().hex}"
    candidate = closure_evidence_root() / REALPROCESS_WORKSPACE_PREFIX / run_id
    resolved = require_inside_closure_evidence(candidate)
    if resolved.exists():
        raise HarnessBlockedError(
            f"refusing to reuse existing realprocess workspace: {resolved}"
        )
    resolved.mkdir(parents=True, exist_ok=False)
    return resolved


def python_executable() -> str:
    return os.environ.get("QMTOOL_ACCEPTANCE_PYTHON", sys.executable)


def redact_log_text(text: str) -> str:
    """Remove tokens, DSNs, and password material from log payloads."""
    redacted = str(text or "")
    redacted = _BEARER_RE.sub("Bearer <redacted>", redacted)
    redacted = _TOKEN_JSON_RE.sub(r"\1<redacted>\2", redacted)
    redacted = _PG_DSN_RE.sub("postgresql://<redacted>", redacted)
    redacted = _PASSWORD_KV_RE.sub(r"\1<redacted>", redacted)
    redacted = _SECRET_ENV_RE.sub(r"\1\2<redacted>", redacted)
    return redacted


def is_port_free(host: str = BACKEND_HOST, port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def assert_backend_port_free(host: str = BACKEND_HOST, port: int = BACKEND_PORT) -> None:
    if not is_port_free(host, port):
        raise HarnessBlockedError(
            f"backend port {host}:{port} is already in use; refusing to start harness backend"
        )


def require_final_acceptance_opt_in() -> None:
    if os.environ.get(FINAL_ACCEPTANCE_ENV, "").strip() != FINAL_ACCEPTANCE_OPT_IN:
        raise HarnessBlockedError(
            f"{FINAL_ACCEPTANCE_ENV} must equal the documented final acceptance opt-in value"
        )


@dataclass
class ManagedProcess:
    pid: int
    popen: subprocess.Popen[str]
    label: str


@dataclass
class J04M0RealProcessHarness:
    """Orchestrate backend + client worker subprocesses with isolated homes."""

    workspace: Path
    log_dir: Path | None = None
    backend_home: Path | None = None
    client1_home: Path | None = None
    client2_home: Path | None = None
    backend_url: str = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
    _processes: list[ManagedProcess] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        if self.log_dir is None:
            self.log_dir = self.workspace / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if self.backend_home is None:
            self.backend_home = self.workspace / "backend-home"
        if self.client1_home is None:
            self.client1_home = self.workspace / "client1-home"
        if self.client2_home is None:
            self.client2_home = self.workspace / "client2-home"
        for home in (self.backend_home, self.client1_home, self.client2_home):
            home.mkdir(parents=True, exist_ok=True)

    def write_log(self, name: str, content: str) -> Path:
        assert self.log_dir is not None
        path = self.log_dir / name
        path.write_text(redact_log_text(content), encoding="utf-8")
        return path

    def _register_process(self, popen: subprocess.Popen[str], *, label: str) -> ManagedProcess:
        if popen.pid is None:
            raise HarnessStartupError(f"{label} subprocess did not receive a PID")
        managed = ManagedProcess(pid=int(popen.pid), popen=popen, label=label)
        self._processes.append(managed)
        return managed

    def start_backend(self, *, extra_env: dict[str, str] | None = None) -> ManagedProcess:
        assert_backend_port_free()
        assert self.backend_home is not None
        env = os.environ.copy()
        env["QMTOOL_HOME"] = str(self.backend_home)
        env.setdefault("PYTHONPATH", str(repo_root()))
        if extra_env:
            env.update(extra_env)
        command = [python_executable(), "-m", BACKEND_MODULE]
        popen = subprocess.Popen(
            command,
            cwd=str(repo_root()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return self._register_process(popen, label="backend")

    def wait_for_health(self, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
        url = f"{self.backend_url.rstrip('/')}/health"
        deadline = time.monotonic() + timeout_seconds
        last_error = "unknown"
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1.0) as response:
                    body = response.read().decode("utf-8")
                    if response.status == 200:
                        return {"status": response.status, "body": body}
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
            except Exception as exc:  # noqa: BLE001
                last_error = type(exc).__name__
            time.sleep(0.25)
        raise HarnessStartupError(f"backend health check timed out ({last_error})")

    def start_client_worker(
        self,
        *,
        home: Path,
        args: list[str],
        label: str,
        extra_env: dict[str, str] | None = None,
    ) -> ManagedProcess:
        env = os.environ.copy()
        env["QMTOOL_HOME"] = str(home)
        env["QMTOOL_BACKEND_URL"] = self.backend_url
        env.setdefault("PYTHONPATH", str(repo_root()))
        if extra_env:
            env.update(extra_env)
        command = [
            python_executable(),
            str(repo_root() / "tests" / "acceptance" / "j04_m0_client_worker.py"),
            *args,
        ]
        popen = subprocess.Popen(
            command,
            cwd=str(repo_root()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return self._register_process(popen, label=label)

    def stop_process(self, label: str, *, grace_seconds: float = 5.0) -> None:
        """Terminate and detach a single managed process by label."""
        remaining: list[ManagedProcess] = []
        for managed in self._processes:
            if managed.label == label:
                popen = managed.popen
                if popen.poll() is None:
                    popen.terminate()
                    try:
                        popen.wait(timeout=grace_seconds)
                    except subprocess.TimeoutExpired:
                        popen.kill()
                        popen.wait(timeout=2.0)
                output = ""
                if popen.stdout is not None:
                    try:
                        output = popen.stdout.read() or ""
                    except Exception:  # noqa: BLE001
                        output = ""
                if output and self.log_dir is not None:
                    self.write_log(f"{managed.label}-{managed.pid}.log", output)
            else:
                remaining.append(managed)
        self._processes = remaining

    def cleanup(self, *, grace_seconds: float = 5.0) -> None:
        for managed in reversed(self._processes):
            popen = managed.popen
            if popen.poll() is not None:
                continue
            popen.terminate()
        deadline = time.monotonic() + grace_seconds
        for managed in self._processes:
            popen = managed.popen
            if popen.poll() is not None:
                continue
            remaining = max(0.0, deadline - time.monotonic())
            try:
                popen.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                popen.kill()
                popen.wait(timeout=2.0)
        for managed in self._processes:
            output = ""
            if managed.popen.stdout is not None:
                try:
                    output = managed.popen.stdout.read() or ""
                except Exception:  # noqa: BLE001
                    output = ""
            if output and self.log_dir is not None:
                self.write_log(f"{managed.label}-{managed.pid}.log", output)
        self._processes.clear()

    def __enter__(self) -> J04M0RealProcessHarness:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.cleanup()
