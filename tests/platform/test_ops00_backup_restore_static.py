"""Static checks for OPS00-C PostgreSQL + blob backup orchestrator."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sys
import threading
from pathlib import Path

import pytest

from qm_platform.blob.backup_orchestrator import (
    CHECKSUMS_FILENAME,
    DUMP_FILENAME,
    MANIFEST_FILENAME,
    BackupOrchestratorError,
    backups_root,
    create_backup,
    host_running_marker_path,
    release_identity_path,
    remove_host_running_marker_if_owned,
    restore_backup_set,
    write_host_running_marker,
)
from qm_platform.runtime.operation_lock import (
    OperationLock,
    OperationLockError,
    is_operation_lock_held,
    operation_lock_path,
)
from src.backend.bootstrap import BackendBootstrapError
from src.backend.service_host import ServiceHost


ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SOURCE = ROOT / "qm_platform" / "blob" / "backup_orchestrator.py"


def _write_release_identity(app_home: Path, content: bytes = b"ops00-test-release") -> None:
    identity = release_identity_path(app_home)
    identity.parent.mkdir(parents=True, exist_ok=True)
    identity.write_bytes(content)


def _minimal_manifest(*, dump_checksum: str, blob_key: str, blob_checksum: str) -> dict:
    return {
        "backup_id": "00000000-0000-4000-8000-000000000001",
        "created_at": "2026-08-31T12:00:00+00:00",
        "app_release_fingerprint": "a" * 64,
        "schema_migration_fingerprint": "b" * 64,
        "dump": {"filename": DUMP_FILENAME, "checksum_sha256": dump_checksum},
        "blobs": [
            {
                "storage_key": blob_key,
                "checksum_sha256": blob_checksum,
                "size_bytes": 4,
            }
        ],
    }


def test_orchestrator_does_not_import_cutover_drill_or_sqlite_evolution() -> None:
    source = ORCHESTRATOR_SOURCE.read_text(encoding="utf-8")
    assert "cutover_drill" not in source
    assert "DatabaseEvolutionService" not in source
    assert "modules.usermanagement" not in source
    assert "tests." not in source


def test_restore_never_overwrites_preexisting_target_database() -> None:
    source = ORCHESTRATOR_SOURCE.read_text(encoding="utf-8")
    assert "DROP DATABASE IF EXISTS" not in source
    assert "CREATE DATABASE {}" in source
    assert "cleanup_target_database" in source


def test_backup_refused_when_host_running_marker_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)
    write_host_running_marker(tmp_path)
    called = {"dump": False}

    def _blocked_pg_dump_args(*_args, **_kwargs):
        called["dump"] = True
        raise AssertionError("pg_dump must not run while host marker is present")

    monkeypatch.setattr(
        "qm_platform.blob.backup_orchestrator._pg_dump_args",
        _blocked_pg_dump_args,
    )
    with pytest.raises(BackupOrchestratorError, match="host running marker"):
        create_backup(source_dsn="postgresql://u@127.0.0.1:5432/db", metadata_dsn="postgresql://u@127.0.0.1:5432/db")
    assert called["dump"] is False


def test_backup_refused_when_exclusive_lock_held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)
    with OperationLock(app_home=tmp_path):
        with pytest.raises(BackupOrchestratorError, match="operation lock"):
            create_backup(
                source_dsn="postgresql://u@127.0.0.1:5432/db",
                metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            )


def test_service_host_start_refused_when_exclusive_lock_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    with OperationLock(app_home=tmp_path):
        host = ServiceHost()
        with pytest.raises(BackendBootstrapError, match="operation lock"):
            host.start(timeout=1.0)


def test_incomplete_backup_set_rejected_on_restore(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup-set"
    backup_dir.mkdir()
    manifest = _minimal_manifest(
        dump_checksum="c" * 64,
        blob_key="artifacts/sample.bin",
        blob_checksum="d" * 64,
    )
    (backup_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    (backup_dir / CHECKSUMS_FILENAME).write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(BackupOrchestratorError, match="dump file is missing"):
        restore_backup_set(
            backup_dir=backup_dir,
            target_admin_dsn="postgresql://admin@127.0.0.1:5432/postgres",
            target_database="qmtool_ops00_restore_static",
            destination_blob_root=tmp_path / "blobs",
        )


def _write_complete_set_with_blob_key(tmp_path: Path, blob_key: str) -> tuple[Path, Path]:
    victim = tmp_path / "sentinel.txt"
    victim.write_text("do-not-overwrite", encoding="utf-8")
    dump_bytes = b"dump-bytes"
    blob_bytes = b"data"
    dump_checksum = hashlib.sha256(dump_bytes).hexdigest()
    blob_checksum = hashlib.sha256(blob_bytes).hexdigest()
    backup_dir = tmp_path / "backup-set"
    blobs_dir = backup_dir / "blobs" / "artifacts"
    blobs_dir.mkdir(parents=True)
    (blobs_dir / "sample.bin").write_bytes(blob_bytes)
    (backup_dir / DUMP_FILENAME).write_bytes(dump_bytes)
    manifest = _minimal_manifest(
        dump_checksum=dump_checksum,
        blob_key=blob_key,
        blob_checksum=blob_checksum,
    )
    (backup_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    (backup_dir / CHECKSUMS_FILENAME).write_text(
        json.dumps({DUMP_FILENAME: dump_checksum, blob_key: blob_checksum}),
        encoding="utf-8",
    )
    dest = tmp_path / "restore-blobs"
    return victim, dest


@pytest.mark.parametrize(
    "blob_key",
    [
        "../sentinel.txt",
        "../../sentinel.txt",
        "/tmp/sentinel.txt",
        "..\\sentinel.txt",
    ],
)
def test_restore_rejects_traversing_storage_key_before_any_mutation(
    tmp_path: Path, blob_key: str
) -> None:
    victim, dest = _write_complete_set_with_blob_key(tmp_path, blob_key)
    with pytest.raises(BackupOrchestratorError):
        restore_backup_set(
            backup_dir=tmp_path / "backup-set",
            target_admin_dsn="postgresql://admin@127.0.0.1:5432/postgres",
            target_database="qmtool_ops00_restore_static",
            destination_blob_root=dest,
        )
    assert victim.read_text(encoding="utf-8") == "do-not-overwrite"
    assert not dest.exists()


def test_restore_rejects_traversing_dump_filename(tmp_path: Path) -> None:
    dump_bytes = b"dump-bytes"
    blob_bytes = b"data"
    dump_checksum = hashlib.sha256(dump_bytes).hexdigest()
    blob_checksum = hashlib.sha256(blob_bytes).hexdigest()
    backup_dir = tmp_path / "backup-set"
    blobs_dir = backup_dir / "blobs" / "artifacts"
    blobs_dir.mkdir(parents=True)
    (blobs_dir / "sample.bin").write_bytes(blob_bytes)
    (backup_dir / DUMP_FILENAME).write_bytes(dump_bytes)
    manifest = _minimal_manifest(
        dump_checksum=dump_checksum,
        blob_key="artifacts/sample.bin",
        blob_checksum=blob_checksum,
    )
    manifest["dump"]["filename"] = "../database.dump"
    (backup_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    (backup_dir / CHECKSUMS_FILENAME).write_text(
        json.dumps({DUMP_FILENAME: dump_checksum, "artifacts/sample.bin": blob_checksum}),
        encoding="utf-8",
    )
    dest = tmp_path / "restore-blobs"
    with pytest.raises(BackupOrchestratorError, match="dump filename is not allowed"):
        restore_backup_set(
            backup_dir=backup_dir,
            target_admin_dsn="postgresql://admin@127.0.0.1:5432/postgres",
            target_database="qmtool_ops00_restore_static",
            destination_blob_root=dest,
        )
    assert not dest.exists()


def _complete_backup_set(
    tmp_path: Path,
    *,
    dump_bytes: bytes = b"dump-bytes",
    blob_bytes: bytes = b"data",
    checksums_dump_value: str | None = "MATCH",
) -> Path:
    backup_dir = tmp_path / "backup-set"
    blobs_dir = backup_dir / "blobs" / "artifacts"
    blobs_dir.mkdir(parents=True)
    blob_path = blobs_dir / "sample.bin"
    blob_path.write_bytes(blob_bytes)
    dump_path = backup_dir / DUMP_FILENAME
    dump_path.write_bytes(dump_bytes)

    dump_checksum = hashlib.sha256(dump_bytes).hexdigest()
    blob_checksum = hashlib.sha256(blob_bytes).hexdigest()
    manifest = _minimal_manifest(
        dump_checksum=dump_checksum,
        blob_key="artifacts/sample.bin",
        blob_checksum=blob_checksum,
    )
    (backup_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

    checksums_doc: dict[str, str] = {
        "artifacts/sample.bin": blob_checksum,
    }
    if checksums_dump_value == "MATCH":
        checksums_doc[DUMP_FILENAME] = dump_checksum
    elif checksums_dump_value is not None:
        checksums_doc[DUMP_FILENAME] = checksums_dump_value
    (backup_dir / CHECKSUMS_FILENAME).write_text(json.dumps(checksums_doc), encoding="utf-8")
    return backup_dir


@pytest.mark.parametrize(
    ("checksums_dump_value",),
    [
        (None,),
        ("0" * 64,),
    ],
)
def test_tampered_checksums_dump_entry_rejected(
    tmp_path: Path, checksums_dump_value: str | None
) -> None:
    backup_dir = _complete_backup_set(
        tmp_path,
        checksums_dump_value=checksums_dump_value,
    )
    with pytest.raises(BackupOrchestratorError, match="checksums file mismatch for dump"):
        restore_backup_set(
            backup_dir=backup_dir,
            target_admin_dsn="postgresql://admin@127.0.0.1:5432/postgres",
            target_database="qmtool_ops00_restore_static",
            destination_blob_root=tmp_path / "restore-blobs",
        )


def test_tampered_manifest_checksum_rejected(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup-set"
    blobs_dir = backup_dir / "blobs" / "artifacts"
    blobs_dir.mkdir(parents=True)
    blob_path = blobs_dir / "sample.bin"
    blob_path.write_bytes(b"data")
    dump_path = backup_dir / DUMP_FILENAME
    dump_path.write_bytes(b"dump-bytes")

    dump_checksum = "e" * 64
    blob_checksum = "f" * 64
    manifest = _minimal_manifest(
        dump_checksum=dump_checksum,
        blob_key="artifacts/sample.bin",
        blob_checksum=blob_checksum,
    )
    (backup_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    (backup_dir / CHECKSUMS_FILENAME).write_text(
        json.dumps(
            {
                DUMP_FILENAME: dump_checksum,
                "artifacts/sample.bin": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(BackupOrchestratorError, match="checksum"):
        restore_backup_set(
            backup_dir=backup_dir,
            target_admin_dsn="postgresql://admin@127.0.0.1:5432/postgres",
            target_database="qmtool_ops00_restore_static",
            destination_blob_root=tmp_path / "restore-blobs",
        )


def test_stop_timeout_leaves_host_marker_and_blocks_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    from qm_platform.events.event_bus import EventBus
    from qm_platform.logging.audit_logger import AuditLogger
    from qm_platform.logging.logger_service import LoggerService
    from qm_platform.runtime.container import RuntimeContainer
    from qm_platform.settings.testing import build_settings_service_for_tests
    from src.backend.service_host import ServiceHostState

    container = RuntimeContainer()
    container.register_port("logger", LoggerService(tmp_path / "platform.log"))
    container.register_port("audit_logger", AuditLogger(tmp_path / "audit.log"))
    container.register_port("event_bus", EventBus())
    container.register_port("settings_service", build_settings_service_for_tests(tmp_path))
    container.register_port("app_home", tmp_path)
    container.register_port("resource_root", tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )

    class _NonTerminatingThread:
        def is_alive(self) -> bool:
            return True

        def join(self, timeout: float | None = None) -> None:
            return

    dump_called = {"value": False}

    def _track_dump(*_args, **_kwargs):
        dump_called["value"] = True
        return []

    monkeypatch.setattr("qm_platform.blob.backup_orchestrator._pg_dump_args", _track_dump)

    host = ServiceHost()
    host.start(timeout=15.0)
    assert host_running_marker_path(tmp_path).is_dir()

    real_thread = host._thread
    server = host._server
    host._thread = _NonTerminatingThread()
    try:
        with pytest.raises(RuntimeError, match="stop timed out"):
            host.stop(timeout=0.1)
        assert host.status().state == ServiceHostState.STOPPING
        assert host_running_marker_path(tmp_path).is_dir()
        with pytest.raises(BackupOrchestratorError, match="host running marker"):
            create_backup(
                source_dsn="postgresql://u@127.0.0.1:5432/db",
                metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            )
        assert dump_called["value"] is False
    finally:
        host._thread = real_thread
        if server is not None:
            server.should_exit = True
        if real_thread is not None:
            real_thread.join(timeout=15.0)
        token = host._host_running_marker_token
        if token is not None:
            remove_host_running_marker_if_owned(token, tmp_path)


def test_backup_preflight_runs_under_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    seen = {"lock_at_marker": False, "lock_at_fingerprint": False}

    def _marker(app_home: Path | None = None) -> bool:
        seen["lock_at_marker"] = is_operation_lock_held(tmp_path)
        return False

    def _fingerprint(app_home: Path | None = None) -> str:
        seen["lock_at_fingerprint"] = is_operation_lock_held(tmp_path)
        raise BackupOrchestratorError("fingerprint reached under lock")

    monkeypatch.setattr(
        "qm_platform.blob.backup_orchestrator.is_host_running_marker_present",
        _marker,
    )
    monkeypatch.setattr(
        "qm_platform.blob.backup_orchestrator.compute_app_release_fingerprint",
        _fingerprint,
    )
    with pytest.raises(BackupOrchestratorError, match="fingerprint reached under lock"):
        create_backup(
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
        )
    assert seen["lock_at_marker"] is True
    assert seen["lock_at_fingerprint"] is True
    assert is_operation_lock_held(tmp_path) is False


def test_restore_target_and_manifest_check_run_under_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    backup_dir = tmp_path / "empty-set"
    backup_dir.mkdir()
    seen = {"lock_at_target": False, "lock_at_manifest": False}

    def _validate(database_name: str, *, admin_dsn: str) -> None:
        seen["lock_at_target"] = is_operation_lock_held(tmp_path)

    def _load(path: Path) -> dict:
        seen["lock_at_manifest"] = is_operation_lock_held(tmp_path)
        raise BackupOrchestratorError("manifest check reached under lock")

    monkeypatch.setattr(
        "qm_platform.blob.backup_orchestrator._validate_restore_target_database",
        _validate,
    )
    monkeypatch.setattr(
        "qm_platform.blob.backup_orchestrator._load_manifest",
        _load,
    )
    with pytest.raises(BackupOrchestratorError, match="manifest check reached under lock"):
        restore_backup_set(
            backup_dir=backup_dir,
            target_admin_dsn="postgresql://admin@127.0.0.1:5432/postgres",
            target_database="qmtool_ops00_restore_static",
            destination_blob_root=tmp_path / "blobs",
            app_home=tmp_path,
        )
    assert seen["lock_at_target"] is True
    assert seen["lock_at_manifest"] is True
    assert is_operation_lock_held(tmp_path) is False


def test_backup_fails_at_lock_during_host_bootstrap_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    from qm_platform.events.event_bus import EventBus
    from qm_platform.logging.audit_logger import AuditLogger
    from qm_platform.logging.logger_service import LoggerService
    from qm_platform.runtime.container import RuntimeContainer
    from qm_platform.settings.testing import build_settings_service_for_tests

    container = RuntimeContainer()
    container.register_port("logger", LoggerService(tmp_path / "platform.log"))
    container.register_port("audit_logger", AuditLogger(tmp_path / "audit.log"))
    container.register_port("event_bus", EventBus())
    container.register_port("settings_service", build_settings_service_for_tests(tmp_path))
    container.register_port("app_home", tmp_path)
    container.register_port("resource_root", tmp_path)

    entered_bootstrap = threading.Event()
    release_bootstrap = threading.Event()

    def _blocking_container():
        entered_bootstrap.set()
        assert release_bootstrap.wait(timeout=20.0)
        return container

    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        _blocking_container,
    )
    dump_called = {"value": False}
    inventory_called = {"value": False}

    def _track_dump(*_args, **_kwargs):
        dump_called["value"] = True
        return []

    def _track_inventory(self):
        inventory_called["value"] = True
        return ()

    monkeypatch.setattr("qm_platform.blob.backup_orchestrator._pg_dump_args", _track_dump)
    monkeypatch.setattr(
        "qm_platform.blob.filesystem_store.FilesystemBlobStore.inventory",
        _track_inventory,
    )

    host = ServiceHost()
    start_error: dict[str, Exception] = {}

    def _start() -> None:
        try:
            host.start(timeout=25.0)
        except Exception as exc:
            start_error["value"] = exc

    start_thread = threading.Thread(target=_start, name="ops00-host-bootstrap")
    start_thread.start()
    try:
        assert entered_bootstrap.wait(timeout=10.0)
        assert is_operation_lock_held(tmp_path)
        with pytest.raises(BackupOrchestratorError, match="operation lock"):
            create_backup(
                source_dsn="postgresql://u@127.0.0.1:5432/db",
                metadata_dsn="postgresql://u@127.0.0.1:5432/db",
                app_home=tmp_path,
            )
        assert dump_called["value"] is False
        assert inventory_called["value"] is False
    finally:
        release_bootstrap.set()
        start_thread.join(timeout=25.0)
        if host.status().state.name != "STOPPED":
            host.stop(timeout=15.0)
    assert "value" not in start_error


def test_held_backup_lock_blocks_host_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    bootstrap_called = {"value": False}

    def _forbidden_container():
        bootstrap_called["value"] = True
        raise AssertionError("bootstrap must not run while backup lock is held")

    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        _forbidden_container,
    )
    with OperationLock(app_home=tmp_path):
        host = ServiceHost()
        with pytest.raises(BackendBootstrapError, match="operation lock"):
            host.start(timeout=2.0)
    assert bootstrap_called["value"] is False
    assert is_operation_lock_held(tmp_path) is False


def test_restore_drill_script_sets_reset_only_after_preflight() -> None:
    source = (ROOT / "scripts" / "run_ops00_restore_drill.py").read_text(encoding="utf-8")
    pop_before = source.index("os.environ.pop(TEST_RESET_ENV, None)")
    preflight_at = source.index("preflight_isolated_postgres_target()")
    set_at = source.index("os.environ[TEST_RESET_ENV] = RESET_OPT_IN_VALUE")
    require_at = source.index("require_approved_admin_dsn()")
    pop_after = source.index("os.environ.pop(TEST_RESET_ENV, None)", set_at)
    assert pop_before < preflight_at < set_at < require_at
    assert set_at < pop_after
    assert "RESET_OPT_IN_VALUE" in source


def test_standalone_create_backup_acquires_and_releases_own_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)
    seen = {"held_during": False}

    def _probe(_home=None):
        seen["held_during"] = is_operation_lock_held(tmp_path)
        raise BackupOrchestratorError("fingerprint probe")

    monkeypatch.setattr(
        "qm_platform.blob.backup_orchestrator.compute_app_release_fingerprint",
        _probe,
    )
    with pytest.raises(BackupOrchestratorError, match="fingerprint probe"):
        create_backup(
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
        )
    assert seen["held_during"] is True
    assert is_operation_lock_held(tmp_path) is False


def test_held_operation_lock_accepted_and_still_held_after_c_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)
    lock = OperationLock(app_home=tmp_path)
    lock.acquire()
    try:

        def _probe(_home=None):
            lock.validate_held_for(tmp_path)
            raise BackupOrchestratorError("fingerprint probe")

        monkeypatch.setattr(
            "qm_platform.blob.backup_orchestrator.compute_app_release_fingerprint",
            _probe,
        )
        with pytest.raises(BackupOrchestratorError, match="fingerprint probe"):
            create_backup(
                source_dsn="postgresql://u@127.0.0.1:5432/db",
                metadata_dsn="postgresql://u@127.0.0.1:5432/db",
                app_home=tmp_path,
                held_operation_lock=lock,
            )
        lock.validate_held_for(tmp_path)
        assert is_operation_lock_held(tmp_path) is True
    finally:
        lock.release()
    assert is_operation_lock_held(tmp_path) is False


def test_operation_lock_rejects_descriptor_owner_identity_mismatch_without_deleting_owner(
    tmp_path: Path,
) -> None:
    lock = OperationLock(app_home=tmp_path)
    lock.acquire()
    original_fd = lock._fd
    owner_path = lock._owner_path
    assert original_fd is not None
    assert owner_path is not None
    foreign = tmp_path / "foreign-operation-owner.lock"
    foreign_fd = os.open(str(foreign), os.O_CREAT | os.O_EXCL | os.O_RDWR)
    lock._fd = foreign_fd
    try:
        with pytest.raises(OperationLockError, match="no longer matches"):
            lock.validate_held_for(tmp_path)
        with pytest.raises(OperationLockError, match="no longer matches"):
            lock.release()
        assert owner_path.is_file()
        assert operation_lock_path(tmp_path).is_dir()
    finally:
        os.close(original_fd)
        owner_path.unlink(missing_ok=True)
        operation_lock_path(tmp_path).rmdir()
        foreign.unlink(missing_ok=True)


def test_operation_lock_release_preserves_replacement_after_identity_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = OperationLock(app_home=tmp_path)
    lock.acquire()
    owned_fd = lock._fd
    lock_path = operation_lock_path(tmp_path)
    assert owned_fd is not None
    assert lock._owner_path is not None

    real_close = os.close
    replacement_owner = lock_path / "foreign-owner.lock"
    replaced = False

    def _close_then_replace(fd: int) -> None:
        nonlocal replaced
        real_close(fd)
        if fd == owned_fd and not replaced:
            replaced = True
            shutil.rmtree(lock_path)
            lock_path.mkdir()
            replacement_owner.write_text("foreign", encoding="ascii")

    monkeypatch.setattr(os, "close", _close_then_replace)
    try:
        with pytest.raises(OperationLockError, match="failed to release"):
            lock.release()
        assert replacement_owner.read_text(encoding="ascii") == "foreign"
        assert is_operation_lock_held(tmp_path) is True
    finally:
        monkeypatch.setattr(os, "close", real_close)
        replacement_owner.unlink(missing_ok=True)
        lock_path.rmdir()


def test_operation_lock_write_failure_closes_descriptor_and_removes_own_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = OperationLock(app_home=tmp_path)
    real_write = os.write

    def _write_failure(fd: int, payload: bytes) -> int:
        raise OSError("simulated lock owner write failure")

    monkeypatch.setattr(os, "write", _write_failure)
    with pytest.raises(OSError, match="simulated lock owner write failure"):
        lock.acquire()
    assert lock._fd is None
    assert lock._owner_path is None
    assert not operation_lock_path(tmp_path).exists()

    monkeypatch.setattr(os, "write", real_write)
    with OperationLock(app_home=tmp_path):
        assert is_operation_lock_held(tmp_path) is True
    assert is_operation_lock_held(tmp_path) is False


def test_unheld_operation_lock_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)
    lock = OperationLock(app_home=tmp_path)
    with pytest.raises(BackupOrchestratorError, match="held operation lock"):
        create_backup(
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
            held_operation_lock=lock,
        )
    assert is_operation_lock_held(tmp_path) is False


def test_wrong_home_held_lock_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = tmp_path / "other-home"
    other.mkdir()
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)
    lock = OperationLock(app_home=other)
    lock.acquire()
    try:
        with pytest.raises(BackupOrchestratorError, match="held operation lock"):
            create_backup(
                source_dsn="postgresql://u@127.0.0.1:5432/db",
                metadata_dsn="postgresql://u@127.0.0.1:5432/db",
                app_home=tmp_path,
                held_operation_lock=lock,
            )
        lock.validate_held_for(other)
    finally:
        lock.release()


def test_boolean_or_path_signal_cannot_substitute_held_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)

    class _FakeLock:
        held = True
        path = tmp_path / "storage" / "platform" / "operation.lock"

    with pytest.raises(BackupOrchestratorError, match="held operation lock"):
        create_backup(
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
            held_operation_lock=_FakeLock(),  # type: ignore[arg-type]
        )


def test_c_error_does_not_release_borrowed_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)
    write_host_running_marker(tmp_path)
    lock = OperationLock(app_home=tmp_path)
    lock.acquire()
    try:
        with pytest.raises(BackupOrchestratorError, match="host running marker"):
            create_backup(
                source_dsn="postgresql://u@127.0.0.1:5432/db",
                metadata_dsn="postgresql://u@127.0.0.1:5432/db",
                app_home=tmp_path,
                held_operation_lock=lock,
            )
        lock.validate_held_for(tmp_path)
    finally:
        lock.release()


def test_standalone_restore_releases_own_lock_after_error(tmp_path: Path) -> None:
    backup_dir = tmp_path / "missing-set"
    with pytest.raises(BackupOrchestratorError, match="backup set directory is missing"):
        restore_backup_set(
            backup_dir=backup_dir,
            target_admin_dsn="postgresql://admin@127.0.0.1:5432/postgres",
            target_database="qmtool_ops00_restore_static",
            destination_blob_root=tmp_path / "blobs",
            app_home=tmp_path,
        )
    assert is_operation_lock_held(tmp_path) is False


@pytest.mark.parametrize(
    "backup_id",
    [
        r"C:\Windows\Temp\evil",
        r"I:\outside\backup",
        "/tmp/evil",
        "//server/share/evil",
        "..",
        "../outside",
        r"..\outside",
        "nested/id",
        r"nested\id",
        "foo/../../etc",
        ".",
        "ops00-explicit-1",
    ],
)
def test_explicit_backup_id_rejects_traversal_and_absolute_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backup_id: str
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)
    sentinel = tmp_path / "outside-sentinel.txt"
    sentinel.write_text("keep-me", encoding="utf-8")
    root = backups_root(tmp_path)
    with pytest.raises(BackupOrchestratorError, match="single safe path component"):
        create_backup(
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
            backup_id=backup_id,
        )
    assert sentinel.read_text(encoding="utf-8") == "keep-me"
    assert not root.exists()
    assert list(tmp_path.glob("**/evil")) == []


def test_explicit_safe_backup_id_is_accepted_before_connect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)

    def _blocked_connect(*_args, **_kwargs):
        raise RuntimeError("connect must not be required to accept a safe backup_id")

    monkeypatch.setattr(
        "qm_platform.blob.backup_orchestrator.psycopg.connect",
        _blocked_connect,
    )
    with pytest.raises(RuntimeError, match="connect must not be required"):
        create_backup(
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
            backup_id="00000000-0000-4000-8000-0000000000d1",
        )
    dest = backups_root(tmp_path) / "00000000-0000-4000-8000-0000000000d1"
    assert not dest.exists()
    assert is_operation_lock_held(tmp_path) is False


def test_duplicate_backup_id_does_not_delete_existing_sealed_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_identity(tmp_path)
    backup_id = "00000000-0000-4000-8000-0000000000d2"
    dest = backups_root(tmp_path) / backup_id
    dest.mkdir(parents=True)
    blob = dest / "blobs" / "artifacts" / "kept.bin"
    blob.parent.mkdir(parents=True)
    (dest / MANIFEST_FILENAME).write_text(
        json.dumps({"backup_id": backup_id}),
        encoding="utf-8",
    )
    (dest / DUMP_FILENAME).write_bytes(b"original-dump-bytes")
    (dest / CHECKSUMS_FILENAME).write_text('{"database.dump": "abc"}', encoding="utf-8")
    blob.write_bytes(b"original-blob-bytes")
    before = {
        path.relative_to(dest).as_posix(): (
            path.read_bytes(),
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in dest.rglob("*")
        if path.is_file()
    }
    with pytest.raises(BackupOrchestratorError, match="already exists"):
        create_backup(
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
            backup_id=backup_id,
        )
    after = {
        path.relative_to(dest).as_posix(): (
            path.read_bytes(),
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in dest.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize(
    ("argv", "script_name"),
    [
        (
            ["ops", "restore-drill", "--backup-dir", "sealed-set"],
            "run_ops00_restore_drill.py",
        ),
        (
            ["ops", "update-rehearsal", "--abort", "--backup-dir", "sealed-set"],
            "run_ops00_update_rehearsal.py",
        ),
    ],
)
def test_ops_cli_dispatches_existing_repo_root_drill_scripts(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    script_name: str,
) -> None:
    from interfaces.cli import main as cli_main
    from interfaces.cli.commands import ops_commands

    seen: dict[str, object] = {}

    class _Completed:
        returncode = 0

    def _run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return _Completed()

    monkeypatch.setattr(ops_commands.subprocess, "run", _run)
    monkeypatch.setattr(sys, "argv", ["qmtool", *argv])
    assert cli_main.main() == 0
    command = seen["command"]
    assert isinstance(command, list)
    script = Path(command[1])
    assert script == ROOT / "scripts" / script_name
    assert script.is_file()


def test_restore_drill_script_delegates_cleanup_to_locked_restore_owner() -> None:
    source = (ROOT / "scripts" / "run_ops00_restore_drill.py").read_text(encoding="utf-8")
    assert "cleanup_target_database=True" in source
    assert "DROP DATABASE" not in source
    assert "_drop_restore_database" not in source
