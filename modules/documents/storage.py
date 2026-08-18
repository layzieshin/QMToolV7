from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


_ALLOWED_STORE_SUFFIXES = {".pdf", ".docx", ".dotx", ".doct", ".png"}


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

    def read_bytes(self, storage_key: str) -> bytes:
        raise NotImplementedError

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError


def contained_path(root: Path, key: str) -> Path:
    raw = str(key or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("storage_key is required")
    if raw.startswith("/") or raw.startswith("~"):
        raise ValueError("storage_key escapes documents storage root")
    first = raw.split("/", 1)[0]
    if ":" in first:
        raise ValueError("storage_key escapes documents storage root")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("storage_key escapes documents storage root")
    relative = Path(*parts)
    if relative.is_absolute():
        raise ValueError("storage_key escapes documents storage root")
    root_resolved = root.resolve(strict=False)
    candidate = (root_resolved / relative).resolve(strict=False)
    if not candidate.is_relative_to(root_resolved):
        raise ValueError("storage_key escapes documents storage root")
    return candidate


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
        if ext not in _ALLOWED_STORE_SUFFIXES:
            ext = ""
        object_id = uuid.uuid4().hex
        storage_key = f"objects/{object_id[:2]}/{object_id}{ext}"
        target = self.resolve_storage_key(storage_key)
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

    def resolve_storage_key(self, storage_key: str) -> Path:
        return contained_path(self._root_path, storage_key)

    def read_bytes(self, storage_key: str) -> bytes:
        path = self.resolve_storage_key(storage_key)
        if not path.is_file():
            raise FileNotFoundError(storage_key)
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self.resolve_storage_key(storage_key)
        if path.is_file():
            path.unlink()


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
