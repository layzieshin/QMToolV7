"""Filesystem storage for incident artifacts."""
from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredObject:
    storage_key: str
    file_path: Path
    sha256: str
    size_bytes: int
    mime_type: str


class IncidentArtifactStorage:
    def __init__(self, root_path: Path) -> None:
        self._root = root_path
        self._root.mkdir(parents=True, exist_ok=True)

    def store_file_copy(
        self,
        *,
        source_path: Path,
        incident_id: str,
        artifact_type: str,
    ) -> StoredObject:
        ext = source_path.suffix.lower() or ".bin"
        object_id = uuid.uuid4().hex
        storage_key = f"{incident_id}/{artifact_type}/{object_id}{ext}"
        target = self._root / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        data = target.read_bytes()
        mime = "application/pdf" if ext == ".pdf" else "application/octet-stream"
        return StoredObject(
            storage_key=storage_key,
            file_path=target,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            mime_type=mime,
        )

    def write_bytes(
        self,
        *,
        incident_id: str,
        artifact_type: str,
        filename: str,
        data: bytes,
        mime_type: str = "application/pdf",
    ) -> StoredObject:
        ext = Path(filename).suffix or ".pdf"
        object_id = uuid.uuid4().hex
        storage_key = f"{incident_id}/{artifact_type}/{object_id}{ext}"
        target = self._root / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return StoredObject(
            storage_key=storage_key,
            file_path=target,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            mime_type=mime_type,
        )

    def resolve_path(self, storage_key: str) -> Path:
        return self._root / storage_key
