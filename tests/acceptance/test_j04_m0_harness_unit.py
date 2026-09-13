"""Unit tests for the J04-M0 real-process harness (no full final acceptance run)."""
from __future__ import annotations

import io
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.acceptance.j04_m0_realprocess_harness import (
    BACKEND_MODULE,
    BACKEND_PORT,
    BACKEND_SIGBREAK_SITECUSTOMIZE,
    BACKEND_SIGBREAK_STARTUP_DIRNAME,
    FINAL_ACCEPTANCE_ENV,
    FINAL_ACCEPTANCE_OPT_IN,
    HarnessBlockedError,
    HarnessError,
    J04M0RealProcessHarness,
    _BackendStdoutDrainer,
    assert_backend_port_free,
    backend_popen_creationflags,
    is_port_free,
    prepend_pythonpath,
    redact_log_text,
    require_final_acceptance_opt_in,
    repo_root,
    write_backend_sigbreak_startup,
)


class _MockAuthHandler(BaseHTTPRequestHandler):
    tokens: dict[str, str] = {"bob": "token-bob", "alice": "token-alice"}

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        username = str(payload.get("username", ""))
        token = self.tokens.get(username, "")
        status = 200 if token else 401
        body = json.dumps({"token": token}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/api/v1/auth/me":
            self.send_response(404)
            self.end_headers()
            return
        auth = self.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        username = next((name for name, value in self.tokens.items() if value == token), "")
        if not username:
            self.send_response(401)
            self.end_headers()
            return
        body = json.dumps(
            {
                "user_id": f"uid-{username}",
                "username": username,
                "global_roles": ["USER"],
                "is_qmb": False,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def mock_auth_server() -> str:
    server = HTTPServer(("127.0.0.1", 0), _MockAuthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_redact_log_text_removes_tokens_and_dsns() -> None:
    raw = (
        'Bearer abc.def-123 {"token":"secret-token"} '
        "postgresql://user:pass@127.0.0.1:5432/db password=secret "
        "QMTOOL_PG_TEST_ADMIN_DSN=postgresql://admin:pw@127.0.0.1:55432/db"
    )
    redacted = redact_log_text(raw)
    assert "secret-token" not in redacted
    assert "abc.def-123" not in redacted
    assert "postgresql://user" not in redacted
    assert "password=secret" not in redacted
    assert "<redacted>" in redacted


def test_require_final_acceptance_opt_in_blocks_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FINAL_ACCEPTANCE_ENV, raising=False)
    with pytest.raises(HarnessBlockedError, match=FINAL_ACCEPTANCE_ENV):
        require_final_acceptance_opt_in()


def test_assert_backend_port_free_blocks_when_listener_bound() -> None:
    if not is_port_free(port=BACKEND_PORT):
        pytest.skip(f"port {BACKEND_PORT} already in use in this environment")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", BACKEND_PORT))
    sock.listen(1)
    try:
        with pytest.raises(HarnessBlockedError, match="already in use"):
            assert_backend_port_free()
    finally:
        sock.close()


def test_harness_backend_launch_uses_canonical_module(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen") as popen:
        mock_proc = MagicMock()
        mock_proc.pid = 4242
        mock_proc.stdout = None
        mock_proc.poll.return_value = None
        popen.return_value = mock_proc
        managed = harness.start_backend(extra_env={"QMTOOL_LICENSE_MODE": "dev"})
        assert managed.pid == 4242
        assert managed.supports_graceful_stop is True
        command = popen.call_args.args[0]
        assert command[-2:] == ["-m", BACKEND_MODULE]
        assert popen.call_args.kwargs["cwd"] == str(repo_root())
        assert popen.call_args.kwargs["env"]["QMTOOL_HOME"] == str(harness.backend_home)
        if sys.platform == "win32":
            assert popen.call_args.kwargs["creationflags"] == subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            assert "creationflags" not in popen.call_args.kwargs
    harness.cleanup()


def test_harness_cleanup_terminates_only_tracked_process(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws", log_dir=tmp_path / "logs")
    sleeper = subprocess.Popen(
        [sys.executable, "-c", "print('sleeping'); import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert sleeper.pid is not None
    harness._register_process(sleeper, label="sleeper")
    harness.cleanup()
    assert sleeper.poll() is not None


def test_harness_write_log_redacts_output(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    path = harness.write_log("sample.log", 'Bearer secret-token postgresql://u:p@h/d')
    text = path.read_text(encoding="utf-8")
    assert "secret-token" not in text
    assert "<redacted>" in text


def test_client_workers_use_separate_homes_and_sessions(
    tmp_path: Path,
    mock_auth_server: str,
) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws", backend_url=mock_auth_server)
    proc_a = harness.start_client_worker(
        home=harness.client1_home,
        args=["--action", "login", "--username", "bob", "--password", "bob-secret"],
        label="client-a",
    )
    proc_b = harness.start_client_worker(
        home=harness.client2_home,
        args=["--action", "login", "--username", "alice", "--password", "alice-secret"],
        label="client-b",
    )
    stdout_a = proc_a.popen.communicate(timeout=15)[0]
    stdout_b = proc_b.popen.communicate(timeout=15)[0]
    payload_a = json.loads(stdout_a)
    payload_b = json.loads(stdout_b)
    assert payload_a["ok"] is True
    assert payload_b["ok"] is True
    assert payload_a["home"] != payload_b["home"]
    assert payload_a["token_fingerprint"] != payload_b["token_fingerprint"]
    assert "token-bob" not in stdout_a
    harness.cleanup()


def test_harness_wait_for_health_succeeds_against_mock_server(
    tmp_path: Path,
    mock_auth_server: str,
) -> None:
    class _HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        harness = J04M0RealProcessHarness(
            workspace=tmp_path / "ws",
            backend_url=f"http://{host}:{port}",
        )
        result = harness.wait_for_health(timeout_seconds=5.0)
        assert result["status"] == 200
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# MR09-R3: stdout-Drain tests
# ---------------------------------------------------------------------------

# Size well above typical pipe buffer (64 KiB on Windows); 300 KiB ensures backpressure.
_LARGE_OUTPUT_BYTES = 300 * 1024
_SENTINEL = "DRAIN_SENTINEL_END_OF_OUTPUT"


def _make_large_output_script() -> str:
    """Return Python source that writes >256 KiB then the sentinel to stdout."""
    return (
        "import sys\n"
        f"sys.stdout.write('X' * {_LARGE_OUTPUT_BYTES})\n"
        f"sys.stdout.write('\\n{_SENTINEL}\\n')\n"
        "sys.stdout.flush()\n"
    )


def _wait_for_log_contains(path: Path, needle: str, *, timeout: float = 5.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if needle in content:
                return content
        time.sleep(0.05)
    pytest.fail(f"log did not contain expected text within timeout: {needle}")


def _register_backend_process(
    harness: J04M0RealProcessHarness,
    popen: subprocess.Popen[str],
) -> tuple[object, Path]:
    assert popen.pid is not None
    log_path = harness.log_dir / f"backend-{popen.pid}.log"
    drainer = _BackendStdoutDrainer(popen, log_path)
    managed = harness._register_process(
        popen,
        label="backend",
        drainer=drainer,
        log_path=log_path,
    )
    return managed, log_path


def test_backend_drain_handles_pipe_backpressure_without_blocking(tmp_path: Path) -> None:
    """Backend stdout drain must consume >256 KiB without blocking the process."""
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    script = _make_large_output_script()
    popen = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    managed, log_path = _register_backend_process(harness, popen)

    # Wait for the subprocess to finish; without a drain it would block indefinitely.
    try:
        popen.wait(timeout=15.0)
    except subprocess.TimeoutExpired:
        popen.kill()
        popen.wait()
        pytest.fail(
            "subprocess blocked: stdout PIPE not drained (pipe backpressure not resolved)"
        )

    harness.cleanup()

    assert log_path.exists(), "backend log was not written"
    content = log_path.read_text(encoding="utf-8")
    assert _SENTINEL in content, "sentinel not found in drained log"
    assert len(content) >= _LARGE_OUTPUT_BYTES, (
        f"log too short: expected >={_LARGE_OUTPUT_BYTES}, got {len(content)}"
    )


def test_backend_drain_without_reader_blocks_on_large_output() -> None:
    """Control: reading stdout only at cleanup (no drainer) must not complete in time.

    This confirms the test above is a meaningful regression guard: without continuous
    draining, a large write to a PIPE causes the subprocess to block.
    """
    script = _make_large_output_script()
    popen = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    blocked = False
    try:
        popen.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        blocked = True
    finally:
        popen.kill()
        popen.wait()
        # Drain the pipe so the OS releases resources, but discard contents.
        try:
            popen.stdout.read()  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass

    assert blocked, (
        "subprocess finished without blocking even without a drain — "
        "pipe buffer may be unusually large on this system; test assumption violated"
    )


def test_backend_drain_redacts_secrets_in_log(tmp_path: Path) -> None:
    """Output written by the backend is stored redacted; raw secrets must not appear."""
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    secret_bearer = "Bearer super-secret-token-abc123"
    secret_dsn = "postgresql://admin:hunter2@127.0.0.1:5432/mydb"
    secret_pw = "password=topsecret"
    script = (
        "import sys\n"
        f"sys.stdout.write({secret_bearer!r} + '\\n')\n"
        f"sys.stdout.write({secret_dsn!r} + '\\n')\n"
        f"sys.stdout.write({secret_pw!r} + '\\n')\n"
        "sys.stdout.flush()\n"
    )
    popen = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    managed, log_path = _register_backend_process(harness, popen)
    content_during_run = _wait_for_log_contains(log_path, "<redacted>")
    popen.wait(timeout=10.0)
    harness.cleanup()

    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "super-secret-token-abc123" not in content_during_run
    assert "hunter2" not in content_during_run
    assert "topsecret" not in content_during_run

    assert "super-secret-token-abc123" not in content
    assert "hunter2" not in content
    assert "topsecret" not in content
    assert "<redacted>" in content


def test_client_worker_stdout_not_consumed_by_drainer(tmp_path: Path) -> None:
    """Client worker processes must NOT be given a drainer; their stdout must remain
    available for communicate()-based JSON reads."""
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    payload = '{"ok": true, "value": 42}'
    script = f"import sys; sys.stdout.write({payload!r}); sys.stdout.flush()"
    popen = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Register WITHOUT drainer — exactly as start_client_worker does.
    managed = harness._register_process(popen, label="client-worker", drainer=None)
    assert managed._drainer is None, "client worker must not have a drainer"

    stdout_data, _ = popen.communicate(timeout=10.0)
    assert stdout_data == payload

    harness.cleanup()


def test_backend_drain_stop_and_cleanup_no_leaks(tmp_path: Path) -> None:
    """stop_process joins the reader; no thread remains alive after cleanup."""
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    popen = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdout.write('hello\\n'); sys.stdout.flush()"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    managed, _log_path = _register_backend_process(harness, popen)
    popen.wait(timeout=10.0)

    harness.stop_process("backend")

    assert managed._drainer is not None
    assert not managed._drainer.is_alive(), "reader thread still alive after stop_process"
    assert harness._processes == [], "process list not cleared after stop_process"

    # A second cleanup must be a no-op (no double-read or crash).
    harness.cleanup()


def test_backend_restart_separate_logs_no_old_reader_leak(tmp_path: Path) -> None:
    """Two sequential backend starts produce separate logs; first reader is dead before second."""
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")

    def _start_echo(message: str) -> tuple[subprocess.Popen[str], object, Path]:
        script = (
            f"import sys; sys.stdout.write({(message + chr(10))!r}); sys.stdout.flush()"
        )
        popen = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        managed, log_path = _register_backend_process(harness, popen)
        return popen, managed, log_path

    popen1, managed1, log1 = _start_echo("FIRST_BACKEND_OUTPUT")
    popen1.wait(timeout=10.0)
    pid1 = managed1.pid

    harness.stop_process("backend")
    assert managed1._drainer is not None
    assert not managed1._drainer.is_alive(), "first reader still alive after stop"

    popen2, managed2, log2 = _start_echo("SECOND_BACKEND_OUTPUT")
    popen2.wait(timeout=10.0)
    pid2 = managed2.pid

    harness.cleanup()
    assert managed2._drainer is not None
    assert not managed2._drainer.is_alive(), "second reader still alive after cleanup"

    assert log1.exists(), "log for first backend missing"
    assert log2.exists(), "log for second backend missing"
    assert "FIRST_BACKEND_OUTPUT" in log1.read_text(encoding="utf-8")
    assert "SECOND_BACKEND_OUTPUT" in log2.read_text(encoding="utf-8")
    assert "SECOND_BACKEND_OUTPUT" not in log1.read_text(encoding="utf-8")


def test_backend_drain_live_log_visibility_while_process_runs(tmp_path: Path) -> None:
    """Evidence must be visible before process exit, not only after cleanup."""
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    script = (
        "import sys, time\n"
        "sys.stdout.write('READY_SENTINEL\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(1.5)\n"
        "sys.stdout.write('END_SENTINEL\\n')\n"
        "sys.stdout.flush()\n"
    )
    popen = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _managed, log_path = _register_backend_process(harness, popen)

    content_while_running = _wait_for_log_contains(log_path, "READY_SENTINEL")
    assert "READY_SENTINEL" in content_while_running
    assert popen.poll() is None, "process already exited; did not prove live persistence"

    popen.wait(timeout=10.0)
    harness.cleanup()
    final_content = log_path.read_text(encoding="utf-8")
    assert "END_SENTINEL" in final_content


def test_backend_drain_join_timeout_raises_harness_error(tmp_path: Path) -> None:
    """A still-alive reader after join timeout must fail cleanup/stop, not pass silently."""
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")

    class _HungDrainer:
        def join(self, timeout: float = 10.0) -> None:
            return

        def is_alive(self) -> bool:
            return True

        def get_error(self) -> Exception | None:
            return None

    popen = subprocess.Popen(
        [sys.executable, "-c", "print('done')"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    popen.wait(timeout=10.0)
    managed = harness._register_process(
        popen,
        label="backend",
        drainer=_HungDrainer(),  # type: ignore[arg-type]
        log_path=harness.log_dir / f"backend-{popen.pid}.log",
    )

    with pytest.raises(HarnessError, match="did not stop within timeout"):
        harness.cleanup()
    assert harness._processes == []
    assert managed.popen.poll() is not None


def test_backend_drain_reader_error_surfaces_via_cleanup(tmp_path: Path) -> None:
    """A drainer read error must surface through cleanup() after best-effort cleanup."""
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")

    # Build a mock popen whose stdout raises on read.
    mock_stdout = MagicMock(spec=io.TextIOWrapper)
    mock_stdout.__iter__ = MagicMock(side_effect=OSError("simulated pipe read error"))

    mock_popen = MagicMock(spec=subprocess.Popen)
    mock_popen.pid = 99999
    mock_popen.stdout = mock_stdout
    mock_popen.poll.return_value = 0

    drainer = _BackendStdoutDrainer(
        mock_popen,  # type: ignore[arg-type]
        harness.log_dir / "backend-99999.log",
    )
    drainer.join(timeout=5.0)  # let the thread finish with the error

    err = drainer.get_error()
    assert err is not None, "drainer did not capture the simulated read error"
    assert isinstance(err, OSError)

    managed = harness._register_process(
        mock_popen,  # type: ignore[arg-type]
        label="backend",
        drainer=drainer,
        log_path=harness.log_dir / "backend-99999.log",
    )
    mock_popen.poll.return_value = 0  # already exited

    other = subprocess.Popen(
        [sys.executable, "-c", "print('other process')"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    other.wait(timeout=10.0)
    harness._register_process(other, label="client-worker")

    with pytest.raises(HarnessError, match="OSError") as exc_info:
        harness.cleanup()

    msg = str(exc_info.value)
    assert "OSError" in msg
    assert "simulated pipe read error" not in msg
    assert harness._processes == []
    assert managed.popen.poll() is not None
    harness.cleanup()


def _mock_child(*, pid: int, exit_on_graceful_signal: bool) -> MagicMock:
    popen = MagicMock()
    popen.pid = pid
    popen.stdout = None
    state = {"live": True}
    signals: list[int] = []

    def poll() -> int | None:
        return None if state["live"] else 0

    def wait(timeout: float | None = None) -> int:
        if state["live"]:
            raise subprocess.TimeoutExpired(cmd="mock-backend", timeout=timeout or 0)
        return 0

    def send_signal(sig: int) -> None:
        signals.append(sig)
        if exit_on_graceful_signal:
            state["live"] = False

    def terminate() -> None:
        state["live"] = False
        popen.terminate_calls += 1

    def kill() -> None:
        state["live"] = False
        popen.kill_calls += 1

    popen.poll.side_effect = poll
    popen.wait.side_effect = wait
    popen.send_signal.side_effect = send_signal
    popen.terminate.side_effect = terminate
    popen.kill.side_effect = kill
    popen.signals = signals
    popen.terminate_calls = 0
    popen.kill_calls = 0
    popen._state = state
    return popen


def test_windows_backend_start_uses_new_process_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.acceptance.j04_m0_realprocess_harness as harness_mod

    monkeypatch.setattr(harness_mod.sys, "platform", "win32")
    monkeypatch.setattr(harness_mod.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen") as popen:
        popen.return_value = _mock_child(pid=11, exit_on_graceful_signal=True)
        managed = harness.start_backend()
        assert managed.supports_graceful_stop is True
        assert popen.call_args.kwargs["creationflags"] == 0x200
        assert backend_popen_creationflags() == 0x200
    harness.cleanup()


def test_posix_backend_start_omits_creationflags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.acceptance.j04_m0_realprocess_harness as harness_mod

    monkeypatch.setattr(harness_mod.sys, "platform", "linux")
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen") as popen:
        popen.return_value = _mock_child(pid=13, exit_on_graceful_signal=True)
        managed = harness.start_backend()
        assert managed.supports_graceful_stop is True
        assert "creationflags" not in popen.call_args.kwargs
    harness.cleanup()


def test_windows_backend_stop_sends_ctrl_break(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.acceptance.j04_m0_realprocess_harness as harness_mod

    monkeypatch.setattr(harness_mod.sys, "platform", "win32")
    monkeypatch.setattr(harness_mod.signal, "CTRL_BREAK_EVENT", 1, raising=False)
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    child = _mock_child(pid=21, exit_on_graceful_signal=True)
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen", return_value=child):
        harness.start_backend()
    harness.stop_process("backend")
    assert child.signals == [1]
    assert child.terminate_calls == 0
    assert harness._processes == []


def test_posix_backend_stop_sends_sigint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.acceptance.j04_m0_realprocess_harness as harness_mod

    monkeypatch.setattr(harness_mod.sys, "platform", "linux")
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    child = _mock_child(pid=22, exit_on_graceful_signal=True)
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen", return_value=child):
        harness.start_backend()
    harness.stop_process("backend")
    assert child.signals == [signal.SIGINT]
    assert child.terminate_calls == 0


def test_unflagged_worker_does_not_receive_backend_signal(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    child = _mock_child(pid=31, exit_on_graceful_signal=True)
    child._state["live"] = True
    managed = harness._register_process(child, label="backend")
    assert managed.supports_graceful_stop is False
    harness.stop_process("backend")
    assert child.signals == []
    assert child.terminate_calls == 1


def test_client_worker_start_has_no_graceful_stop(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    child = _mock_child(pid=32, exit_on_graceful_signal=True)
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen", return_value=child) as popen:
        managed = harness.start_client_worker(
            home=harness.client1_home,
            args=["--action", "login", "--username", "bob", "--password", "x"],
            label="client-a",
        )
        assert managed.supports_graceful_stop is False
        assert "creationflags" not in popen.call_args.kwargs
    harness.stop_process("client-a")
    assert child.signals == []
    assert child.terminate_calls == 1


def test_graceful_stop_waits_and_joins_drainer(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    child = _mock_child(pid=41, exit_on_graceful_signal=True)
    joined: list[float] = []

    class _Drainer:
        def join(self, timeout: float = 10.0) -> None:
            joined.append(timeout)

        def is_alive(self) -> bool:
            return False

        def get_error(self) -> Exception | None:
            return None

    harness._register_process(
        child,
        label="backend",
        drainer=_Drainer(),  # type: ignore[arg-type]
        supports_graceful_stop=True,
    )
    harness.stop_process("backend")
    assert joined
    assert child.signals
    assert not child._state["live"]


def test_restart_requires_exit_and_removed_marker(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    first = _mock_child(pid=51, exit_on_graceful_signal=True)
    second = _mock_child(pid=52, exit_on_graceful_signal=True)
    with patch(
        "tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen",
        side_effect=[first, second],
    ):
        harness.start_backend()
        harness.stop_process("backend")
        assert first.signals
        assert first.terminate_calls == 0
        harness.start_backend()
        assert second.pid == 52
        assert harness._processes[-1].supports_graceful_stop is True
    harness.cleanup()


def test_harness_does_not_delete_host_running_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.acceptance.j04_m0_realprocess_harness as harness_mod

    monkeypatch.setattr(harness_mod, "_MARKER_GONE_WAIT_SECONDS", 0)
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    child = _mock_child(pid=61, exit_on_graceful_signal=True)
    marker = harness.backend_home / "storage" / "platform" / "host-running.pid"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.mkdir()
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen", return_value=child):
        harness.start_backend()
    with pytest.raises(HarnessError, match="stale marker"):
        harness.stop_process("backend")
    assert marker.exists()
    assert list(marker.iterdir()) == []


def test_restart_fallback_is_fail_closed(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    child = _mock_child(pid=71, exit_on_graceful_signal=False)
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen", return_value=child):
        harness.start_backend()
    with pytest.raises(HarnessError, match="fallback to terminate/kill"):
        harness.stop_process("backend", grace_seconds=0.01)
    assert child.terminate_calls == 1
    fallback_log = harness.log_dir / "backend-graceful-stop-fallback.log"
    assert fallback_log.is_file()
    assert "fallback to terminate/kill" in fallback_log.read_text(encoding="utf-8")
    assert harness._processes == []


def test_cleanup_uses_graceful_path_for_backend_child(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    child = _mock_child(pid=81, exit_on_graceful_signal=True)
    worker = _mock_child(pid=82, exit_on_graceful_signal=True)
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen", return_value=child):
        harness.start_backend()
    harness._register_process(worker, label="client-a")
    harness.cleanup()
    assert child.signals
    assert child.terminate_calls == 0
    assert worker.signals == []
    assert worker.terminate_calls == 1
    assert harness._processes == []


def test_windows_backend_command_stays_module_and_gets_sitecustomize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tests.acceptance.j04_m0_realprocess_harness as harness_mod

    monkeypatch.setattr(harness_mod.sys, "platform", "win32")
    monkeypatch.setattr(harness_mod.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    other = tmp_path / "other-path"
    more = tmp_path / "more-path"
    extra_pythonpath = os.pathsep.join((str(other), str(more)))
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen") as popen:
        popen.return_value = _mock_child(pid=91, exit_on_graceful_signal=True)
        managed = harness.start_backend(extra_env={"PYTHONPATH": extra_pythonpath})
        command = popen.call_args.args[0]
        assert command == [sys.executable, "-m", BACKEND_MODULE] or command[-2:] == [
            "-m",
            BACKEND_MODULE,
        ]
        env = popen.call_args.kwargs["env"]
        parts = env["PYTHONPATH"].split(os.pathsep)
        startup = harness.workspace / BACKEND_SIGBREAK_STARTUP_DIRNAME
        assert parts[0] == str(startup)
        assert str(other) in parts
        assert str(more) in parts
        sitecustomize = startup / "sitecustomize.py"
        assert sitecustomize.is_file()
        text = sitecustomize.read_text(encoding="utf-8")
        assert text == BACKEND_SIGBREAK_SITECUSTOMIZE
        assert "getattr(signal, \"SIGBREAK\", None)" in text
        assert "signal.default_int_handler" in text
        assert "postgresql://" not in text
        assert managed.supports_graceful_stop is True
    harness.cleanup()


def test_posix_backend_does_not_inject_sitecustomize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tests.acceptance.j04_m0_realprocess_harness as harness_mod

    monkeypatch.setattr(harness_mod.sys, "platform", "linux")
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen") as popen:
        popen.return_value = _mock_child(pid=92, exit_on_graceful_signal=True)
        harness.start_backend()
        env = popen.call_args.kwargs["env"]
        assert BACKEND_SIGBREAK_STARTUP_DIRNAME not in env.get("PYTHONPATH", "")
        assert not (harness.workspace / BACKEND_SIGBREAK_STARTUP_DIRNAME).exists()
        assert popen.call_args.args[0][-2:] == ["-m", BACKEND_MODULE]
    harness.cleanup()


def test_client_worker_pythonpath_excludes_sigbreak_startup(tmp_path: Path) -> None:
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    child = _mock_child(pid=93, exit_on_graceful_signal=True)
    with patch("tests.acceptance.j04_m0_realprocess_harness.subprocess.Popen", return_value=child) as popen:
        harness.start_client_worker(
            home=harness.client1_home,
            args=["--action", "login", "--username", "bob", "--password", "x"],
            label="client-a",
        )
        env = popen.call_args.kwargs["env"]
        assert BACKEND_SIGBREAK_STARTUP_DIRNAME not in env.get("PYTHONPATH", "")
    harness.stop_process("client-a")


def test_prepend_pythonpath_keeps_existing_entries(tmp_path: Path) -> None:
    prefix = tmp_path / "startup"
    result = prepend_pythonpath(os.pathsep.join(("keep-a", "keep-b")), prefix)
    parts = result.split(os.pathsep)
    assert parts == [str(prefix), "keep-a", "keep-b"]


def test_write_backend_sigbreak_startup_is_platform_neutral_without_sigbreak(tmp_path: Path) -> None:
    startup = write_backend_sigbreak_startup(tmp_path)
    text = (startup / "sitecustomize.py").read_text(encoding="utf-8")
    assert "getattr(signal, \"SIGBREAK\", None)" in text
    assert "host-running.pid" not in text


@pytest.mark.skipif(sys.platform != "win32", reason="CTRL_BREAK sitecustomize proof is Windows-only")
def test_windows_sigbreak_sitecustomize_runs_python_finally(tmp_path: Path) -> None:
    """Real Windows child: sitecustomize registers SIGBREAK; script itself must not."""
    harness = J04M0RealProcessHarness(workspace=tmp_path / "ws")
    startup = write_backend_sigbreak_startup(harness.workspace)
    ready = tmp_path / "ready.txt"
    sentinel = tmp_path / "finally.txt"
    child_script = tmp_path / "sigbreak_child.py"
    child_source = (
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n"
        "ready_path = Path(sys.argv[1])\n"
        "sentinel_path = Path(sys.argv[2])\n"
        "ready_path.write_text('ready\\n', encoding='utf-8')\n"
        "try:\n"
        "    deadline = time.monotonic() + 20.0\n"
        "    while time.monotonic() < deadline:\n"
        "        time.sleep(0.2)\n"
        "finally:\n"
        "    sentinel_path.write_text('finally\\n', encoding='utf-8')\n"
    )
    assert "SIGBREAK" not in child_source
    assert "signal.signal" not in child_source
    child_script.write_text(child_source, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(startup)
    popen = subprocess.Popen(
        [sys.executable, str(child_script), str(ready), str(sentinel)],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if ready.is_file():
                break
            time.sleep(0.05)
        else:
            raise AssertionError("child did not write ready signal")
        popen.send_signal(signal.CTRL_BREAK_EVENT)
        try:
            popen.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            popen.kill()
            popen.wait(timeout=2.0)
            raise AssertionError("child did not exit after CTRL_BREAK_EVENT")
        assert sentinel.is_file(), "Python finally did not run"
        assert sentinel.read_text(encoding="utf-8").strip() == "finally"
    finally:
        if popen.poll() is None:
            popen.kill()
            popen.wait(timeout=2.0)
        ready.unlink(missing_ok=True)
        sentinel.unlink(missing_ok=True)
        child_script.unlink(missing_ok=True)
