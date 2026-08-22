"""Live PostgreSQL checks for AP-029 PG00-D platform blob contract."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest

from qm_platform.blob import (
    BACKUP_SET_OPEN,
    BackupSetWrite,
    BlobArtifactWrite,
    PlatformBlobRepository,
    PlatformBlobWriteError,
)
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from qm_platform.persistence import postgres_schema as pgs
from tests.platform.test_postgres_schema_live import _prepare_platform_schema
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres


def _read_artifact(migrator_dsn: str, artifact_id: str) -> dict:
    with psycopg.connect(migrator_dsn, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        row = conn.execute(
            """
            SELECT artifact_id::text AS artifact_id,
                   organization_id,
                   backup_set_id::text AS backup_set_id,
                   checksum_sha256,
                   size_bytes,
                   media_type,
                   version_no,
                   storage_key
            FROM platform.blob_artifacts
            WHERE artifact_id = %s::uuid
            """,
            (artifact_id,),
        ).fetchone()
    assert row is not None
    return dict(row)


@pytest.fixture
def platform_env(live_postgres_env: LivePostgresEnv) -> LivePostgresEnv:
    _prepare_platform_schema(live_postgres_env)
    pgs.migrate_platform_schema(live_postgres_env.migrator_dsn)
    yield live_postgres_env


def test_runtime_can_insert_blob_metadata_but_not_delete(platform_env: LivePostgresEnv) -> None:
    backup_set_id = str(uuid4())
    artifact_id = str(uuid4())
    now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)

    with psycopg.connect(platform_env.runtime_dsn) as runtime:
        runtime.execute("SET ROLE qmtool_runtime")
        PlatformBlobRepository.insert_backup_set_on_connection(
            runtime,
            BackupSetWrite(
                backup_set_id=backup_set_id,
                status=BACKUP_SET_OPEN,
                created_at=now,
            ),
        )
        PlatformBlobRepository.insert_artifact_on_connection(
            runtime,
            BlobArtifactWrite(
                artifact_id=artifact_id,
                backup_set_id=backup_set_id,
                checksum_sha256="b" * 64,
                size_bytes=12,
                media_type="application/octet-stream",
                version_no=1,
                storage_key="artifacts/live-sample.bin",
                created_at=now,
                updated_at=now,
            ),
        )
        runtime.commit()
        with pytest.raises(Exception):
            runtime.execute(
                "DELETE FROM platform.blob_artifacts WHERE artifact_id=%s::uuid",
                (artifact_id,),
            )
            runtime.commit()
        runtime.rollback()

    row = _read_artifact(platform_env.migrator_dsn, artifact_id)
    assert row["organization_id"] == INSTALLATION_ORGANIZATION_ID
    assert row["backup_set_id"] == backup_set_id
    assert row["checksum_sha256"] == "b" * 64
    assert row["storage_key"] == "artifacts/live-sample.bin"


def test_runtime_update_is_allowed_for_blob_metadata(platform_env: LivePostgresEnv) -> None:
    backup_set_id = str(uuid4())
    artifact_id = str(uuid4())
    now = datetime(2026, 8, 22, 12, 5, tzinfo=timezone.utc)

    with psycopg.connect(platform_env.runtime_dsn) as runtime:
        runtime.execute("SET ROLE qmtool_runtime")
        PlatformBlobRepository.insert_backup_set_on_connection(
            runtime,
            BackupSetWrite(backup_set_id=backup_set_id, created_at=now),
        )
        PlatformBlobRepository.insert_artifact_on_connection(
            runtime,
            BlobArtifactWrite(
                artifact_id=artifact_id,
                backup_set_id=backup_set_id,
                checksum_sha256="c" * 64,
                size_bytes=4,
                media_type="application/octet-stream",
                version_no=1,
                storage_key="artifacts/update-me.bin",
                created_at=now,
                updated_at=now,
            ),
        )
        PlatformBlobRepository.update_artifact_on_connection(
            runtime,
            BlobArtifactWrite(
                artifact_id=artifact_id,
                backup_set_id=backup_set_id,
                checksum_sha256="d" * 64,
                size_bytes=8,
                media_type="application/pdf",
                version_no=2,
                storage_key="ignored-on-update",
                updated_at=datetime(2026, 8, 22, 12, 6, tzinfo=timezone.utc),
            ),
        )
        runtime.commit()

    row = _read_artifact(platform_env.migrator_dsn, artifact_id)
    assert row["checksum_sha256"] == "d" * 64
    assert row["size_bytes"] == 8
    assert row["media_type"] == "application/pdf"
    assert row["version_no"] == 2


def test_runtime_cannot_insert_backup_set_with_bad_organization(platform_env: LivePostgresEnv) -> None:
    with psycopg.connect(platform_env.runtime_dsn) as runtime:
        runtime.execute("SET ROLE qmtool_runtime")
        with pytest.raises(PlatformBlobWriteError):
            PlatformBlobRepository.insert_backup_set_on_connection(
                runtime,
                BackupSetWrite(
                    backup_set_id=str(uuid4()),
                    organization_id="00000000-0000-4000-8000-000000009999",
                ),
            )
