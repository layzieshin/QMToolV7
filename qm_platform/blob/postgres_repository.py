"""PostgreSQL metadata writer for platform blob artifacts (AP-029 PG00-D)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import psycopg

from .contract import (
    BackupSetWrite,
    BlobArtifactWrite,
    PlatformBlobWriteError,
    as_utc,
)

_BACKUP_SET_INSERT_SQL = """
INSERT INTO platform.backup_sets (
    backup_set_id, organization_id, label, status, created_at
) VALUES (
    %s::uuid, %s, %s, %s, %s
)
"""

_BLOB_INSERT_SQL = """
INSERT INTO platform.blob_artifacts (
    artifact_id, organization_id, backup_set_id,
    checksum_sha256, size_bytes, media_type, version_no,
    storage_key, created_at, updated_at
) VALUES (
    %s::uuid, %s, %s::uuid,
    %s, %s, %s, %s,
    %s, %s, %s
)
"""

_BLOB_UPDATE_SQL = """
UPDATE platform.blob_artifacts
SET checksum_sha256 = %s,
    size_bytes = %s,
    media_type = %s,
    version_no = %s,
    updated_at = %s
WHERE artifact_id = %s::uuid
"""


class PlatformBlobRepository:
    """Runtime metadata writes on an existing PostgreSQL connection."""

    @staticmethod
    def insert_backup_set_on_connection(
        conn: psycopg.Connection,
        backup_set: BackupSetWrite,
    ) -> str:
        try:
            backup_set_id = backup_set.backup_set_id or str(uuid4())
            created_at = as_utc(backup_set.created_at or datetime.now(timezone.utc))
            cursor = conn.execute(
                _BACKUP_SET_INSERT_SQL,
                (
                    backup_set_id,
                    backup_set.resolved_organization_id(),
                    backup_set.label,
                    backup_set.validated_status(),
                    created_at,
                ),
            )
        except PlatformBlobWriteError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PlatformBlobWriteError("platform backup set unavailable") from exc
        if int(cursor.rowcount or 0) <= 0:
            raise PlatformBlobWriteError("platform backup set unavailable")
        return backup_set_id

    @staticmethod
    def insert_artifact_on_connection(
        conn: psycopg.Connection,
        artifact: BlobArtifactWrite,
    ) -> str:
        try:
            artifact_id = artifact.artifact_id or str(uuid4())
            now = as_utc(artifact.created_at or datetime.now(timezone.utc))
            updated_at = as_utc(artifact.updated_at or now)
            cursor = conn.execute(
                _BLOB_INSERT_SQL,
                (
                    artifact_id,
                    artifact.resolved_organization_id(),
                    artifact.backup_set_id,
                    artifact.validated_checksum(),
                    artifact.validated_size_bytes(),
                    artifact.validated_media_type(),
                    artifact.validated_version_no(),
                    artifact.validated_storage_key(),
                    now,
                    updated_at,
                ),
            )
        except PlatformBlobWriteError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PlatformBlobWriteError("platform blob metadata unavailable") from exc
        if int(cursor.rowcount or 0) <= 0:
            raise PlatformBlobWriteError("platform blob metadata unavailable")
        return artifact_id

    @staticmethod
    def update_artifact_on_connection(
        conn: psycopg.Connection,
        artifact: BlobArtifactWrite,
    ) -> str:
        try:
            updated_at = as_utc(artifact.updated_at or datetime.now(timezone.utc))
            cursor = conn.execute(
                _BLOB_UPDATE_SQL,
                (
                    artifact.validated_checksum(),
                    artifact.validated_size_bytes(),
                    artifact.validated_media_type(),
                    artifact.validated_version_no(),
                    updated_at,
                    artifact.artifact_id,
                ),
            )
        except PlatformBlobWriteError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PlatformBlobWriteError("platform blob metadata unavailable") from exc
        if int(cursor.rowcount or 0) <= 0:
            raise PlatformBlobWriteError("platform blob metadata unavailable")
        return artifact.artifact_id
