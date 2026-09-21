"""Unit tests for the WEB01 real-process harness (no Slot-2 live run)."""
from __future__ import annotations

import inspect
import json
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from tests.acceptance.j04_m0_realprocess_harness import redact_log_text
from tests.acceptance.web01_realprocess_harness import (
    REPO_ROOT,
    _SubprocessOutputDrainer,
    HANDSHAKE_CONFLICT_STALE,
    HANDSHAKE_MAINTENANCE,
    HANDSHAKE_MAINTENANCE_EXIT,
    HANDSHAKE_PIS_ROLES,
    FINAL_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
    GRACEFUL_STOP_DIAGNOSIS_FILENAME,
    HANDSHAKE_RESTART,
    MAINTENANCE_COMPLETE_FILENAME,
    MAINTENANCE_EXIT_COMPLETE_FILENAME,
    MAINTENANCE_EXIT_REQUEST_FILENAME,
    MAINTENANCE_REQUEST_FILENAME,
    MANDATORY_SCREENSHOTS,
    MANDATORY_SCREENSHOT_DIMENSIONS,
    PIS_DOCUMENT_ID,
    PLAYWRIGHT_JSON_FILENAME,
    RESTART_COMPLETE_FILENAME,
    RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
    RESTART_REQUEST_FILENAME,
    WEB01_EDITOR_USERNAME,
    Web01HarnessBlockedError,
    Web01HarnessError,
    Web01HandshakeTracker,
    Web01RealProcessHarness,
    _MINIMAL_PNG,
    allocate_k1_visual_dir,
    allocate_k1_workspace,
    allocate_web01_workspace,
    copy_playwright_json_report,
    evidence_root,
    redact_json_text,
    redact_log_text_with_extras,
    is_blank_or_trivial_png,
    port_is_free,
    read_png_dimensions,
    require_inside_web01_evidence,
    require_clean_restart_stop_diagnosis,
    require_joint_opt_in,
    stop_backend_graceful,
    stop_owned_process,
    validate_png_screenshot,
    verify_visual_screenshots,
)


def _write_valid_png(path: Path, *, width: int, height: int, uniform: bool = False) -> None:
    img = Image.new("RGB", (width, height), (240, 240, 240))
    if not uniform:
        for x in range(0, width, max(1, width // 16)):
            for y in range(0, height, max(1, height // 16)):
                img.putpixel((x, y), (x % 255, y % 255, (x + y) % 255))
    img.save(path, format="PNG")


def _write_non_uniform_jpeg_bytes(path: Path, *, width: int, height: int) -> None:
    img = Image.new("RGB", (width, height), (240, 240, 240))
    for x in range(0, width, max(1, width // 16)):
        for y in range(0, height, max(1, height // 16)):
            img.putpixel((x, y), (x % 255, y % 255, (x + y) % 255))
    from io import BytesIO

    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    path.write_bytes(buffer.getvalue())


_CLEAN_STOP_DIAGNOSIS = {
    "fallback_used": False,
    "marker_present_after_exit": False,
    "child_returncode": 0,
}


def _populate_valid_visual_dir(visual: Path) -> None:
    visual.mkdir(parents=True, exist_ok=True)
    for name in MANDATORY_SCREENSHOTS:
        width, height = MANDATORY_SCREENSHOT_DIMENSIONS[name]
        _write_valid_png(visual / name, width=width, height=height)


def test_evidence_root_is_under_build_ap_029_web01() -> None:
    root = evidence_root().resolve()
    assert root.name == "ap-029-web01"
    assert root.parent.name == "build"


def test_require_inside_web01_evidence_rejects_foreign_path() -> None:
    foreign = REPO_ROOT / "build" / "pytest-foreign-web01-evidence"
    foreign.mkdir(parents=True, exist_ok=True)
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


def test_harness_workspace_guard_on_construct() -> None:
    foreign = REPO_ROOT / "build" / "pytest-foreign-web01-harness"
    foreign.mkdir(parents=True, exist_ok=True)
    with pytest.raises(Web01HarnessBlockedError):
        Web01RealProcessHarness(workspace=foreign)


def test_redact_log_text_strips_bearer_tokens() -> None:
    raw = "Authorization: Bearer secret-token-123"
    assert "secret-token-123" not in redact_log_text(raw)


def test_redact_log_text_with_extras_redacts_chunk_boundaries() -> None:
    secret = "chunk-secret-value"
    parts = ["prefix-", "chunk-sec", "ret-value suffix"]
    redacted = ""
    for part in parts:
        redacted = redact_log_text_with_extras(redacted + part, (secret,))
    assert secret not in redacted
    assert "<redacted>" in redacted


def test_subprocess_output_drainer_writes_redacted_log(tmp_path: Path) -> None:
    secret = "postgresql://user:leak@127.0.0.1/db"
    log_path = tmp_path / "backend-stdout.log"

    class _FakePipe:
        def __init__(self, chunks: list[str]) -> None:
            self._chunks = chunks

        def read(self, size: int) -> str:
            if not self._chunks:
                return ""
            return self._chunks.pop(0)

    drainer = _SubprocessOutputDrainer(
        _FakePipe([secret[:10], secret[10:] + "\n", "Bearer abc.def-123\n"]),
        log_path,
        extra_secrets=(secret,),
    )
    drainer.join()
    text = log_path.read_text(encoding="utf-8")
    assert secret not in text
    assert "abc.def-123" not in text
    assert "<redacted>" in text


def test_redact_json_text_preserves_valid_json_without_secrets() -> None:
    payload = redact_json_text(
        '{"dsn":"postgresql://user:secret@127.0.0.1/db","note":"Bearer abc.def-123"}',
        extra_secrets=("secret",),
    )
    parsed = json.loads(payload)
    assert parsed["dsn"] == "postgresql://<redacted>"
    assert parsed["note"] == "Bearer <redacted>"


def test_allocate_k1_workspace_uses_k1_checkpoint_segment() -> None:
    workspace = allocate_k1_workspace()
    assert "checkpoints" in workspace.parts
    assert "k1" in workspace.parts


def test_allocate_k1_visual_dir_uses_visual_segment() -> None:
    visual = allocate_k1_visual_dir()
    assert "visual" in visual.parts
    assert "k1" in visual.parts


def test_mandatory_screenshot_manifest_has_sixteen_entries() -> None:
    assert len(MANDATORY_SCREENSHOTS) == 16
    assert len(set(MANDATORY_SCREENSHOTS)) == 16
    assert "login-desktop.png" in MANDATORY_SCREENSHOTS
    assert "detail-desktop.png" in MANDATORY_SCREENSHOTS
    assert "viewer-desktop.png" in MANDATORY_SCREENSHOTS
    assert "maintenance-banner-desktop.png" in MANDATORY_SCREENSHOTS


def test_mandatory_screenshot_dimensions_cover_all_manifest_entries() -> None:
    assert set(MANDATORY_SCREENSHOT_DIMENSIONS) == set(MANDATORY_SCREENSHOTS)
    assert MANDATORY_SCREENSHOT_DIMENSIONS["login-stacked.png"] == (390, 844)
    assert MANDATORY_SCREENSHOT_DIMENSIONS["login-desktop.png"] == (1280, 800)


def test_read_png_dimensions_rejects_invalid_header(tmp_path: Path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not-a-png")
    with pytest.raises(Web01HarnessError, match="invalid or corrupt PNG"):
        read_png_dimensions(bad)


def test_validate_png_screenshot_accepts_real_decodable_png(tmp_path: Path) -> None:
    path = tmp_path / "valid.png"
    _write_valid_png(path, width=1280, height=800)
    width, height = validate_png_screenshot(path, expected_dimensions=(1280, 800))
    assert width == 1280
    assert height == 800


def test_validate_png_screenshot_rejects_jpeg_bytes_with_png_filename(tmp_path: Path) -> None:
    path = tmp_path / "login-desktop.png"
    _write_non_uniform_jpeg_bytes(path, width=1280, height=800)
    with pytest.raises(Web01HarnessError, match=r"is not PNG \(detected JPEG\)"):
        validate_png_screenshot(path, expected_dimensions=(1280, 800))


def test_validate_png_screenshot_rejects_truncated_png(tmp_path: Path) -> None:
    path = tmp_path / "truncated.png"
    _write_valid_png(path, width=64, height=64)
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    with pytest.raises(Web01HarnessError, match="invalid or corrupt PNG"):
        validate_png_screenshot(path)


def test_validate_png_screenshot_rejects_wrong_dimensions(tmp_path: Path) -> None:
    path = tmp_path / "wrong-size.png"
    _write_valid_png(path, width=800, height=600)
    with pytest.raises(Web01HarnessError, match="dimensions"):
        validate_png_screenshot(path, expected_dimensions=(1280, 800))


def test_validate_png_screenshot_rejects_uniform_large_png(tmp_path: Path) -> None:
    path = tmp_path / "uniform.png"
    _write_valid_png(path, width=1280, height=800, uniform=True)
    with pytest.raises(Web01HarnessError, match="blank or trivial"):
        validate_png_screenshot(path)


def test_validate_png_screenshot_accepts_non_trivial_png(tmp_path: Path) -> None:
    path = tmp_path / "nontrivial.png"
    _write_valid_png(path, width=390, height=844)
    assert validate_png_screenshot(path) == (390, 844)


def test_is_blank_or_trivial_png_detects_minimal_placeholder(tmp_path: Path) -> None:
    minimal_path = tmp_path / "minimal.png"
    minimal_path.write_bytes(_MINIMAL_PNG)
    assert is_blank_or_trivial_png(minimal_path) is True


def test_verify_visual_screenshots_reports_missing_files(tmp_path: Path) -> None:
    visual = tmp_path / "visual"
    visual.mkdir()
    _write_valid_png(visual / "login-desktop.png", width=1280, height=800)
    with pytest.raises(Web01HarnessError, match="missing mandatory"):
        verify_visual_screenshots(visual)


def test_verify_visual_screenshots_rejects_extra_files(tmp_path: Path) -> None:
    visual = tmp_path / "visual"
    _populate_valid_visual_dir(visual)
    (visual / "bonus-desktop.png").write_bytes(b"extra")
    with pytest.raises(Web01HarnessError, match="extra WEB01-K1 screenshots"):
        verify_visual_screenshots(visual)


def test_verify_visual_screenshots_rejects_wrong_dimensions(tmp_path: Path) -> None:
    visual = tmp_path / "visual"
    _populate_valid_visual_dir(visual)
    _write_valid_png(visual / "login-desktop.png", width=800, height=600)
    with pytest.raises(Web01HarnessError, match="dimensions"):
        verify_visual_screenshots(visual)


def test_verify_visual_screenshots_rejects_blank_files(tmp_path: Path) -> None:
    visual = tmp_path / "visual"
    _populate_valid_visual_dir(visual)
    _write_valid_png(visual / "viewer-desktop.png", width=1280, height=800, uniform=True)
    with pytest.raises(Web01HarnessError, match="blank or trivial"):
        verify_visual_screenshots(visual)


def test_verify_visual_screenshots_accepts_complete_valid_set(tmp_path: Path) -> None:
    visual = tmp_path / "visual"
    _populate_valid_visual_dir(visual)
    verified = verify_visual_screenshots(visual)
    assert len(verified) == 16
    assert [path.name for path in verified] == list(MANDATORY_SCREENSHOTS)


def test_copy_playwright_json_report_requires_source() -> None:
    workspace = allocate_k1_workspace()
    visual = workspace / "visual"
    visual.mkdir()
    with pytest.raises(Web01HarnessError, match="Playwright JSON reporter output is missing"):
        copy_playwright_json_report(workspace, visual)


def test_copy_playwright_json_report_copies_to_visual_dir() -> None:
    workspace = allocate_k1_workspace()
    visual = workspace / "visual"
    visual.mkdir()
    source = workspace / "browser-smoke-playwright.json"
    source.write_text(
        '{"token":"Bearer secret-token-123","password":"super-secret"}\n',
        encoding="utf-8",
    )
    destination = copy_playwright_json_report(
        workspace,
        visual,
        extra_secrets=("super-secret",),
    )
    assert destination == visual / PLAYWRIGHT_JSON_FILENAME
    assert destination.is_file()
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["token"] == "Bearer <redacted>"
    assert payload["password"] == "<redacted>"
    workspace_payload = json.loads(source.read_text(encoding="utf-8"))
    assert workspace_payload == payload
    assert "secret-token-123" not in destination.read_text(encoding="utf-8")
    assert "super-secret" not in source.read_text(encoding="utf-8")


def test_wait_for_restart_request_succeeds_when_marker_present() -> None:
    workspace = allocate_k1_workspace()
    (workspace / RESTART_REQUEST_FILENAME).write_text('{"phase":"restart"}\n', encoding="utf-8")
    harness = Web01RealProcessHarness(workspace=workspace)
    harness.wait_for_restart_request(timeout=1.0)


def test_wait_for_maintenance_request_times_out_without_marker() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    with pytest.raises(Web01HarnessError, match="timeout waiting for maintenance-request"):
        harness.wait_for_maintenance_request(timeout=0.2)


def test_write_restart_complete_and_maintenance_complete_markers() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace, bind_port=54321)
    harness.write_restart_complete()
    harness.enter_degraded_maintenance()
    restart = json.loads((workspace / RESTART_COMPLETE_FILENAME).read_text(encoding="utf-8"))
    maintenance = json.loads((workspace / MAINTENANCE_COMPLETE_FILENAME).read_text(encoding="utf-8"))
    assert restart["phase"] == "host-restarted"
    assert restart["port"] == 54321
    assert maintenance["phase"] == "maintenance-enabled"
    assert (workspace / MAINTENANCE_REQUEST_FILENAME).exists() is False


def test_maintenance_exit_handshake_filenames_are_explicit() -> None:
    assert MAINTENANCE_EXIT_REQUEST_FILENAME == "maintenance-exit-request.json"
    assert MAINTENANCE_EXIT_COMPLETE_FILENAME == "maintenance-exit-complete.json"
    assert HANDSHAKE_MAINTENANCE_EXIT == "maintenance_exit"


def test_wait_for_maintenance_exit_request_succeeds_when_marker_present() -> None:
    workspace = allocate_k1_workspace()
    (workspace / MAINTENANCE_EXIT_REQUEST_FILENAME).write_text(
        '{"phase":"maintenance-exit-request"}\n',
        encoding="utf-8",
    )
    harness = Web01RealProcessHarness(workspace=workspace)
    harness.wait_for_maintenance_exit_request(timeout=1.0)


def test_wait_for_maintenance_exit_request_times_out_without_marker() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    with pytest.raises(Web01HarnessError, match="timeout waiting for maintenance-exit-request"):
        harness.wait_for_maintenance_exit_request(timeout=0.2)


def test_complete_maintenance_exit_handshake_writes_completion_after_inactive_verification() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    with patch(
        "tests.acceptance.web01_realprocess_harness.exit_maintenance",
    ) as exit_mock, patch(
        "tests.acceptance.web01_realprocess_harness.is_maintenance_active",
        return_value=False,
    ) as active_mock:
        harness.complete_maintenance_exit_handshake()
    exit_mock.assert_called_once_with(harness.home)
    active_mock.assert_called_once_with(harness.home)
    payload = json.loads((workspace / MAINTENANCE_EXIT_COMPLETE_FILENAME).read_text(encoding="utf-8"))
    assert payload["phase"] == "maintenance-exited"


def test_complete_maintenance_exit_handshake_fails_when_maintenance_still_active() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    with patch(
        "tests.acceptance.web01_realprocess_harness.exit_maintenance",
    ), patch(
        "tests.acceptance.web01_realprocess_harness.is_maintenance_active",
        return_value=True,
    ):
        with pytest.raises(Web01HarnessError, match="maintenance flag still active"):
            harness.complete_maintenance_exit_handshake()
    assert (workspace / MAINTENANCE_EXIT_COMPLETE_FILENAME).exists() is False


def test_cleanup_removes_maintenance_flag_only_after_successful_stop() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    with patch("tests.acceptance.web01_realprocess_harness.stop_owned_process"), patch(
        "tests.acceptance.web01_realprocess_harness.exit_maintenance",
    ) as exit_mock:
        harness.cleanup()
    exit_mock.assert_called_once_with(harness.home)
    assert (workspace / MAINTENANCE_EXIT_COMPLETE_FILENAME).exists() is False
    assert (workspace / MAINTENANCE_COMPLETE_FILENAME).exists() is False


def test_cleanup_does_not_remove_maintenance_when_backend_stop_raises() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness.backend = SimpleNamespace()
    with patch(
        "tests.acceptance.web01_realprocess_harness.stop_backend_graceful",
        side_effect=Web01HarnessError("stop failed"),
    ), patch(
        "tests.acceptance.web01_realprocess_harness.exit_maintenance",
    ) as exit_mock:
        with pytest.raises(Web01HarnessError, match="stop failed"):
            harness.cleanup()
    exit_mock.assert_not_called()
    assert (workspace / MAINTENANCE_EXIT_COMPLETE_FILENAME).exists() is False


def test_handshake_tracker_maintenance_exit_exactly_once(tmp_path: Path) -> None:
    tracker = Web01HandshakeTracker()
    marker = tmp_path / MAINTENANCE_EXIT_REQUEST_FILENAME
    marker.write_text("{}", encoding="utf-8")
    calls = 0

    def handler() -> None:
        nonlocal calls
        calls += 1

    assert tracker.try_process(HANDSHAKE_MAINTENANCE_EXIT, marker_path=marker, handler=handler) is True
    assert tracker.try_process(HANDSHAKE_MAINTENANCE_EXIT, marker_path=marker, handler=handler) is False
    assert calls == 1
    assert tracker.is_complete(HANDSHAKE_MAINTENANCE_EXIT)


def test_handshake_tracker_maintenance_exit_not_complete_after_handler_failure(tmp_path: Path) -> None:
    tracker = Web01HandshakeTracker()
    marker = tmp_path / MAINTENANCE_EXIT_REQUEST_FILENAME
    marker.write_text("{}", encoding="utf-8")

    def failing_handler() -> None:
        raise RuntimeError("exit refused")

    with pytest.raises(RuntimeError, match="exit refused"):
        tracker.try_process(HANDSHAKE_MAINTENANCE_EXIT, marker_path=marker, handler=failing_handler)
    assert tracker.is_complete(HANDSHAKE_MAINTENANCE_EXIT) is False


def test_wait_playwright_timeout_terminates_child() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)

    class _HungProcess:
        pid = 4242

        def __init__(self) -> None:
            self._poll: int | None = None
            self.wait_calls = 0

        def poll(self) -> int | None:
            return self._poll

        def wait(self, timeout: float | None = None) -> int:
            self.wait_calls += 1
            raise subprocess.TimeoutExpired(cmd="playwright", timeout=timeout or 0)

    hung = _HungProcess()
    harness.playwright = hung  # type: ignore[assignment]
    with patch("tests.acceptance.web01_realprocess_harness.stop_owned_process") as stop_mock:
        with pytest.raises(Web01HarnessError, match="timeout waiting for Playwright"):
            harness.wait_playwright(timeout=0.01)
        stop_mock.assert_called_once_with(hung)
    assert harness.playwright is None


def test_wait_playwright_timeout_preserves_reference_when_stop_fails() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)

    class _HungProcess:
        pid = 5151

        def poll(self) -> int | None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired(cmd="playwright", timeout=timeout or 0)

    hung = _HungProcess()
    harness.playwright = hung  # type: ignore[assignment]
    with patch(
        "tests.acceptance.web01_realprocess_harness.stop_owned_process",
        side_effect=Web01HarnessError("taskkill failed"),
    ):
        with pytest.raises(Web01HarnessError, match="forced stop failed"):
            harness.wait_playwright(timeout=0.01)
    assert harness.playwright is hung


def test_stop_owned_process_taskkill_nonzero_raises_and_keeps_reference() -> None:
    class _AliveProcess:
        pid = 6060

        def poll(self) -> int | None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout or 0)

    proc = _AliveProcess()
    with patch.object(subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="denied")):
        with patch("tests.acceptance.web01_realprocess_harness.sys.platform", "win32"):
            with pytest.raises(Web01HarnessError, match="taskkill failed"):
                stop_owned_process(proc)  # type: ignore[arg-type]
    assert proc.poll() is None


def test_stop_owned_process_success_clears_child_on_windows() -> None:
    class _StoppedProcess:
        pid = 7070
        _exit: int | None = None

        def poll(self) -> int | None:
            return self._exit

        def wait(self, timeout: float | None = None) -> int:
            self._exit = 0
            return 0

    proc = _StoppedProcess()
    with patch.object(
        subprocess,
        "run",
        return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
    ):
        with patch("tests.acceptance.web01_realprocess_harness.sys.platform", "win32"):
            stop_owned_process(proc)  # type: ignore[arg-type]
    assert proc.poll() == 0


def test_handshake_tracker_invokes_handler_once_per_type(tmp_path: Path) -> None:
    tracker = Web01HandshakeTracker()
    marker = tmp_path / "marker.json"
    calls = 0

    def handler() -> None:
        nonlocal calls
        calls += 1

    marker.write_text("{}", encoding="utf-8")
    assert tracker.try_process(HANDSHAKE_PIS_ROLES, marker_path=marker, handler=handler) is True
    assert tracker.try_process(HANDSHAKE_PIS_ROLES, marker_path=marker, handler=handler) is False
    assert calls == 1
    assert tracker.is_complete(HANDSHAKE_PIS_ROLES)


def test_handshake_tracker_allows_retry_after_handler_failure(tmp_path: Path) -> None:
    tracker = Web01HandshakeTracker()
    marker = tmp_path / "marker.json"
    marker.write_text("{}", encoding="utf-8")
    attempts = 0

    def flaky_handler() -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("transient")

    with pytest.raises(RuntimeError, match="transient"):
        tracker.try_process(HANDSHAKE_MAINTENANCE, marker_path=marker, handler=flaky_handler)
    assert tracker.is_complete(HANDSHAKE_MAINTENANCE) is False
    assert tracker.try_process(HANDSHAKE_MAINTENANCE, marker_path=marker, handler=flaky_handler) is True
    assert attempts == 2
    assert tracker.is_complete(HANDSHAKE_MAINTENANCE)


@pytest.mark.parametrize(
    ("handshake_id", "filename"),
    [
        (HANDSHAKE_PIS_ROLES, "pis-marker.json"),
        (HANDSHAKE_CONFLICT_STALE, "conflict-marker.json"),
        (HANDSHAKE_MAINTENANCE, "maintenance-marker.json"),
        (HANDSHAKE_MAINTENANCE_EXIT, "maintenance-exit-marker.json"),
        (HANDSHAKE_RESTART, "restart-marker.json"),
    ],
)
def test_handshake_tracker_each_type_exactly_once(
    tmp_path: Path,
    handshake_id: str,
    filename: str,
) -> None:
    tracker = Web01HandshakeTracker()
    marker = tmp_path / filename
    marker.write_text("{}", encoding="utf-8")
    calls = 0

    def handler() -> None:
        nonlocal calls
        calls += 1

    assert tracker.try_process(handshake_id, marker_path=marker, handler=handler) is True
    assert tracker.try_process(handshake_id, marker_path=marker, handler=handler) is False
    assert calls == 1


def test_wait_playwright_nonzero_exit_is_fail_closed() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness.playwright = SimpleNamespace(wait=lambda timeout=None: 1, poll=lambda: 1)
    with pytest.raises(Web01HarnessError, match="failed with exit 1"):
        harness.wait_playwright(timeout=1.0)
    assert harness.playwright is None


def test_pis_document_id_constant() -> None:
    assert PIS_DOCUMENT_ID.startswith("DOC-WEB01")
    assert WEB01_EDITOR_USERNAME == "web01_editor"


def test_start_backend_initial_runs_fixture_initialization_once() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    with patch.object(harness, "_launch_backend_process") as launch_mock, patch(
        "tests.acceptance.web01_realprocess_harness.complete_bootstrap_password_change",
    ) as bootstrap_mock, patch(
        "tests.acceptance.web01_realprocess_harness.ensure_bootstrap_admin_qmb",
    ) as qmb_mock:
        harness.start_backend(
            live_env=live_env,
            dist_dir=dist_dir,
            run_fixture_initialization=True,
        )
    launch_mock.assert_called_once_with(
        live_env=live_env,
        dist_dir=dist_dir,
        append_backend_log=False,
    )
    bootstrap_mock.assert_called_once_with(harness.base_url)
    qmb_mock.assert_called_once_with(harness.base_url)
    assert harness._fixture_initialized is True


def test_start_backend_default_runs_fixture_initialization() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    with patch.object(harness, "_launch_backend_process") as launch_mock, patch(
        "tests.acceptance.web01_realprocess_harness.complete_bootstrap_password_change",
    ) as bootstrap_mock, patch(
        "tests.acceptance.web01_realprocess_harness.ensure_bootstrap_admin_qmb",
    ) as qmb_mock:
        harness.start_backend(live_env=live_env, dist_dir=dist_dir)
    launch_mock.assert_called_once_with(
        live_env=live_env,
        dist_dir=dist_dir,
        append_backend_log=False,
    )
    bootstrap_mock.assert_called_once_with(harness.base_url)
    qmb_mock.assert_called_once_with(harness.base_url)
    assert harness._fixture_initialized is True


def test_start_backend_default_parameter_preserves_conflict_harness_call() -> None:
    signature = inspect.signature(Web01RealProcessHarness.start_backend)
    assert signature.parameters["run_fixture_initialization"].default is True
    conflict_source = (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "acceptance"
        / "test_web01_conflict_realprocess.py"
    ).read_text(encoding="utf-8")
    assert "harness.start_backend(live_env=live_postgres_env, dist_dir=dist_dir)" in conflict_source
    assert "run_fixture_initialization" not in conflict_source


def test_restart_backend_process_skips_fixture_initialization() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness._fixture_initialized = True
    harness.bind_port = 54321
    harness.backend = SimpleNamespace()
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    prior_handle = MagicMock()
    harness.backend_log_handle = prior_handle
    with patch.object(harness, "_launch_backend_process") as launch_mock, patch(
        "tests.acceptance.web01_realprocess_harness.stop_backend_graceful",
        return_value=_CLEAN_STOP_DIAGNOSIS,
    ) as stop_mock, patch(
        "tests.acceptance.web01_realprocess_harness.wait_port_free",
    ), patch(
        "tests.acceptance.web01_realprocess_harness.complete_bootstrap_password_change",
    ) as bootstrap_mock, patch(
        "tests.acceptance.web01_realprocess_harness.ensure_bootstrap_admin_qmb",
    ) as qmb_mock:
        harness.restart_backend_process(live_env=live_env, dist_dir=dist_dir)
    stop_mock.assert_called_once()
    assert stop_mock.call_args.kwargs["diagnosis_filename"] == RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME
    prior_handle.close.assert_called_once()
    assert harness.backend_log_handle is None
    launch_mock.assert_called_once_with(
        live_env=live_env,
        dist_dir=dist_dir,
        append_backend_log=True,
    )
    bootstrap_mock.assert_not_called()
    qmb_mock.assert_not_called()


def test_launch_backend_process_appends_backend_log_on_restart() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness.bind_port = 54321
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    mock_process = MagicMock()
    mock_process.stdout = MagicMock()
    mock_process.stdout.read.return_value = ""

    with patch(
        "tests.acceptance.web01_realprocess_harness.sys.platform",
        "linux",
    ), patch(
        "tests.acceptance.web01_realprocess_harness.port_is_free",
        return_value=True,
    ), patch(
        "tests.acceptance.web01_realprocess_harness.write_ephemeral_pems",
        return_value=(workspace / "cert.pem", workspace / "key.pem"),
    ), patch.object(harness, "copy_tracked_license"), patch(
        "tests.acceptance.web01_realprocess_harness.subprocess.Popen",
        return_value=mock_process,
    ), patch(
        "tests.acceptance.web01_realprocess_harness.wait_https_health",
    ), patch(
        "tests.acceptance.web01_realprocess_harness.is_host_running_marker_present",
        return_value=True,
    ), patch(
        "tests.acceptance.web01_realprocess_harness._SubprocessOutputDrainer",
    ) as drainer_ctor:
        harness._launch_backend_process(
            live_env=live_env,
            dist_dir=dist_dir,
            append_backend_log=True,
        )
    drainer_ctor.assert_called_once()
    assert drainer_ctor.call_args.kwargs["append"] is True


def test_restart_backend_process_rejects_stale_host_running_marker() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness._fixture_initialized = True
    harness.backend = SimpleNamespace()
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    with patch(
        "tests.acceptance.web01_realprocess_harness.stop_backend_graceful",
        return_value={
            "fallback_used": False,
            "marker_present_after_exit": True,
            "child_returncode": 0,
        },
    ), patch(
        "tests.acceptance.web01_realprocess_harness.wait_port_free",
    ) as wait_mock, patch.object(harness, "_launch_backend_process") as launch_mock:
        with pytest.raises(Web01HarnessError, match="host-running marker is still present"):
            harness.restart_backend_process(live_env=live_env, dist_dir=dist_dir)
    wait_mock.assert_not_called()
    launch_mock.assert_not_called()


def test_restart_backend_process_rejects_before_fixture_initialization() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness.backend = SimpleNamespace()
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    with patch(
        "tests.acceptance.web01_realprocess_harness.stop_backend_graceful",
    ) as stop_mock, patch.object(harness, "_launch_backend_process") as launch_mock:
        with pytest.raises(Web01HarnessError, match="restart refused before fixture initialization"):
            harness.restart_backend_process(live_env=live_env, dist_dir=dist_dir)
    stop_mock.assert_not_called()
    launch_mock.assert_not_called()


def test_start_backend_initial_refuses_second_initialization_without_retry() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness._fixture_initialized = True
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    with patch.object(harness, "_launch_backend_process") as launch_mock, patch(
        "tests.acceptance.web01_realprocess_harness.complete_bootstrap_password_change",
    ) as bootstrap_mock:
        with pytest.raises(
            Web01HarnessError,
            match="fixture initialization already completed",
        ):
            harness.start_backend(
                live_env=live_env,
                dist_dir=dist_dir,
                run_fixture_initialization=True,
            )
    launch_mock.assert_not_called()
    bootstrap_mock.assert_not_called()


def test_stop_backend_graceful_returns_diagnosis_and_writes_selected_filename() -> None:
    workspace = allocate_k1_workspace()
    proc = SimpleNamespace(poll=lambda: 0)
    with patch(
        "tests.acceptance.web01_realprocess_harness.send_graceful_stop_signal",
    ), patch(
        "tests.acceptance.web01_realprocess_harness.is_host_running_marker_present",
        return_value=False,
    ):
        diagnosis = stop_backend_graceful(
            proc,  # type: ignore[arg-type]
            home=workspace / "qmtool-home",
            workspace=workspace,
            diagnosis_filename=RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
        )
    assert diagnosis == _CLEAN_STOP_DIAGNOSIS
    path = workspace / RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == diagnosis


def test_stop_backend_graceful_default_filename_preserves_h_compatibility() -> None:
    workspace = allocate_k1_workspace()
    proc = SimpleNamespace(poll=lambda: 0)
    with patch(
        "tests.acceptance.web01_realprocess_harness.send_graceful_stop_signal",
    ), patch(
        "tests.acceptance.web01_realprocess_harness.is_host_running_marker_present",
        return_value=False,
    ):
        stop_backend_graceful(
            proc,  # type: ignore[arg-type]
            home=workspace / "qmtool-home",
            workspace=workspace,
        )
    assert (workspace / GRACEFUL_STOP_DIAGNOSIS_FILENAME).is_file()
    assert not (workspace / RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME).exists()


def test_restart_and_final_diagnosis_files_do_not_overwrite_each_other() -> None:
    workspace = allocate_k1_workspace()
    proc = SimpleNamespace(poll=lambda: 0)
    home = workspace / "qmtool-home"
    with patch(
        "tests.acceptance.web01_realprocess_harness.send_graceful_stop_signal",
    ), patch(
        "tests.acceptance.web01_realprocess_harness.is_host_running_marker_present",
        return_value=False,
    ):
        stop_backend_graceful(
            proc,  # type: ignore[arg-type]
            home=home,
            workspace=workspace,
            diagnosis_filename=RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
        )
        stop_backend_graceful(
            proc,  # type: ignore[arg-type]
            home=home,
            workspace=workspace,
            diagnosis_filename=FINAL_GRACEFUL_STOP_DIAGNOSIS_FILENAME,
        )
    restart_path = workspace / RESTART_GRACEFUL_STOP_DIAGNOSIS_FILENAME
    final_path = workspace / FINAL_GRACEFUL_STOP_DIAGNOSIS_FILENAME
    assert restart_path.is_file()
    assert final_path.is_file()
    assert restart_path != final_path


def test_restart_backend_process_rejects_fallback_diagnosis() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness._fixture_initialized = True
    harness.backend = SimpleNamespace()
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    with patch(
        "tests.acceptance.web01_realprocess_harness.stop_backend_graceful",
        return_value={
            "fallback_used": True,
            "marker_present_after_exit": False,
            "child_returncode": 0,
        },
    ), patch.object(harness, "_launch_backend_process") as launch_mock:
        with pytest.raises(Web01HarnessError, match="graceful-stop fallback"):
            harness.restart_backend_process(live_env=live_env, dist_dir=dist_dir)
    launch_mock.assert_not_called()


def test_restart_backend_process_rejects_nonzero_child_returncode() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness._fixture_initialized = True
    harness.backend = SimpleNamespace()
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    with patch(
        "tests.acceptance.web01_realprocess_harness.stop_backend_graceful",
        return_value={
            "fallback_used": False,
            "marker_present_after_exit": False,
            "child_returncode": 1,
        },
    ), patch.object(harness, "_launch_backend_process") as launch_mock:
        with pytest.raises(Web01HarnessError, match="restart refused after backend stop exit 1"):
            harness.restart_backend_process(live_env=live_env, dist_dir=dist_dir)
    launch_mock.assert_not_called()


def test_restart_backend_process_preserves_backend_reference_when_stop_raises() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness._fixture_initialized = True
    backend = SimpleNamespace()
    harness.backend = backend
    log_handle = MagicMock()
    harness.backend_log_handle = log_handle
    live_env = SimpleNamespace(runtime_dsn="postgresql://example/runtime")
    dist_dir = workspace / "dist"
    with patch(
        "tests.acceptance.web01_realprocess_harness.stop_backend_graceful",
        side_effect=Web01HarnessError("stop failed"),
    ), patch.object(harness, "_launch_backend_process") as launch_mock:
        with pytest.raises(Web01HarnessError, match="stop failed"):
            harness.restart_backend_process(live_env=live_env, dist_dir=dist_dir)
    assert harness.backend is backend
    assert harness.backend_log_handle is log_handle
    launch_mock.assert_not_called()


def test_cleanup_default_diagnosis_filename_preserves_h_compatibility() -> None:
    workspace = allocate_k1_workspace()
    harness = Web01RealProcessHarness(workspace=workspace)
    harness.backend = SimpleNamespace()
    with patch(
        "tests.acceptance.web01_realprocess_harness.stop_owned_process",
    ), patch(
        "tests.acceptance.web01_realprocess_harness.stop_backend_graceful",
        return_value=_CLEAN_STOP_DIAGNOSIS,
    ) as stop_mock, patch(
        "tests.acceptance.web01_realprocess_harness.exit_maintenance",
    ):
        harness.cleanup()
    stop_mock.assert_called_once()
    assert stop_mock.call_args.kwargs["diagnosis_filename"] == GRACEFUL_STOP_DIAGNOSIS_FILENAME


def test_require_clean_restart_stop_diagnosis_rejects_each_failure_mode() -> None:
    with pytest.raises(Web01HarnessError, match="graceful-stop fallback"):
        require_clean_restart_stop_diagnosis(
            {"fallback_used": True, "marker_present_after_exit": False, "child_returncode": 0}
        )
    with pytest.raises(Web01HarnessError, match="host-running marker is still present"):
        require_clean_restart_stop_diagnosis(
            {"fallback_used": False, "marker_present_after_exit": True, "child_returncode": 0}
        )
    with pytest.raises(Web01HarnessError, match="restart refused after backend stop exit 2"):
        require_clean_restart_stop_diagnosis(
            {"fallback_used": False, "marker_present_after_exit": False, "child_returncode": 2}
        )
