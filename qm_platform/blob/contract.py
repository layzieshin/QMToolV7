"""Blob metadata contracts and validation (AP-029 PG00-D)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath

from qm_platform.organization.server_context import resolve_active_organization_id

BACKUP_SET_OPEN = "open"
BACKUP_SET_SEALED = "sealed"

_CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")


class PlatformBlobWriteError(RuntimeError):
    """Raised when platform blob metadata cannot be written safely."""


def validate_checksum_sha256(value: str) -> str:
    normalized = str(value).strip().lower()
    if not _CHECKSUM_RE.fullmatch(normalized):
        raise PlatformBlobWriteError("checksum_sha256 must be 64 lowercase hex digits")
    return normalized


def validate_storage_key(value: str) -> str:
    if not isinstance(value, str):
        raise PlatformBlobWriteError("storage_key must be a string")
    key = value.strip()
    if not key:
        raise PlatformBlobWriteError("storage_key is required")
    if key.startswith(("/", "\\")):
        raise PlatformBlobWriteError("storage_key must be relative")
    parts = PurePosixPath(key.replace("\\", "/")).parts
    if ".." in parts:
        raise PlatformBlobWriteError("storage_key traversal is rejected")
    return key.replace("\\", "/")


@dataclass(frozen=True)
class BackupSetWrite:
    backup_set_id: str
    organization_id: str | None = None
    label: str | None = None
    status: str = BACKUP_SET_OPEN
    created_at: datetime | None = None

    def resolved_organization_id(self) -> str:
        if self.organization_id is not None and str(self.organization_id).strip():
            return resolve_active_organization_id(
                client_organization_id=str(self.organization_id).strip()
            )
        return resolve_active_organization_id()

    def validated_status(self) -> str:
        if self.status not in (BACKUP_SET_OPEN, BACKUP_SET_SEALED):
            raise PlatformBlobWriteError("backup set status is invalid")
        return self.status


@dataclass(frozen=True)
class BlobArtifactWrite:
    artifact_id: str
    backup_set_id: str
    checksum_sha256: str
    size_bytes: int
    media_type: str
    version_no: int
    storage_key: str
    organization_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def resolved_organization_id(self) -> str:
        if self.organization_id is not None and str(self.organization_id).strip():
            return resolve_active_organization_id(
                client_organization_id=str(self.organization_id).strip()
            )
        return resolve_active_organization_id()

    def validated_checksum(self) -> str:
        return validate_checksum_sha256(self.checksum_sha256)

    def validated_storage_key(self) -> str:
        return validate_storage_key(self.storage_key)

    def validated_media_type(self) -> str:
        media_type = str(self.media_type).strip()
        if not media_type:
            raise PlatformBlobWriteError("media_type is required")
        return media_type

    def validated_size_bytes(self) -> int:
        size = int(self.size_bytes)
        if size <= 0:
            raise PlatformBlobWriteError("size_bytes must be positive")
        return size

    def validated_version_no(self) -> int:
        version = int(self.version_no)
        if version <= 0:
            raise PlatformBlobWriteError("version_no must be positive")
        return version


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware UTC")
    return value.astimezone(timezone.utc)
