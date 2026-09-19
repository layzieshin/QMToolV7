"""Unit tests for the WEB01 real-process harness (no Slot-2 live run)."""
from __future__ import annotations

import socket
from pathlib import Path

import pytest

from tests.acceptance.j04_m0_realprocess_harness import redact_log_text
from tests.acceptance.web01_realprocess_harness import (
    Web01HarnessBlockedError,
    Web01RealProcessHarness,
    allocate_web01_workspace,
    evidence_root,
    port_is_free,
    require_inside_web01_evidence,
    require_joint_opt_in,
)


def test_evidence_root_is_under_build_ap_029_web01() -> None:
    root = evidence_root().resolve()
    assert root.name == "ap-029-web01"
    assert root.parent.name == "build"


def test_require_inside_web01_evidence_rejects_foreign_path(tmp_path: Path) -> None:
    foreign = tmp_path / "outside"
    foreign.mkdir()
    with pytest.raises(Web01HarnessBlockedError):
        require_inside_web01_evidence(foreign)


def test_allocate_web01_workspace_creates_unique_directory() -> None:
    first = allocate_web01_workspace()
    second = allocate_web01_workspace()
    assert first != second
    assert first.is_dir()
    assert second.is_dir()


def test_port_is_free_reports_occupied_loopback_port() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = int(sock.getsockname()[1])
    try:
        assert port_is_free("127.0.0.1", port) is False
    finally:
        sock.close()


def test_require_joint_opt_in_blocks_without_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QMTOOL_WEB01_JOINT", raising=False)
    with pytest.raises(Web01HarnessBlockedError):
        require_joint_opt_in()


def test_harness_workspace_guard_on_construct(tmp_path: Path) -> None:
    with pytest.raises(Web01HarnessBlockedError):
        Web01RealProcessHarness(workspace=tmp_path / "outside")


def test_redact_log_text_strips_bearer_tokens() -> None:
    raw = 'Authorization: Bearer secret-token-123'
    assert "secret-token-123" not in redact_log_text(raw)
