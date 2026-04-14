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


class DocumentsStoragePort:
    def store_file_copy(
        self,
        *,
        source_path: Path,
        document_id: str,
        version: int,
        artifact_type: str,
    ) -> StoredObject:
        raise NotImplementedError


class FileSystemDocumentsStorage(DocumentsStoragePort):
    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path
        self._root_path.mkdir(parents=True, exist_ok=True)

    def store_file_copy(
        self,
        *,
        source_path: Path,
        document_id: str,
        version: int,
        artifact_type: str,
    ) -> StoredObject:
        ext = source_path.suffix.lower()
        object_id = uuid.uuid4().hex
        storage_key = f"{document_id}/v{version}/{artifact_type}/{object_id}{ext}"
        target = self._root_path / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        data = target.read_bytes()
        return StoredObject(
            storage_key=storage_key,
            file_path=target,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            mime_type=_guess_mime(ext),
        )


def _guess_mime(ext: str) -> str:
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if ext == ".dotx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.template"
    if ext == ".doct":
        return "application/octet-stream"
    return "application/octet-stream"

