"""Uninstalled backend service host (OPS00-A).

Local-process lifecycle (start/status/graceful stop) without Windows SCM registration.
Production profile validates TLS path configuration and writable ``QMTOOL_HOME`` before
serving; HTTPS termination is implemented in OPS00-B.
"""
from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import uvicorn

from qm_platform.runtime.paths import runtime_home, runtime_home_writable
from src.backend.api import create_app
from src.backend.bootstrap import BackendBootstrapError, build_backend_container

_PRODUCTION_PROFILES = frozenset({"prod", "production"})
_DEFAULT_BIND_HOST = "127.0.0.1"
_DEFAULT_BIND_PORT = 8000


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


def _resolve_tls_paths() -> tuple[str, str]:
    cert = os.environ.get("QMTOOL_TLS_CERT_FILE", "").strip()
    key = os.environ.get("QMTOOL_TLS_KEY_FILE", "").strip()
    return cert, key


def validate_service_host_config() -> None:
    """Fail-closed host configuration checks before serving requests."""
    if not runtime_home_writable():
        raise BackendBootstrapError(
            f"QMTOOL_HOME ({runtime_home()}) is missing or not writable for the backend host"
        )

    if not is_production_profile():
        return

    cert_path, key_path = _resolve_tls_paths()
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

    from pathlib import Path

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

    def status(self) -> ServiceHostStatus:
        with self._lock:
            state = self._state
            bind_host = self._bind_host
            bind_port = self._bind_port
        return ServiceHostStatus(
            state=state,
            bind_host=bind_host,
            bind_port=bind_port,
            production_profile=is_production_profile(),
        )

    def start(self, *, timeout: float = 30.0) -> None:
        with self._lock:
            if self._state in {ServiceHostState.STARTING, ServiceHostState.RUNNING}:
                raise RuntimeError("service host is already running or starting")
            self._bind_host = resolve_bind_host()
            self._bind_port = resolve_bind_port()
            self._state = ServiceHostState.STARTING

        try:
            validate_service_host_config()
            container = build_backend_container()
            if is_production_profile():
                raise BackendBootstrapError(
                    "production profile refuses HTTP-only bind before serving; "
                    "HTTPS termination is implemented in OPS00-B"
                )
            app = create_app(container)
        except Exception:
            with self._lock:
                self._state = ServiceHostState.STOPPED
            raise

        config = uvicorn.Config(
            app,
            host=self._bind_host,
            port=self._bind_port,
            log_level=os.environ.get("QMTOOL_UVICORN_LOG_LEVEL", "info"),
            lifespan="auto",
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
        thread.start()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if server.started:
                with self._lock:
                    self._state = ServiceHostState.RUNNING
                return
            if not thread.is_alive():
                break
            time.sleep(0.05)

        self.stop(timeout=1.0)
        raise RuntimeError("service host failed to start within timeout")

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


def probe_health(bind_host: str, bind_port: int, *, timeout: float = 2.0) -> dict[str, Any]:
    """HTTP GET /health against a running host (test helper)."""
    import urllib.error
    import urllib.request

    url = f"http://{bind_host}:{bind_port}/health"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"health probe failed for {url}: {exc}") from exc
    import json

    return json.loads(body)
