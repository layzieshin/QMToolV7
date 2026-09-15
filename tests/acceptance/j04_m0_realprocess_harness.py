"""Deterministic real-process orchestration for J04-M0 final acceptance (test-only).

Not a product entrypoint. Starts ``python -m src.backend`` on the canonical port,
tracks only self-spawned PIDs, and redacts logs written under ``build/j04-m0-closure/``.
"""
from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qm_platform.blob import is_host_running_marker_present

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


_READER_JOIN_TIMEOUT = 10.0  # seconds to wait for drain thread after process ends
_BACKEND_GRACEFUL_STOP_TIMEOUT = 15.0
_FALLBACK_KILL_TIMEOUT = 2.0
_MARKER_GONE_WAIT_SECONDS = 2.0


def backend_popen_creationflags() -> int:
    """Windows backend children need their own process group for CTRL_BREAK."""
    if sys.platform == "win32":
        return subprocess.CREATE_NEW_PROCESS_GROUP
    return 0


def send_graceful_stop_signal(popen: subprocess.Popen[str]) -> str:
    """Ask a graceful-stop child to take the ServiceHost.run_forever() interrupt path.

    Windows: CTRL_BREAK_EVENT (the child was started with CREATE_NEW_PROCESS_GROUP).
    POSIX: SIGINT.
    """
    if sys.platform == "win32":
        popen.send_signal(signal.CTRL_BREAK_EVENT)
        return "CTRL_BREAK_EVENT"
    popen.send_signal(signal.SIGINT)
    return "SIGINT"


BACKEND_SIGBREAK_STARTUP_DIRNAME = "backend-sigbreak-startup"

BACKEND_SIGBREAK_SITECUSTOMIZE = (
    '"""Test-only: map Windows SIGBREAK to KeyboardInterrupt before -m src.backend."""\n'
    "from __future__ import annotations\n"
    "\n"
    "import signal\n"
    "\n"
    "_sigbreak = getattr(signal, \"SIGBREAK\", None)\n"
    "if _sigbreak is not None:\n"
    "    try:\n"
    "        signal.signal(signal.SIGBREAK, signal.default_int_handler)\n"
    "    except Exception:\n"
    "        raise SystemExit(\"sitecustomize: SIGBREAK handler registration failed\") from None\n"
)


def write_backend_sigbreak_startup(workspace: Path) -> Path:
    """Write isolated sitecustomize.py under the harness workspace. No secrets."""
    startup = Path(workspace) / BACKEND_SIGBREAK_STARTUP_DIRNAME
    startup.mkdir(parents=True, exist_ok=True)
    (startup / "sitecustomize.py").write_text(BACKEND_SIGBREAK_SITECUSTOMIZE, encoding="utf-8")
    return startup


def prepend_pythonpath(existing: str, prefix: Path) -> str:
    """Put ``prefix`` first and keep remaining PYTHONPATH entries."""
    prefix_s = str(prefix)
    parts = [prefix_s]
    for item in (existing or "").split(os.pathsep):
        if item and item != prefix_s:
            parts.append(item)
    return os.pathsep.join(parts)


class _BackendStdoutDrainer:
    """Continuously reads a backend process's stdout PIPE into a redacted log file.

    Runs in a daemon thread so it never blocks the orchestration loop. Only used for
    backend processes; client workers keep their stdout for communicate()-based JSON reads.
    """

    def __init__(self, popen: subprocess.Popen[str], log_path: Path) -> None:
        self._popen = popen
        self._log_path = log_path
        self._lock = threading.Lock()
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            pipe = self._popen.stdout
            if pipe is None:
                return
            with self._log_path.open("w", encoding="utf-8") as handle:
                for line in pipe:
                    redacted = redact_log_text(line)
                    handle.write(redacted)
                    handle.flush()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._error = exc

    def join(self, timeout: float = _READER_JOIN_TIMEOUT) -> None:
        self._thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def get_error(self) -> Exception | None:
        with self._lock:
            return self._error


@dataclass
class ManagedProcess:
    pid: int
    popen: subprocess.Popen[str]
    label: str
    supports_graceful_stop: bool = False
    _drainer: _BackendStdoutDrainer | None = field(default=None, repr=False)
    _log_path: Path | None = field(default=None, repr=False)


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

    def _register_process(
        self,
        popen: subprocess.Popen[str],
        *,
        label: str,
        drainer: _BackendStdoutDrainer | None = None,
        log_path: Path | None = None,
        supports_graceful_stop: bool = False,
    ) -> ManagedProcess:
        if popen.pid is None:
            raise HarnessStartupError(f"{label} subprocess did not receive a PID")
        managed = ManagedProcess(
            pid=int(popen.pid),
            popen=popen,
            label=label,
            supports_graceful_stop=supports_graceful_stop,
            _drainer=drainer,
            _log_path=log_path,
        )
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
        if sys.platform == "win32":
            startup = write_backend_sigbreak_startup(self.workspace)
            env["PYTHONPATH"] = prepend_pythonpath(env.get("PYTHONPATH", ""), startup)
        command = [python_executable(), "-m", BACKEND_MODULE]
        popen_kwargs: dict[str, Any] = {
            "cwd": str(repo_root()),
            "env": env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
        }
        creationflags = backend_popen_creationflags()
        if creationflags:
            popen_kwargs["creationflags"] = creationflags
        popen = subprocess.Popen(command, **popen_kwargs)
        assert self.log_dir is not None
        if popen.pid is None:
            raise HarnessStartupError("backend subprocess did not receive a PID")
        log_path = self.log_dir / f"backend-{int(popen.pid)}.log"
        drainer = _BackendStdoutDrainer(popen, log_path)
        return self._register_process(
            popen,
            label="backend",
            drainer=drainer,
            log_path=log_path,
            supports_graceful_stop=True,
        )

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

    def _drain_and_log(self, managed: ManagedProcess) -> None:
        """Finalize process output handling.

        Backend processes already stream redacted stdout into their PID log via the
        drainer thread; here we only join that thread and surface timeout/read errors.
        Non-streamed processes still have their remaining stdout read here and written
        once into the PID-scoped log.
        """
        drainer = managed._drainer
        if drainer is not None:
            drainer.join(timeout=_READER_JOIN_TIMEOUT)
            if drainer.is_alive():
                if managed.popen.stdout is not None:
                    try:
                        managed.popen.stdout.close()
                    except Exception:  # noqa: BLE001
                        pass
                drainer.join(timeout=1.0)
            if drainer.is_alive():
                raise HarnessError(
                    f"backend stdout reader for pid={managed.pid} did not stop within timeout"
                )
            err = drainer.get_error()
            if err is not None:
                raise HarnessError(
                    f"backend stdout reader for pid={managed.pid} "
                    f"encountered an error: {type(err).__name__}"
                )
            return
        else:
            output = ""
            if managed.popen.stdout is not None:
                try:
                    output = managed.popen.stdout.read() or ""
                except Exception:  # noqa: BLE001
                    output = ""
            output = redact_log_text(output)
        if output and self.log_dir is not None:
            log_name = f"{managed.label}-{managed.pid}.log"
            path = self.log_dir / log_name
            path.write_text(output, encoding="utf-8")

    def _terminate_or_kill(self, popen: subprocess.Popen[str], *, grace_seconds: float) -> None:
        if popen.poll() is not None:
            return
        popen.terminate()
        try:
            popen.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            popen.kill()
            popen.wait(timeout=_FALLBACK_KILL_TIMEOUT)

    def _wait_until_marker_gone(self) -> bool:
        """Observe marker absence only. Never unlink or rmdir the marker."""
        if self.backend_home is None:
            return True
        deadline = time.monotonic() + _MARKER_GONE_WAIT_SECONDS
        while True:
            if not is_host_running_marker_present(app_home=self.backend_home):
                return True
            if time.monotonic() >= deadline:
                return not is_host_running_marker_present(app_home=self.backend_home)
            time.sleep(0.05)

    def _stop_graceful_backend(
        self,
        managed: ManagedProcess,
        *,
        grace_seconds: float,
        fail_closed_on_fallback: bool,
    ) -> None:
        popen = managed.popen
        fallback_used = False
        signal_name = "none"
        if popen.poll() is None:
            signal_name = send_graceful_stop_signal(popen)
            try:
                popen.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                pass
        if popen.poll() is None:
            fallback_used = True
            detail = (
                f"backend graceful stop fallback to terminate/kill after {signal_name} "
                f"pid={managed.pid}"
            )
            self.write_log("backend-graceful-stop-fallback.log", detail)
            self._terminate_or_kill(popen, grace_seconds=_FALLBACK_KILL_TIMEOUT)
        self._drain_and_log(managed)
        if not fail_closed_on_fallback:
            return
        if fallback_used:
            raise HarnessError(
                "backend graceful stop fallback to terminate/kill; "
                f"refusing restart pid={managed.pid}"
            )
        if popen.poll() is None:
            raise HarnessError(
                f"backend child still running after graceful stop; refusing restart pid={managed.pid}"
            )
        if not self._wait_until_marker_gone():
            raise HarnessError(
                "backend host running marker still present after graceful stop; "
                "refusing restart over stale marker"
            )

    def _stop_terminate_tracked(
        self,
        managed: ManagedProcess,
        *,
        grace_seconds: float,
    ) -> None:
        self._terminate_or_kill(managed.popen, grace_seconds=grace_seconds)
        self._drain_and_log(managed)

    def stop_process(self, label: str, *, grace_seconds: float | None = None) -> None:
        """Stop and detach a single managed process by label.

        Backend children started via ``start_backend`` use the graceful interrupt
        path. A restart must not treat terminate/kill fallback as success.
        """
        remaining: list[ManagedProcess] = []
        errors: list[HarnessError] = []
        for managed in self._processes:
            if managed.label != label:
                remaining.append(managed)
                continue
            try:
                if managed.supports_graceful_stop:
                    timeout = (
                        _BACKEND_GRACEFUL_STOP_TIMEOUT
                        if grace_seconds is None
                        else grace_seconds
                    )
                    self._stop_graceful_backend(
                        managed,
                        grace_seconds=timeout,
                        fail_closed_on_fallback=True,
                    )
                else:
                    timeout = 5.0 if grace_seconds is None else grace_seconds
                    self._stop_terminate_tracked(managed, grace_seconds=timeout)
            except HarnessError as exc:
                errors.append(exc)
        self._processes = remaining
        if errors:
            raise errors[0]

    def cleanup(self, *, grace_seconds: float = 5.0) -> None:
        errors: list[HarnessError] = []
        for managed in reversed(self._processes):
            try:
                if managed.supports_graceful_stop:
                    self._stop_graceful_backend(
                        managed,
                        grace_seconds=max(grace_seconds, _BACKEND_GRACEFUL_STOP_TIMEOUT),
                        fail_closed_on_fallback=False,
                    )
                else:
                    self._stop_terminate_tracked(managed, grace_seconds=grace_seconds)
            except HarnessError as exc:
                errors.append(exc)
        self._processes.clear()
        if errors:
            raise errors[0]

    def __enter__(self) -> J04M0RealProcessHarness:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.cleanup()
