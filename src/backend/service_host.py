"""Uninstalled backend service host (OPS00-A/B).

Local-process lifecycle (start/status/graceful stop) without Windows SCM registration.
Production profile validates TLS file PEMs and writable ``QMTOOL_HOME`` before serving
HTTPS via uvicorn. Non-production may continue to use loopback HTTP.
"""
from __future__ import annotations

import asyncio
import os
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import uvicorn

from qm_platform.runtime.paths import runtime_home, runtime_home_writable
from qm_platform.runtime.operation_lock import OperationLock, OperationLockError
from qm_platform.blob.backup_orchestrator import (
    BackupOrchestratorError,
    compute_app_release_fingerprint,
    create_host_running_marker_exclusive,
    is_host_running_marker_present,
    remove_host_running_marker,
)
from qm_platform.runtime.maintenance import (
    get_expected_release_fingerprint,
    is_rehearsal_in_progress,
)
from src.backend.api import create_app
from src.backend.bootstrap import BackendBootstrapError, build_backend_container
from src.backend.tls_config import load_tls_material, resolve_tls_paths

_PRODUCTION_PROFILES = frozenset({"prod", "production"})
_DEFAULT_BIND_HOST = "127.0.0.1"
_DEFAULT_BIND_PORT = 8000

_active_host_lock = threading.Lock()
_active_host: ServiceHost | None = None


def _register_active_host(host: ServiceHost) -> None:
    global _active_host
    with _active_host_lock:
        _active_host = host


def _clear_active_host(host: ServiceHost) -> None:
    global _active_host
    with _active_host_lock:
        if _active_host is host:
            _active_host = None


def drain_and_stop_active_host(*, timeout: float = 30.0) -> None:
    """Stop the in-process ServiceHost or fail closed when another process owns the marker."""
    with _active_host_lock:
        host = _active_host

    if host is not None:
        host.stop(timeout=timeout)
        return

    if is_host_running_marker_present():
        raise BackendBootstrapError(
            "backend host must be stopped so in-flight writes drain before update rehearsal; "
            "stop the running host process first"
        )


class ServiceHostState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass(frozen=True)
class ServiceHostStatus:
    state: ServiceHostState
    bind_host: str
    bind_port: int
    production_profile: bool
    https_enabled: bool


def is_production_profile() -> bool:
    return os.environ.get("QMTOOL_RUNTIME_PROFILE", "").strip().lower() in _PRODUCTION_PROFILES


def resolve_bind_host() -> str:
    configured = os.environ.get("QMTOOL_BIND_HOST", _DEFAULT_BIND_HOST).strip()
    return configured or _DEFAULT_BIND_HOST


def resolve_bind_port() -> int:
    raw = os.environ.get("QMTOOL_BIND_PORT", str(_DEFAULT_BIND_PORT)).strip() or str(
        _DEFAULT_BIND_PORT
    )
    try:
        port = int(raw)
    except ValueError as exc:
        raise BackendBootstrapError(f"QMTOOL_BIND_PORT must be an integer, got {raw!r}") from exc
    if port < 1 or port > 65535:
        raise BackendBootstrapError(f"QMTOOL_BIND_PORT out of range: {port}")
    return port


def validate_rehearsal_release_fingerprint(app_home: Path | None = None) -> None:
    """Fail closed when release identity mismatches abort-restored expectation."""
    home = app_home if app_home is not None else runtime_home()
    if is_rehearsal_in_progress(home):
        raise BackendBootstrapError(
            "backend host cannot start while update rehearsal candidate is staged without abort"
        )
    expected = get_expected_release_fingerprint(home)
    if expected is None:
        return
    try:
        current = compute_app_release_fingerprint(home)
    except BackupOrchestratorError as exc:
        raise BackendBootstrapError(
            "backend host cannot start without a valid release identity file"
        ) from exc
    if current != expected:
        raise BackendBootstrapError(
            "backend host cannot start: release fingerprint does not match abort-restored expectation"
        )


def validate_service_host_config() -> None:
    """Fail-closed host configuration checks before serving requests."""
    if not runtime_home_writable():
        raise BackendBootstrapError(
            f"QMTOOL_HOME ({runtime_home()}) is missing or not writable for the backend host"
        )

    if not is_production_profile():
        return

    cert_path, key_path = resolve_tls_paths()
    missing = [
        name
        for name, value in (
            ("QMTOOL_TLS_CERT_FILE", cert_path),
            ("QMTOOL_TLS_KEY_FILE", key_path),
        )
        if not value
    ]
    if missing:
        raise BackendBootstrapError(
            "production profile requires TLS certificate configuration; "
            f"set {', '.join(missing)} (insecure HTTP-only bind is rejected before serving)"
        )

    cert_file = Path(cert_path)
    key_file = Path(key_path)
    absent = [
        label
        for label, path in (("QMTOOL_TLS_CERT_FILE", cert_file), ("QMTOOL_TLS_KEY_FILE", key_file))
        if not path.is_file()
    ]
    if absent:
        raise BackendBootstrapError(
            "production profile requires readable TLS certificate files; "
            f"missing or unreadable: {', '.join(absent)}"
        )


class ServiceHost:
    """Thread-friendly uninstalled service host wrapping uvicorn."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = ServiceHostState.STOPPED
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bind_host = resolve_bind_host()
        self._bind_port = resolve_bind_port()
        self._https_enabled = False
        self._owns_host_running_marker = False

    def status(self) -> ServiceHostStatus:
        with self._lock:
            state = self._state
            bind_host = self._bind_host
            bind_port = self._bind_port
            https_enabled = self._https_enabled
        return ServiceHostStatus(
            state=state,
            bind_host=bind_host,
            bind_port=bind_port,
            production_profile=is_production_profile(),
            https_enabled=https_enabled,
        )

    def start(self, *, timeout: float = 30.0) -> None:
        operation_lock = OperationLock()
        try:
            operation_lock.acquire()
        except OperationLockError as exc:
            raise BackendBootstrapError(
                "backend host cannot start while exclusive operation lock is held"
            ) from exc

        try:
            with self._lock:
                if self._state in {ServiceHostState.STARTING, ServiceHostState.RUNNING}:
                    raise RuntimeError("service host is already running or starting")
                self._bind_host = resolve_bind_host()
                self._bind_port = resolve_bind_port()
                self._state = ServiceHostState.STARTING
                self._https_enabled = False

            if is_host_running_marker_present():
                with self._lock:
                    self._state = ServiceHostState.STOPPED
                    self._https_enabled = False
                raise BackendBootstrapError(
                    "backend host cannot start while host running marker is present"
                )

            ssl_certfile: str | None = None
            ssl_keyfile: str | None = None

            try:
                validate_service_host_config()
                validate_rehearsal_release_fingerprint()
                if is_production_profile():
                    tls_material = load_tls_material()
                    ssl_certfile = tls_material.cert_file
                    ssl_keyfile = tls_material.key_file
                container = build_backend_container()
                app = create_app(container)
            except Exception:
                with self._lock:
                    self._state = ServiceHostState.STOPPED
                    self._https_enabled = False
                raise

            config = uvicorn.Config(
                app,
                host=self._bind_host,
                port=self._bind_port,
                log_level=os.environ.get("QMTOOL_UVICORN_LOG_LEVEL", "warning"),
                lifespan="auto",
                ssl_certfile=ssl_certfile,
                ssl_keyfile=ssl_keyfile,
            )
            server = uvicorn.Server(config)

            def _serve() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._loop = loop
                try:
                    loop.run_until_complete(server.serve())
                finally:
                    loop.close()
                    self._loop = None

            thread = threading.Thread(target=_serve, name="qmtool-backend-host", daemon=True)
            with self._lock:
                self._server = server
                self._thread = thread
                self._https_enabled = ssl_certfile is not None and ssl_keyfile is not None
            thread.start()

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if server.started:
                    try:
                        create_host_running_marker_exclusive()
                    except BackupOrchestratorError as exc:
                        self.stop(timeout=1.0)
                        raise BackendBootstrapError(
                            "backend host cannot start while host running marker is present"
                        ) from exc
                    self._owns_host_running_marker = True
                    with self._lock:
                        self._state = ServiceHostState.RUNNING
                    _register_active_host(self)
                    return
                if not thread.is_alive():
                    break
                time.sleep(0.05)

            self.stop(timeout=1.0)
            raise RuntimeError("service host failed to start within timeout")
        finally:
            operation_lock.release()

    def stop(self, *, timeout: float = 30.0) -> None:
        with self._lock:
            if self._state == ServiceHostState.STOPPED:
                return
            self._state = ServiceHostState.STOPPING
            server = self._server
            thread = self._thread

        if server is not None:
            server.should_exit = True

        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                raise RuntimeError(
                    f"service host stop timed out after {timeout}s; serve thread still alive"
                )

        with self._lock:
            self._server = None
            self._thread = None
            self._state = ServiceHostState.STOPPED
            self._https_enabled = False
        if self._owns_host_running_marker:
            remove_host_running_marker()
            self._owns_host_running_marker = False
        _clear_active_host(self)

    def run_forever(self) -> None:
        """Operator entry: validate, start, and block until graceful shutdown."""
        self.start()
        try:
            while self.status().state == ServiceHostState.RUNNING:
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def is_serving(self) -> bool:
        with self._lock:
            state = self._state
            bind_host = self._bind_host
            bind_port = self._bind_port
            thread = self._thread

        if state == ServiceHostState.STARTING:
            return False
        if state == ServiceHostState.STOPPED:
            if thread is None or not thread.is_alive():
                return False

        try:
            with socket.create_connection((bind_host, bind_port), timeout=0.5):
                return True
        except OSError:
            return False


def probe_health(
    bind_host: str,
    bind_port: int,
    *,
    timeout: float = 2.0,
    use_https: bool = False,
    ssl_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    """GET /health against a running host (test helper)."""
    import json
    import urllib.error
    import urllib.request

    scheme = "https" if use_https else "http"
    url = f"{scheme}://{bind_host}:{bind_port}/health"
    request = urllib.request.Request(url, method="GET")
    context = ssl_context
    if use_https and context is None:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"health probe failed for {url}: {exc}") from exc

    return json.loads(body)


def probe_url(
    url: str,
    *,
    timeout: float = 2.0,
    ssl_context: ssl.SSLContext | None = None,
) -> tuple[int, bytes]:
    """GET an arbitrary URL (test helper for same-origin static fixtures)."""
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
            return response.status, response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET probe failed for {url}: {exc}") from exc
