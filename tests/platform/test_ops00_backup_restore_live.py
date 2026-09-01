"""Live Slot-2 checks for OPS00-C PostgreSQL + blob backup orchestrator."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import socket
import string
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI

from qm_platform.blob.backup_orchestrator import release_identity_path
from qm_platform.blob import (
    BACKUP_SET_OPEN,
    BackupSetWrite,
    BlobArtifactWrite,
    FilesystemBlobStore,
    PlatformBlobRepository,
    create_backup,
    restore_backup_set,
)
from qm_platform.blob.backup_orchestrator import (
    RESTORE_DB_PREFIX,
    BackupOrchestratorError,
    CHECKSUMS_FILENAME,
    MANIFEST_FILENAME,
)
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.persistence import postgres_schema as pgs
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.operation_lock import OperationLock
from qm_platform.settings.testing import build_settings_service_for_tests
from src.backend.bootstrap import BackendBootstrapError
from src.backend.service_host import ServiceHost
from tests.platform.test_postgres_schema_live import _prepare_platform_schema
from tests.postgres_destructive_guard import (
    EXPECTED_DATABASE,
    DestructivePostgresGuardError,
    require_approved_admin_dsn,
)
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres

OPS00_RESTORE_PREFIX = RESTORE_DB_PREFIX


def _write_release_identity(app_home: Path) -> None:
    path = release_identity_path(app_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ops00-live-release-identity")


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
    return f"{OPS00_RESTORE_PREFIX}{suffix}"


def _build_quiescence_test_app() -> tuple[FastAPI, threading.Event, threading.Event]:
    in_flight_started = threading.Event()
    in_flight_block = threading.Event()
    app = FastAPI()

    @app.post("/write")
    async def write_handler() -> dict[str, str]:
        in_flight_started.set()
        await asyncio.to_thread(in_flight_block.wait)
        return {"status": "written"}

    return app, in_flight_started, in_flight_block


def _post_write(url: str, *, timeout: float = 30.0) -> int:
    request = urllib.request.Request(url, data=b"{}", method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return int(response.status)


def _drop_ops00_restore_database(database_name: str, *, admin_dsn: str) -> None:
    if not database_name.startswith(OPS00_RESTORE_PREFIX):
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


@pytest.fixture
def platform_env(live_postgres_env: LivePostgresEnv) -> LivePostgresEnv:
    _prepare_platform_schema(live_postgres_env)
    pgs.migrate_platform_schema(live_postgres_env.migrator_dsn)
    yield live_postgres_env


def test_live_backup_quiescence_host_lock_and_restore(
    platform_env: LivePostgresEnv,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_dsn = require_approved_admin_dsn()
    app_home = tmp_path / "qmtool-home"
    app_home.mkdir()
    monkeypatch.setenv("QMTOOL_HOME", str(app_home))
    _write_release_identity(app_home)

    blob_root = app_home / "storage" / "platform" / "blobs"
    blob_root.mkdir(parents=True)
    store = FilesystemBlobStore(blob_root)
    payload = b"ops00-live-blob-payload"
    _seed_blob_artifacts(platform_env, store, storage_key="artifacts/live.bin", payload=payload)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bind_port = sock.getsockname()[1]
    monkeypatch.setenv("QMTOOL_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("QMTOOL_BIND_PORT", str(bind_port))

    container = _minimal_container(app_home)
    quiescence_app, in_flight_started, in_flight_block = _build_quiescence_test_app()

    def _patched_create_app(_container) -> FastAPI:
        return quiescence_app

    monkeypatch.setattr(
        "src.backend.service_host.build_backend_container",
        lambda: container,
    )
    monkeypatch.setattr("src.backend.service_host.create_app", _patched_create_app)

    write_url = f"http://127.0.0.1:{bind_port}/write"
    host = ServiceHost()
    host.start(timeout=20.0)
    try:
        with pytest.raises(BackupOrchestratorError, match="host running marker"):
            create_backup(
                source_dsn=admin_dsn,
                metadata_dsn=platform_env.runtime_dsn,
                app_home=app_home,
                blob_store=store,
            )

        post_result: dict[str, object] = {}

        def _in_flight_post() -> None:
            try:
                post_result["status"] = _post_write(write_url, timeout=30.0)
            except Exception as exc:
                post_result["error"] = exc

        post_thread = threading.Thread(target=_in_flight_post, name="ops00-in-flight-write")
        post_thread.start()
        assert in_flight_started.wait(timeout=10.0), "in-flight write handler did not start"

        stop_error: dict[str, Exception] = {}

        def _stop_host() -> None:
            try:
                host.stop(timeout=20.0)
            except Exception as exc:
                stop_error["value"] = exc

        stop_thread = threading.Thread(target=_stop_host, name="ops00-host-stop")
        stop_thread.start()
        time.sleep(0.2)
        in_flight_block.set()
        stop_thread.join(timeout=25.0)
        post_thread.join(timeout=25.0)

        assert "value" not in stop_error, stop_error.get("value")
        assert post_result.get("status") == 200
        assert "error" not in post_result

        with pytest.raises((urllib.error.URLError, ConnectionRefusedError, OSError)):
            _post_write(write_url, timeout=2.0)
    finally:
        if host.status().state.name != "STOPPED":
            host.stop(timeout=20.0)

    with OperationLock(app_home=app_home):
        with pytest.raises(BackendBootstrapError, match="operation lock"):
            ServiceHost().start(timeout=5.0)

    backup = create_backup(
        source_dsn=admin_dsn,
        metadata_dsn=platform_env.runtime_dsn,
        app_home=app_home,
        blob_store=store,
    )
    assert backup.blob_count == 1

    restore_db = _restore_db_name()
    restore_blob_root = app_home / "storage" / "platform" / "blobs-restored"
    try:
        restored = restore_backup_set(
            backup_dir=Path(backup.backup_path),
            target_admin_dsn=admin_dsn,
            target_database=restore_db,
            destination_blob_root=restore_blob_root,
            app_home=app_home,
        )
        assert restored.verified_artifact_count >= 1
        restored_store = FilesystemBlobStore(restore_blob_root)
        assert restored_store.read_bytes("artifacts/live.bin") == payload
    finally:
        _drop_ops00_restore_database(restore_db, admin_dsn=admin_dsn)


def test_live_incomplete_backup_set_rejected(
    platform_env: LivePostgresEnv,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_dsn = require_approved_admin_dsn()
    app_home = tmp_path / "qmtool-home"
    app_home.mkdir()
    monkeypatch.setenv("QMTOOL_HOME", str(app_home))
    _write_release_identity(app_home)

    blob_root = app_home / "storage" / "platform" / "blobs"
    blob_root.mkdir(parents=True)
    store = FilesystemBlobStore(blob_root)
    backup = create_backup(
        source_dsn=admin_dsn,
        metadata_dsn=platform_env.runtime_dsn,
        app_home=app_home,
        blob_store=store,
    )
    backup_dir = Path(backup.backup_path)
    manifest_path = backup_dir / MANIFEST_FILENAME
    manifest_path.unlink()
    restore_db = _restore_db_name()
    try:
        with pytest.raises(BackupOrchestratorError, match="manifest"):
            restore_backup_set(
                backup_dir=backup_dir,
                target_admin_dsn=admin_dsn,
                target_database=restore_db,
                destination_blob_root=app_home / "restore-blobs",
                app_home=app_home,
            )
    finally:
        if (backup_dir / CHECKSUMS_FILENAME).exists():
            pass
        _drop_ops00_restore_database(restore_db, admin_dsn=admin_dsn)


def test_live_never_targets_source_database(platform_env: LivePostgresEnv, tmp_path: Path) -> None:
    admin_dsn = require_approved_admin_dsn()
    backup_dir = tmp_path / "empty-set"
    backup_dir.mkdir()
    with pytest.raises(BackupOrchestratorError, match="forbidden"):
        restore_backup_set(
            backup_dir=backup_dir,
            target_admin_dsn=admin_dsn,
            target_database=EXPECTED_DATABASE,
            destination_blob_root=tmp_path / "blobs",
        )

    with pytest.raises(BackupOrchestratorError, match="forbidden"):
        restore_backup_set(
            backup_dir=backup_dir,
            target_admin_dsn=admin_dsn,
            target_database="qmtool_test",
            destination_blob_root=tmp_path / "blobs",
        )


def test_live_restore_drill_script_without_inherited_reset(
    platform_env: LivePostgresEnv,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_dsn = require_approved_admin_dsn()
    app_home = tmp_path / "qmtool-home"
    app_home.mkdir()
    monkeypatch.setenv("QMTOOL_HOME", str(app_home))
    _write_release_identity(app_home)

    blob_root = app_home / "storage" / "platform" / "blobs"
    blob_root.mkdir(parents=True)
    store = FilesystemBlobStore(blob_root)
    payload = b"ops00-script-restore-payload"
    _seed_blob_artifacts(
        platform_env, store, storage_key="artifacts/script.bin", payload=payload
    )
    backup = create_backup(
        source_dsn=admin_dsn,
        metadata_dsn=platform_env.runtime_dsn,
        app_home=app_home,
        blob_store=store,
    )
    restore_db = _restore_db_name()
    script = Path(__file__).resolve().parents[2] / "scripts" / "run_ops00_restore_drill.py"
    env = os.environ.copy()
    env.pop("QMTOOL_PG_TEST_RESET", None)
    env["QMTOOL_HOME"] = str(app_home)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--backup-dir",
                backup.backup_path,
                "--target-database",
                restore_db,
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        assert completed.returncode == 0
        stdout = completed.stdout
        assert "password=" not in stdout.casefold()
        assert "pwd=" not in stdout.casefold()
        assert "preflight: ok" in stdout
        json_start = stdout.rfind("{")
        payload_json = json.loads(stdout[json_start:])
        assert payload_json["verified_artifact_count"] >= 1
        restored = (
            app_home / "storage" / "platform" / "blobs-restore-drill" / "artifacts" / "script.bin"
        )
        assert restored.read_bytes() == payload
    finally:
        _drop_ops00_restore_database(restore_db, admin_dsn=admin_dsn)


def test_live_restore_replaces_destination_blob_tree_exactly(
    platform_env: LivePostgresEnv,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_dsn = require_approved_admin_dsn()
    app_home = tmp_path / "qmtool-home"
    app_home.mkdir()
    monkeypatch.setenv("QMTOOL_HOME", str(app_home))
    _write_release_identity(app_home)

    blob_root = app_home / "storage" / "platform" / "blobs"
    blob_root.mkdir(parents=True)
    store = FilesystemBlobStore(blob_root)
    payload_a = b"ops00-blob-a"
    payload_b = b"ops00-blob-b"
    _seed_blob_artifacts(platform_env, store, storage_key="artifacts/a.bin", payload=payload_a)
    backup_a = create_backup(
        source_dsn=admin_dsn,
        metadata_dsn=platform_env.runtime_dsn,
        app_home=app_home,
        blob_store=store,
    )
    _seed_blob_artifacts(platform_env, store, storage_key="artifacts/b.bin", payload=payload_b)
    backup_ab = create_backup(
        source_dsn=admin_dsn,
        metadata_dsn=platform_env.runtime_dsn,
        app_home=app_home,
        blob_store=store,
    )

    restore_db = _restore_db_name()
    restore_blob_root = app_home / "storage" / "platform" / "blobs-restored"
    try:
        first = restore_backup_set(
            backup_dir=Path(backup_ab.backup_path),
            target_admin_dsn=admin_dsn,
            target_database=restore_db,
            destination_blob_root=restore_blob_root,
            app_home=app_home,
        )
        assert first.verified_artifact_count == 2
        restored_store = FilesystemBlobStore(restore_blob_root)
        keys_after_first = {entry.storage_key for entry in restored_store.inventory()}
        assert keys_after_first == {"artifacts/a.bin", "artifacts/b.bin"}

        stale = restore_blob_root / "artifacts" / "stale.bin"
        stale.write_bytes(b"stale-must-not-survive")

        second = restore_backup_set(
            backup_dir=Path(backup_a.backup_path),
            target_admin_dsn=admin_dsn,
            target_database=restore_db,
            destination_blob_root=restore_blob_root,
            app_home=app_home,
        )
        assert second.verified_artifact_count == 1
        restored_store = FilesystemBlobStore(restore_blob_root)
        inventory = restored_store.inventory()
        assert {entry.storage_key for entry in inventory} == {"artifacts/a.bin"}
        assert restored_store.read_bytes("artifacts/a.bin") == payload_a
        assert not stale.exists()
        leftover_b = restore_blob_root / "artifacts" / "b.bin"
        assert not leftover_b.exists()

        with psycopg.connect(
            psycopg.conninfo.make_conninfo(
                **{
                    **psycopg.conninfo.conninfo_to_dict(admin_dsn),
                    "dbname": restore_db,
                }
            )
        ) as conn:
            pg_rows = PlatformBlobRepository.list_artifacts_on_connection(conn)
        assert len(pg_rows) == 1
        assert str(pg_rows[0]["storage_key"]) == "artifacts/a.bin"
    finally:
        _drop_ops00_restore_database(restore_db, admin_dsn=admin_dsn)
