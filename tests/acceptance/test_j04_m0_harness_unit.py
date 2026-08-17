"""Unit tests for the J04-M0 real-process harness (no full final acceptance run)."""
from __future__ import annotations

import json
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
    FINAL_ACCEPTANCE_ENV,
    FINAL_ACCEPTANCE_OPT_IN,
    HarnessBlockedError,
    J04M0RealProcessHarness,
    assert_backend_port_free,
    is_port_free,
    redact_log_text,
    require_final_acceptance_opt_in,
    repo_root,
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
        if self.path != "/auth/me":
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
        command = popen.call_args.args[0]
        assert command[-2:] == ["-m", BACKEND_MODULE]
        assert popen.call_args.kwargs["cwd"] == str(repo_root())
        assert popen.call_args.kwargs["env"]["QMTOOL_HOME"] == str(harness.backend_home)
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
