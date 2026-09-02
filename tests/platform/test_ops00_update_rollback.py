"""Static and live checks for OPS00-D maintenance and update rehearsal abort."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import secrets
import socket
import string
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from qm_platform.blob import (
    BACKUP_SET_OPEN,
    BackupSetWrite,
    BlobArtifactWrite,
    FilesystemBlobStore,
    PlatformBlobRepository,
    create_backup,
)
from qm_platform.blob.backup_orchestrator import (
    RESTORE_DB_PREFIX,
    BackupOrchestratorError,
    compute_app_release_fingerprint,
    is_host_running_marker_present,
    release_identity_path,
    write_host_running_marker,
)
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.persistence import postgres_schema as pgs
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.maintenance import (
    MaintenanceError,
    abort_update_rehearsal,
    get_expected_release_fingerprint,
    is_rehearsal_in_progress,
    rehearsal_state_path,
    release_snapshot_dir,
    replace_release_with_candidate,
    restore_release_snapshot,
    snapshot_release_tree,
    start_update_rehearsal,
)
from qm_platform.runtime.operation_lock import (
    OperationLock,
    OperationLockError,
    is_operation_lock_held,
)
from qm_platform.settings.testing import build_settings_service_for_tests
from src.backend.bootstrap import BackendBootstrapError
from src.backend.service_host import ServiceHost, drain_and_stop_active_host
from tests.platform.test_postgres_schema_live import _prepare_platform_schema
from tests.postgres_destructive_guard import (
    DestructivePostgresGuardError,
    require_approved_admin_dsn,
)
from tests.postgres_live_support import LivePostgresEnv

ROOT = Path(__file__).resolve().parents[2]
MAINTENANCE_SOURCE = ROOT / "qm_platform" / "runtime" / "maintenance.py"
OPS_COMMANDS_SOURCE = ROOT / "interfaces" / "cli" / "commands" / "ops_commands.py"
UPDATE_REHEARSAL_SCRIPT = ROOT / "scripts" / "run_ops00_update_rehearsal.py"


def _write_release_tree(base: Path, identity_bytes: bytes) -> Path:
    release = base / "release"
    release.mkdir(parents=True, exist_ok=True)
    (release / "identity").write_bytes(identity_bytes)
    return release


def _write_candidate_tree(base: Path, identity_bytes: bytes) -> Path:
    candidate = base / "candidate-b"
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / "identity").write_bytes(identity_bytes)
    return candidate


def _minimal_container(tmp_path: Path) -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("logger", LoggerService(tmp_path / "platform.log"))
    container.register_port("audit_logger", AuditLogger(tmp_path / "audit.log"))
    container.register_port("event_bus", EventBus())
    container.register_port(
        "settings_service",
        build_settings_service_for_tests(tmp_path),
    )
    container.register_port("app_home", tmp_path)
    container.register_port("resource_root", tmp_path)
    return container


def _restore_db_name() -> str:
    alphabet = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{RESTORE_DB_PREFIX}{suffix}"


def _drop_ops00_restore_database(database_name: str, *, admin_dsn: str) -> None:
    if not database_name.startswith(RESTORE_DB_PREFIX):
        raise DestructivePostgresGuardError("restore database name missing required prefix")
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (database_name,),
        )
        admin.execute(
            psycopg.sql.SQL("DROP DATABASE IF EXISTS {}").format(
                psycopg.sql.Identifier(database_name)
            )
        )


def _seed_blob_artifacts(
    env: LivePostgresEnv,
    store: FilesystemBlobStore,
    *,
    storage_key: str,
    payload: bytes,
) -> None:
    checksum = hashlib.sha256(payload).hexdigest()
    store.write_bytes(storage_key, payload)
    backup_set_id = str(uuid4())
    artifact_id = str(uuid4())
    now = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    with psycopg.connect(env.runtime_dsn) as runtime:
        runtime.execute("SET ROLE qmtool_runtime")
        PlatformBlobRepository.insert_backup_set_on_connection(
            runtime,
            BackupSetWrite(backup_set_id=backup_set_id, status=BACKUP_SET_OPEN, created_at=now),
        )
        PlatformBlobRepository.insert_artifact_on_connection(
            runtime,
            BlobArtifactWrite(
                artifact_id=artifact_id,
                backup_set_id=backup_set_id,
                checksum_sha256=checksum,
                size_bytes=len(payload),
                media_type="application/octet-stream",
                version_no=1,
                storage_key=storage_key,
                created_at=now,
                updated_at=now,
            ),
        )
        runtime.commit()


def test_abort_restores_release_tree_a_fingerprint(tmp_path: Path) -> None:
    app_home = tmp_path / "home"
    app_home.mkdir()
    identity_a = b"ops00-release-tree-a-bytes"
    identity_b = b"ops00-release-tree-b-bytes-different"
    _write_release_tree(app_home, identity_a)
    fp_a = compute_app_release_fingerprint(app_home)

    snapshot_fp = snapshot_release_tree(app_home)
    assert snapshot_fp == fp_a

    candidate = _write_candidate_tree(app_home, identity_b)
    replace_release_with_candidate(candidate, app_home)
    assert compute_app_release_fingerprint(app_home) != fp_a

    restored_fp = restore_release_snapshot(app_home)
    assert restored_fp == fp_a
    assert release_identity_path(app_home).read_bytes() == identity_a


def test_maintenance_module_uses_operation_lock_not_second_lock_class() -> None:
    source = MAINTENANCE_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert "OperationLock" not in class_names
    assert "OperationLock" in source
    assert "operation_lock_path" not in source


def test_no_down_migration_in_d_sources() -> None:
    paths = (
        MAINTENANCE_SOURCE,
        OPS_COMMANDS_SOURCE,
        UPDATE_REHEARSAL_SCRIPT,
        ROOT / "src" / "backend" / "service_host.py",
    )
    forbidden = ("down_migration", "downgrade", "DatabaseEvolutionService", "cutover_drill")
    for path in paths:
        source = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in source, f"{token!r} found in {path}"


def test_rehearsal_refused_when_host_running_marker_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    app_home = tmp_path
    _write_release_tree(app_home, b"release-a")
    candidate = _write_candidate_tree(app_home, b"release-b")
    write_host_running_marker(app_home)
    called = {"backup": False}

    def _fake_create_backup(**kwargs):
        called["backup"] = True
        raise AssertionError("create_backup must not be called when host marker is present")

    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.create_backup",
        _fake_create_backup,
    )
    with pytest.raises(MaintenanceError, match="host running marker is present"):
        start_update_rehearsal(
            candidate_release_dir=candidate,
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=app_home,
        )
    assert called["backup"] is False


def test_drain_and_stop_active_host_enables_rehearsal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    _write_release_tree(tmp_path, b"drain-rehearsal-release-a")
    candidate = _write_candidate_tree(tmp_path, b"drain-rehearsal-release-b")

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )
    host = ServiceHost()
    host.start(timeout=15.0)
    assert is_host_running_marker_present(tmp_path) is True

    drain_and_stop_active_host(timeout=15.0)
    assert host.status().state.name == "STOPPED"
    assert is_host_running_marker_present(tmp_path) is False

    called = {"backup": False}

    def _fake_create_backup(**kwargs):
        called["backup"] = True
        from qm_platform.blob.backup_orchestrator import BackupResult

        backup_path = tmp_path / "backups" / "00000000-0000-4000-8000-000000000003"
        backup_path.mkdir(parents=True, exist_ok=True)
        return BackupResult(
            backup_id="00000000-0000-4000-8000-000000000003",
            backup_path=str(backup_path),
            app_release_fingerprint=compute_app_release_fingerprint(tmp_path),
            schema_migration_fingerprint="b" * 64,
            blob_count=0,
            dump_checksum_sha256="c" * 64,
        )

    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.create_backup",
        _fake_create_backup,
    )
    result = start_update_rehearsal(
        candidate_release_dir=candidate,
        source_dsn="postgresql://u@127.0.0.1:5432/db",
        metadata_dsn="postgresql://u@127.0.0.1:5432/db",
        app_home=tmp_path,
    )
    assert called["backup"] is True
    assert result.candidate_release_fingerprint != result.prior_release_fingerprint


def test_rehearsal_calls_backup_orchestrator_not_pg_dump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    app_home = tmp_path
    _write_release_tree(app_home, b"release-a")
    candidate = _write_candidate_tree(app_home, b"release-b")
    called = {"backup": False, "dump": False}

    def _fake_create_backup(**kwargs):
        called["backup"] = True
        from qm_platform.blob.backup_orchestrator import BackupResult

        backup_path = tmp_path / "backups" / "00000000-0000-4000-8000-000000000001"
        backup_path.mkdir(parents=True, exist_ok=True)
        return BackupResult(
            backup_id="00000000-0000-4000-8000-000000000001",
            backup_path=str(backup_path),
            app_release_fingerprint=compute_app_release_fingerprint(app_home),
            schema_migration_fingerprint="b" * 64,
            blob_count=0,
            dump_checksum_sha256="c" * 64,
        )

    def _blocked_dump(*_args, **_kwargs):
        called["dump"] = True
        raise AssertionError("pg_dump must not be called from maintenance module")

    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.create_backup",
        _fake_create_backup,
    )
    monkeypatch.setattr(
        "qm_platform.blob.backup_orchestrator._pg_dump_args",
        _blocked_dump,
    )
    result = start_update_rehearsal(
        candidate_release_dir=candidate,
        source_dsn="postgresql://u@127.0.0.1:5432/db",
        metadata_dsn="postgresql://u@127.0.0.1:5432/db",
        app_home=app_home,
    )
    assert called["backup"] is True
    assert called["dump"] is False
    assert result.candidate_release_fingerprint != result.prior_release_fingerprint


def test_failed_candidate_staging_restores_release_a_and_releases_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    app_home = tmp_path
    identity_a = b"staging-fail-release-a"
    _write_release_tree(app_home, identity_a)
    candidate = _write_candidate_tree(app_home, b"staging-fail-release-b")

    def _fake_create_backup(**kwargs):
        from qm_platform.blob.backup_orchestrator import BackupResult

        return BackupResult(
            backup_id="00000000-0000-4000-8000-000000000002",
            backup_path=str(tmp_path / "backups" / "00000000-0000-4000-8000-000000000002"),
            app_release_fingerprint=compute_app_release_fingerprint(app_home),
            schema_migration_fingerprint="b" * 64,
            blob_count=0,
            dump_checksum_sha256="c" * 64,
        )

    def _fail_replace(*_args, **_kwargs):
        raise RuntimeError("candidate replace failed")

    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.create_backup",
        _fake_create_backup,
    )
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.replace_release_with_candidate",
        _fail_replace,
    )
    with pytest.raises(RuntimeError, match="candidate replace failed"):
        start_update_rehearsal(
            candidate_release_dir=candidate,
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=app_home,
        )

    assert is_operation_lock_held(app_home) is False
    assert release_identity_path(app_home).read_bytes() == identity_a


def test_abort_restore_failure_leaves_candidate_staged_and_blocks_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    identity_a = b"abort-restore-fail-release-a"
    identity_b = b"abort-restore-fail-release-b"
    _write_release_tree(tmp_path, identity_a)
    candidate = _write_candidate_tree(tmp_path, identity_b)

    def _fake_create_backup(**kwargs):
        from qm_platform.blob.backup_orchestrator import BackupResult

        backup_path = tmp_path / "backups" / "00000000-0000-4000-8000-000000000099"
        backup_path.mkdir(parents=True, exist_ok=True)
        return BackupResult(
            backup_id="00000000-0000-4000-8000-000000000099",
            backup_path=str(backup_path),
            app_release_fingerprint=compute_app_release_fingerprint(tmp_path),
            schema_migration_fingerprint="b" * 64,
            blob_count=0,
            dump_checksum_sha256="c" * 64,
        )

    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.create_backup",
        _fake_create_backup,
    )
    start_update_rehearsal(
        candidate_release_dir=candidate,
        source_dsn="postgresql://u@127.0.0.1:5432/db",
        metadata_dsn="postgresql://u@127.0.0.1:5432/db",
        app_home=tmp_path,
    )
    assert is_rehearsal_in_progress(tmp_path) is True

    def _fail_restore(**kwargs):
        raise BackupOrchestratorError("simulated PG+Blob restore failure")

    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.restore_backup_set",
        _fail_restore,
    )
    with pytest.raises(MaintenanceError, match="simulated PG\\+Blob restore failure"):
        abort_update_rehearsal(
            backup_dir=tmp_path / "backups" / "00000000-0000-4000-8000-000000000099",
            target_admin_dsn="postgresql://u@127.0.0.1:5432/db",
            target_database="qmtool_j04_restore_test",
            destination_blob_root=tmp_path / "blobs-restored",
            app_home=tmp_path,
        )

    assert is_rehearsal_in_progress(tmp_path) is True
    assert get_expected_release_fingerprint(tmp_path) is None

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="candidate is staged"):
        host.start(timeout=2.0)


def test_host_start_fails_on_release_fingerprint_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    identity_a = b"host-mismatch-release-a"
    identity_b = b"host-mismatch-release-b-other"
    _write_release_tree(tmp_path, identity_a)
    fp_a = compute_app_release_fingerprint(tmp_path)
    candidate = _write_candidate_tree(tmp_path, identity_b)
    replace_release_with_candidate(candidate, tmp_path)

    from qm_platform.runtime.maintenance import _save_rehearsal_state

    _save_rehearsal_state(
        {
            "phase": "aborted",
            "expected_app_release_fingerprint": fp_a,
        },
        tmp_path,
    )

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="fingerprint does not match"):
        host.start(timeout=2.0)


def test_host_start_fails_on_fingerprint_mismatch_after_candidate_b(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    identity_a = b"host-start-release-a"
    identity_b = b"host-start-release-b-other"
    _write_release_tree(tmp_path, identity_a)
    snapshot_release_tree(tmp_path)
    candidate = _write_candidate_tree(tmp_path, identity_b)
    replace_release_with_candidate(candidate, tmp_path)

    from qm_platform.runtime.maintenance import _save_rehearsal_state

    _save_rehearsal_state(
        {
            "phase": "candidate_staged",
            "backup_id": "00000000-0000-4000-8000-000000000001",
            "backup_path": str(tmp_path / "backups" / "00000000-0000-4000-8000-000000000001"),
            "prior_release_fingerprint": compute_app_release_fingerprint(tmp_path),
            "candidate_release_fingerprint": compute_app_release_fingerprint(tmp_path),
        },
        tmp_path,
    )

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="candidate is staged"):
        host.start(timeout=2.0)


@pytest.mark.parametrize("payload", [{"phase": "future_phase"}, {"phase": "candidate_staged"}])
def test_host_start_rejects_unknown_or_incomplete_rehearsal_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: dict
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _save_state(tmp_path, payload)
    host = ServiceHost()
    with pytest.raises(BackendBootstrapError, match="rehearsal state is invalid"):
        host.start(timeout=2.0)


def test_host_start_succeeds_after_abort_restores_a(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    identity_a = b"host-abort-release-a"
    identity_b = b"host-abort-release-b-other"
    _write_release_tree(tmp_path, identity_a)
    fp_a = compute_app_release_fingerprint(tmp_path)
    snapshot_release_tree(tmp_path)
    candidate = _write_candidate_tree(tmp_path, identity_b)
    replace_release_with_candidate(candidate, tmp_path)

    from qm_platform.runtime.maintenance import _save_rehearsal_state, restore_release_snapshot

    restored_fp = restore_release_snapshot(tmp_path)
    _save_rehearsal_state(
        {
            "phase": "aborted",
            "expected_app_release_fingerprint": restored_fp,
        },
        tmp_path,
    )
    assert restored_fp == fp_a

    container = _minimal_container(tmp_path)
    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )
    host = ServiceHost()
    host.start(timeout=15.0)
    try:
        assert host.status().state.name == "RUNNING"
    finally:
        host.stop(timeout=15.0)


@pytest.fixture
def platform_env(live_postgres_env: LivePostgresEnv) -> LivePostgresEnv:
    _prepare_platform_schema(live_postgres_env)
    pgs.migrate_platform_schema(live_postgres_env.migrator_dsn)
    yield live_postgres_env


@pytest.mark.postgres
def test_live_update_rehearsal_abort_restores_pg_blob_and_release_a(
    platform_env: LivePostgresEnv,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_dsn = require_approved_admin_dsn()
    app_home = tmp_path / "qmtool-home"
    app_home.mkdir()
    monkeypatch.setenv("QMTOOL_HOME", str(app_home))

    identity_a = b"ops00-live-rehearsal-release-a"
    identity_b = b"ops00-live-rehearsal-release-b"
    _write_release_tree(app_home, identity_a)
    fp_a = compute_app_release_fingerprint(app_home)
    candidate = _write_candidate_tree(app_home, identity_b)

    blob_root = app_home / "storage" / "platform" / "blobs"
    blob_root.mkdir(parents=True)
    store = FilesystemBlobStore(blob_root)
    payload = b"ops00-live-rehearsal-blob"
    _seed_blob_artifacts(
        platform_env, store, storage_key="artifacts/rehearsal.bin", payload=payload
    )

    rehearsal = start_update_rehearsal(
        candidate_release_dir=candidate,
        source_dsn=admin_dsn,
        metadata_dsn=platform_env.runtime_dsn,
        app_home=app_home,
    )
    assert rehearsal.prior_release_fingerprint == fp_a
    assert compute_app_release_fingerprint(app_home) == rehearsal.candidate_release_fingerprint

    restore_db = _restore_db_name()
    restore_blob_root = app_home / "storage" / "platform" / "blobs-rehearsal-restored"
    try:
        aborted = abort_update_rehearsal(
            backup_dir=Path(rehearsal.backup_path),
            target_admin_dsn=admin_dsn,
            target_database=restore_db,
            destination_blob_root=restore_blob_root,
            app_home=app_home,
        )
        assert aborted.restored_release_fingerprint == fp_a
        assert release_identity_path(app_home).read_bytes() == identity_a
        restored_store = FilesystemBlobStore(restore_blob_root)
        assert restored_store.read_bytes("artifacts/rehearsal.bin") == payload
        assert aborted.verified_artifact_count >= 1
    finally:
        _drop_ops00_restore_database(restore_db, admin_dsn=admin_dsn)


@pytest.mark.postgres
def test_live_update_rehearsal_script_without_inherited_reset(
    platform_env: LivePostgresEnv,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_dsn = require_approved_admin_dsn()
    app_home = tmp_path / "qmtool-home"
    app_home.mkdir()
    monkeypatch.setenv("QMTOOL_HOME", str(app_home))

    identity_a = b"ops00-script-rehearsal-a"
    identity_b = b"ops00-script-rehearsal-b"
    _write_release_tree(app_home, identity_a)
    candidate = _write_candidate_tree(app_home, identity_b)

    blob_root = app_home / "storage" / "platform" / "blobs"
    blob_root.mkdir(parents=True)
    store = FilesystemBlobStore(blob_root)
    payload = b"ops00-script-rehearsal-payload"
    _seed_blob_artifacts(
        platform_env, store, storage_key="artifacts/script-rehearsal.bin", payload=payload
    )

    rehearsal = start_update_rehearsal(
        candidate_release_dir=candidate,
        source_dsn=admin_dsn,
        metadata_dsn=platform_env.runtime_dsn,
        app_home=app_home,
    )
    restore_db = _restore_db_name()
    env = os.environ.copy()
    env.pop("QMTOOL_PG_TEST_RESET", None)
    env["QMTOOL_HOME"] = str(app_home)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(UPDATE_REHEARSAL_SCRIPT),
                "--backup-dir",
                rehearsal.backup_path,
                "--target-database",
                restore_db,
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            cwd=str(ROOT),
        )
        assert completed.returncode == 0, completed.stderr
        stdout = completed.stdout
        assert "password=" not in stdout.casefold()
        assert "preflight: ok" in stdout
        json_start = stdout.rfind("{")
        payload_json = json.loads(stdout[json_start:])
        assert payload_json["verified_artifact_count"] >= 1
        assert release_identity_path(app_home).read_bytes() == identity_a
        restored = (
            app_home
            / "storage"
            / "platform"
            / "blobs-update-rehearsal-restore"
            / "artifacts"
            / "script-rehearsal.bin"
        )
        assert restored.read_bytes() == payload
    finally:
        _drop_ops00_restore_database(restore_db, admin_dsn=admin_dsn)


def _assert_rival_cannot_acquire(app_home: Path) -> None:
    started = threading.Event()
    finished = threading.Event()
    result: dict[str, bool | None] = {"acquired": None}

    def _rival() -> None:
        started.set()
        try:
            OperationLock(app_home).acquire()
        except OperationLockError:
            result["acquired"] = False
            finished.set()
            return
        result["acquired"] = True
        finished.set()

    thread = threading.Thread(target=_rival)
    thread.start()
    assert started.wait(timeout=2.0)
    assert finished.wait(timeout=2.0)
    thread.join(timeout=2.0)
    assert result["acquired"] is False
    assert is_operation_lock_held(app_home) is True


def _fake_backup_result(tmp_path: Path, app_home: Path):
    from qm_platform.blob.backup_orchestrator import BackupResult

    backup_path = tmp_path / "backups" / "00000000-0000-4000-8000-0000000000aa"
    backup_path.mkdir(parents=True, exist_ok=True)
    return BackupResult(
        backup_id="00000000-0000-4000-8000-0000000000aa",
        backup_path=str(backup_path),
        app_release_fingerprint=compute_app_release_fingerprint(app_home),
        schema_migration_fingerprint="b" * 64,
        blob_count=0,
        dump_checksum_sha256="c" * 64,
    )


def test_start_rehearsal_has_no_lock_free_hook_between_snapshot_backup_and_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    app_home = tmp_path
    _write_release_tree(app_home, b"lock-window-release-a")
    candidate = _write_candidate_tree(app_home, b"lock-window-release-b")
    checkpoints: list[str] = []

    real_snapshot = snapshot_release_tree
    real_replace = replace_release_with_candidate

    def _snapshot(home=None):
        checkpoints.append("snapshot")
        _assert_rival_cannot_acquire(app_home)
        return real_snapshot(home)

    def _backup(**kwargs):
        checkpoints.append("backup")
        held = kwargs.get("held_operation_lock")
        assert held is not None
        held.validate_held_for(app_home)
        _assert_rival_cannot_acquire(app_home)
        return _fake_backup_result(tmp_path, app_home)

    def _replace(candidate_dir, home=None):
        checkpoints.append("candidate")
        _assert_rival_cannot_acquire(app_home)
        return real_replace(candidate_dir, home)

    monkeypatch.setattr("qm_platform.runtime.maintenance.snapshot_release_tree", _snapshot)
    monkeypatch.setattr("qm_platform.runtime.maintenance.create_backup", _backup)
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.replace_release_with_candidate",
        _replace,
    )
    start_update_rehearsal(
        candidate_release_dir=candidate,
        source_dsn="postgresql://u@127.0.0.1:5432/db",
        metadata_dsn="postgresql://u@127.0.0.1:5432/db",
        app_home=app_home,
    )
    assert checkpoints == ["snapshot", "backup", "candidate"]
    assert is_operation_lock_held(app_home) is False


def test_abort_rehearsal_has_no_lock_free_hook_between_restore_and_aborted_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    app_home = tmp_path
    _write_release_tree(app_home, b"abort-lock-a")
    snapshot_release_tree(app_home)
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    from qm_platform.runtime.maintenance import _save_rehearsal_state

    _save_rehearsal_state(
        {
            "phase": "candidate_staged",
            "backup_id": "00000000-0000-4000-8000-0000000000bb",
            "backup_path": str(backup_dir),
        },
        app_home,
    )
    checkpoints: list[str] = []
    real_restore_tree = restore_release_snapshot

    def _restore_tree(home=None):
        checkpoints.append("release")
        _assert_rival_cannot_acquire(app_home)
        return real_restore_tree(home)

    def _restore_set(**kwargs):
        checkpoints.append("pg_blob")
        held = kwargs.get("held_operation_lock")
        assert held is not None
        held.validate_held_for(app_home)
        _assert_rival_cannot_acquire(app_home)
        from qm_platform.blob.backup_orchestrator import RestoreResult

        return RestoreResult(
            backup_id="00000000-0000-4000-8000-0000000000bb",
            target_database="qmtool_ops00_restore_static",
            restored_blob_count=1,
            verified_artifact_count=1,
        )

    def _save(state, home=None):
        checkpoints.append("aborted")
        _assert_rival_cannot_acquire(app_home)
        return _save_rehearsal_state(state, home)

    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.restore_release_snapshot",
        _restore_tree,
    )
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.restore_backup_set",
        _restore_set,
    )
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance._save_rehearsal_state",
        _save,
    )
    abort_update_rehearsal(
        backup_dir=backup_dir,
        target_admin_dsn="postgresql://admin@127.0.0.1:5432/postgres",
        target_database="qmtool_ops00_restore_static",
        destination_blob_root=tmp_path / "restored-blobs",
        app_home=app_home,
    )
    assert checkpoints == ["release", "pg_blob", "aborted"]
    assert is_operation_lock_held(app_home) is False


def test_update_rehearsal_script_sets_reset_only_after_preflight() -> None:
    source = UPDATE_REHEARSAL_SCRIPT.read_text(encoding="utf-8")
    pop_before = source.index("os.environ.pop(TEST_RESET_ENV, None)")
    preflight_at = source.index("preflight_isolated_postgres_target()")
    set_at = source.index("os.environ[TEST_RESET_ENV] = RESET_OPT_IN_VALUE")
    require_at = source.index("require_approved_admin_dsn()")
    pop_after = source.index("os.environ.pop(TEST_RESET_ENV, None)", set_at)
    assert pop_before < preflight_at < set_at < require_at
    assert set_at < pop_after
    assert "cleanup_target_database=True" in source
    assert "DROP DATABASE" not in source
    assert "_drop_restore_database" not in source


def _save_state(app_home: Path, payload: dict) -> None:
    from qm_platform.runtime.maintenance import _save_rehearsal_state

    _save_rehearsal_state(payload, app_home)


def _track_restore_calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"release": 0, "pg_blob": 0}

    def _restore_tree(*_args, **_kwargs):
        calls["release"] += 1
        raise AssertionError("restore_release_snapshot must not run")

    def _restore_set(**_kwargs):
        calls["pg_blob"] += 1
        raise AssertionError("restore_backup_set must not run")

    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.restore_release_snapshot",
        _restore_tree,
    )
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.restore_backup_set",
        _restore_set,
    )
    return calls


def _abort(app_home: Path, backup_dir: Path) -> None:
    abort_update_rehearsal(
        backup_dir=backup_dir,
        target_admin_dsn="postgresql://u@127.0.0.1:5432/db",
        target_database="qmtool_ops00_restore_static",
        destination_blob_root=app_home / "restored-blobs",
        app_home=app_home,
    )


def test_second_start_while_candidate_staged_leaves_snapshot_live_backup_and_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    app_home = tmp_path
    identity_a = b"replay-guard-release-a"
    identity_b = b"replay-guard-release-b"
    _write_release_tree(app_home, identity_a)
    candidate = _write_candidate_tree(app_home, identity_b)
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.create_backup",
        lambda **kwargs: _fake_backup_result(tmp_path, app_home),
    )
    first = start_update_rehearsal(
        candidate_release_dir=candidate,
        source_dsn="postgresql://u@127.0.0.1:5432/db",
        metadata_dsn="postgresql://u@127.0.0.1:5432/db",
        app_home=app_home,
    )
    snapshot_before = (release_snapshot_dir(app_home) / "identity").read_bytes()
    live_before = release_identity_path(app_home).read_bytes()
    state_before = rehearsal_state_path(app_home).read_bytes()
    assert snapshot_before == identity_a
    assert live_before == identity_b

    later_calls = {"snapshot": 0, "backup": 0, "replace": 0}

    def _snapshot(home=None):
        later_calls["snapshot"] += 1
        raise AssertionError("second start must not snapshot")

    def _backup(**kwargs):
        later_calls["backup"] += 1
        raise AssertionError("second start must not backup")

    def _replace(*_args, **_kwargs):
        later_calls["replace"] += 1
        raise AssertionError("second start must not replace")

    monkeypatch.setattr("qm_platform.runtime.maintenance.snapshot_release_tree", _snapshot)
    monkeypatch.setattr("qm_platform.runtime.maintenance.create_backup", _backup)
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.replace_release_with_candidate",
        _replace,
    )
    with pytest.raises(MaintenanceError, match="already staged"):
        start_update_rehearsal(
            candidate_release_dir=candidate,
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=app_home,
        )
    assert later_calls == {"snapshot": 0, "backup": 0, "replace": 0}
    assert is_operation_lock_held(app_home) is False
    assert (release_snapshot_dir(app_home) / "identity").read_bytes() == identity_a
    assert release_identity_path(app_home).read_bytes() == identity_b
    assert rehearsal_state_path(app_home).read_bytes() == state_before
    state = json.loads(state_before.decode("utf-8"))
    assert state["backup_id"] == first.backup_id
    assert state["backup_path"] == first.backup_path


def test_start_unknown_phase_is_rejected_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_tree(tmp_path, b"unknown-phase-a")
    candidate = _write_candidate_tree(tmp_path, b"unknown-phase-b")
    _save_state(tmp_path, {"phase": "not-a-contract-phase"})
    state_before = rehearsal_state_path(tmp_path).read_bytes()
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.snapshot_release_tree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not snapshot")),
    )
    with pytest.raises(MaintenanceError, match="phase is unknown"):
        start_update_rehearsal(
            candidate_release_dir=candidate,
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
        )
    assert is_operation_lock_held(tmp_path) is False
    assert rehearsal_state_path(tmp_path).read_bytes() == state_before
    assert release_identity_path(tmp_path).read_bytes() == b"unknown-phase-a"


def test_start_incomplete_aborted_state_is_rejected_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_tree(tmp_path, b"incomplete-aborted-release-a")
    candidate = _write_candidate_tree(tmp_path, b"incomplete-aborted-release-b")
    _save_state(tmp_path, {"phase": "aborted"})
    state_before = rehearsal_state_path(tmp_path).read_bytes()
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.snapshot_release_tree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not snapshot")),
    )
    with pytest.raises(MaintenanceError, match="aborted rehearsal state is incomplete"):
        start_update_rehearsal(
            candidate_release_dir=candidate,
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
        )
    assert is_operation_lock_held(tmp_path) is False
    assert rehearsal_state_path(tmp_path).read_bytes() == state_before
    assert release_identity_path(tmp_path).read_bytes() == b"incomplete-aborted-release-a"


def test_start_non_file_rehearsal_state_is_rejected_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    _write_release_tree(tmp_path, b"non-file-state-release-a")
    candidate = _write_candidate_tree(tmp_path, b"non-file-state-release-b")
    state_path = rehearsal_state_path(tmp_path)
    state_path.mkdir(parents=True)
    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.snapshot_release_tree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not snapshot")),
    )
    with pytest.raises(MaintenanceError, match="not a regular file"):
        start_update_rehearsal(
            candidate_release_dir=candidate,
            source_dsn="postgresql://u@127.0.0.1:5432/db",
            metadata_dsn="postgresql://u@127.0.0.1:5432/db",
            app_home=tmp_path,
        )
    assert is_operation_lock_held(tmp_path) is False
    assert state_path.is_dir()
    assert release_identity_path(tmp_path).read_bytes() == b"non-file-state-release-a"


def test_abort_without_state_does_not_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    backup = tmp_path / "backup"
    backup.mkdir()
    calls = _track_restore_calls(monkeypatch)
    with pytest.raises(MaintenanceError, match="rehearsal state is missing"):
        _abort(tmp_path, backup)
    assert calls == {"release": 0, "pg_blob": 0}
    assert is_operation_lock_held(tmp_path) is False
    assert not rehearsal_state_path(tmp_path).is_file()


def test_abort_when_already_aborted_does_not_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    backup = tmp_path / "backup"
    backup.mkdir()
    _save_state(tmp_path, {"phase": "aborted", "backup_path": str(backup)})
    state_before = rehearsal_state_path(tmp_path).read_bytes()
    calls = _track_restore_calls(monkeypatch)
    with pytest.raises(MaintenanceError, match="already aborted"):
        _abort(tmp_path, backup)
    assert calls == {"release": 0, "pg_blob": 0}
    assert rehearsal_state_path(tmp_path).read_bytes() == state_before
    assert is_operation_lock_held(tmp_path) is False


def test_abort_unknown_phase_does_not_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    backup = tmp_path / "backup"
    backup.mkdir()
    _save_state(tmp_path, {"phase": "mystery", "backup_path": str(backup)})
    state_before = rehearsal_state_path(tmp_path).read_bytes()
    calls = _track_restore_calls(monkeypatch)
    with pytest.raises(MaintenanceError, match="phase is unknown"):
        _abort(tmp_path, backup)
    assert calls == {"release": 0, "pg_blob": 0}
    assert rehearsal_state_path(tmp_path).read_bytes() == state_before


def test_abort_with_different_backup_directory_does_not_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    staged = tmp_path / "staged-backup"
    other = tmp_path / "other-backup"
    staged.mkdir()
    other.mkdir()
    _save_state(tmp_path, {"phase": "candidate_staged", "backup_path": str(staged)})
    state_before = rehearsal_state_path(tmp_path).read_bytes()
    calls = _track_restore_calls(monkeypatch)
    with pytest.raises(MaintenanceError, match="does not match the staged backup set"):
        _abort(tmp_path, other)
    assert calls == {"release": 0, "pg_blob": 0}
    assert rehearsal_state_path(tmp_path).read_bytes() == state_before
    assert is_operation_lock_held(tmp_path) is False


@pytest.mark.parametrize(
    ("backup_path", "match"),
    [
        ("", "missing or invalid"),
        (None, "missing or invalid"),
        (123, "missing or invalid"),
        ("__missing__", "does not exist or is invalid"),
    ],
)
def test_abort_rejects_invalid_backup_path_before_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backup_path: object,
    match: str,
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    supplied = tmp_path / "supplied-backup"
    supplied.mkdir()
    payload: dict = {"phase": "candidate_staged"}
    if backup_path == "__missing__":
        payload["backup_path"] = str(tmp_path / "does-not-exist-backup")
    elif backup_path is not None:
        payload["backup_path"] = backup_path
    _save_state(tmp_path, payload)
    state_before = rehearsal_state_path(tmp_path).read_bytes()
    calls = _track_restore_calls(monkeypatch)
    with pytest.raises(MaintenanceError, match=match):
        _abort(tmp_path, supplied)
    assert calls == {"release": 0, "pg_blob": 0}
    assert rehearsal_state_path(tmp_path).read_bytes() == state_before


def test_abort_rejects_file_instead_of_backup_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    backup_file = tmp_path / "backup-file"
    backup_file.write_text("not-a-directory\n", encoding="utf-8")
    _save_state(
        tmp_path,
        {"phase": "candidate_staged", "backup_path": str(backup_file)},
    )
    state_before = rehearsal_state_path(tmp_path).read_bytes()
    calls = _track_restore_calls(monkeypatch)
    with pytest.raises(MaintenanceError, match="not a directory"):
        _abort(tmp_path, backup_file)
    assert calls == {"release": 0, "pg_blob": 0}
    assert rehearsal_state_path(tmp_path).read_bytes() == state_before


def test_abort_accepts_lexical_alias_and_passes_canonical_persisted_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    app_home = tmp_path
    _write_release_tree(app_home, b"alias-abort-a")
    snapshot_release_tree(app_home)
    backup_dir = (tmp_path / "canonical-backup").resolve()
    backup_dir.mkdir()
    persisted = str(backup_dir)
    _save_state(
        app_home,
        {
            "phase": "candidate_staged",
            "backup_id": "00000000-0000-4000-8000-0000000000cc",
            "backup_path": persisted,
        },
    )
    seen: dict[str, Path | None] = {"backup_dir": None}

    def _restore_set(**kwargs):
        seen["backup_dir"] = Path(kwargs["backup_dir"])
        from qm_platform.blob.backup_orchestrator import RestoreResult

        return RestoreResult(
            backup_id="00000000-0000-4000-8000-0000000000cc",
            target_database="qmtool_ops00_restore_static",
            restored_blob_count=1,
            verified_artifact_count=1,
        )

    monkeypatch.setattr(
        "qm_platform.runtime.maintenance.restore_backup_set",
        _restore_set,
    )
    alias = backup_dir / "."
    _abort(app_home, alias)
    received = seen["backup_dir"]
    assert received is not None
    assert received == Path(persisted).resolve(strict=True)
    assert received.samefile(backup_dir)
    assert json.loads(rehearsal_state_path(app_home).read_text(encoding="utf-8"))[
        "phase"
    ] == "aborted"
    assert is_operation_lock_held(app_home) is False
