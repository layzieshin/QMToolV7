"""Static checks for AP-029 PG00-D platform blob contract."""
from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from qm_platform.blob import (
    BACKUP_SET_OPEN,
    BackupSetWrite,
    BlobArtifactWrite,
    FilesystemBlobStore,
    PlatformBlobRepository,
    PlatformBlobWriteError,
    validate_checksum_sha256,
    validate_storage_key,
)
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from qm_platform.persistence import postgres_schema as pgs

ROOT = Path(__file__).resolve().parents[2]


def test_migration_chain_includes_blob_artifacts() -> None:
    steps = pgs.discover_migrations()
    assert [step.name for step in steps] == [
        "platform_settings",
        "platform_settings_integrity",
        "organization",
        "audit_events",
        "blob_artifacts",
        "blob_backup_set_org_fk",
    ]
    assert steps[4].version == 5
    assert steps[5].version == 6
    assert steps[5].name == "blob_backup_set_org_fk"
    assert len(steps[4].checksum) == 64


def test_blob_migration_grants_expected_runtime_privileges() -> None:
    sql = (
        pgs.MIGRATIONS_DIR / "0005_blob_artifacts.sql"
    ).read_text(encoding="utf-8").lower()
    assert "create table platform.backup_sets" in sql
    assert "create table platform.blob_artifacts" in sql
    assert "backup_set_id" in sql
    assert "checksum_sha256" in sql
    assert "grant select, insert on table platform.backup_sets to qmtool_runtime" in sql
    assert "grant select, insert, update on table platform.blob_artifacts to qmtool_runtime" in sql
    assert "grant delete" not in sql


def test_packaging_includes_blob_artifacts_migration() -> None:
    text = (ROOT / "packaging/build_onedir.py").read_text(encoding="utf-8")
    assert "qm_platform/persistence/postgres/migrations/0005_blob_artifacts.sql" in text
    assert "qm_platform/persistence/postgres/migrations/0006_blob_backup_set_org_fk.sql" in text


def test_blob_org_fk_migration_enforces_composite_reference() -> None:
    sql = (
        pgs.MIGRATIONS_DIR / "0006_blob_backup_set_org_fk.sql"
    ).read_text(encoding="utf-8").lower()
    assert "backup_sets_id_org_unique" in sql
    assert "unique (backup_set_id, organization_id)" in sql
    assert "blob_artifacts_backup_set_org_fkey" in sql
    assert "foreign key (backup_set_id, organization_id)" in sql
    assert "references platform.backup_sets (backup_set_id, organization_id)" in sql


def test_validate_storage_key_rejects_traversal() -> None:
    with pytest.raises(PlatformBlobWriteError, match="traversal"):
        validate_storage_key("../secret.bin")
    with pytest.raises(PlatformBlobWriteError, match="relative"):
        validate_storage_key("/absolute/path")


def test_filesystem_blob_store_rejects_escape(tmp_path: Path) -> None:
    store = FilesystemBlobStore(tmp_path / "blob-root")
    with pytest.raises(PlatformBlobWriteError, match="traversal"):
        store.resolve_path("safe/../../outside.bin")


def test_filesystem_blob_store_roundtrip_and_checksum(tmp_path: Path) -> None:
    store = FilesystemBlobStore(tmp_path / "blob-root")
    payload = b"platform-blob-contract"
    checksum = store.write_bytes("artifacts/sample.bin", payload)
    assert checksum == hashlib.sha256(payload).hexdigest()
    assert store.read_bytes("artifacts/sample.bin") == payload


def test_blank_storage_key_fails_before_sql() -> None:
    class _NoSqlConnection:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("validation must run before SQL")

    artifact = BlobArtifactWrite(
        artifact_id=str(uuid4()),
        backup_set_id=str(uuid4()),
        checksum_sha256="a" * 64,
        size_bytes=1,
        media_type="application/octet-stream",
        version_no=1,
        storage_key="  ",
    )
    with pytest.raises(PlatformBlobWriteError):
        PlatformBlobRepository.insert_artifact_on_connection(_NoSqlConnection(), artifact)


def test_invalid_checksum_fails_before_sql() -> None:
    class _NoSqlConnection:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("validation must run before SQL")

    artifact = BlobArtifactWrite(
        artifact_id=str(uuid4()),
        backup_set_id=str(uuid4()),
        checksum_sha256="not-a-checksum",
        size_bytes=1,
        media_type="application/octet-stream",
        version_no=1,
        storage_key="artifacts/sample.bin",
    )
    with pytest.raises(PlatformBlobWriteError):
        PlatformBlobRepository.insert_artifact_on_connection(_NoSqlConnection(), artifact)


def test_backup_set_resolves_installation_organization() -> None:
    backup_set = BackupSetWrite(
        backup_set_id=str(uuid4()),
        status=BACKUP_SET_OPEN,
    )
    assert backup_set.resolved_organization_id() == INSTALLATION_ORGANIZATION_ID


def test_validate_checksum_sha256_normalizes_lowercase() -> None:
    assert validate_checksum_sha256("A" * 64) == "a" * 64
