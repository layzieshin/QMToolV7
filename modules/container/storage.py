"""Backend-only file storage for container artifacts.

The adapter owns physical paths.  Callers supply bytes or a binary stream and
only receive a generated relative storage key; the untrusted original filename
is intentionally retained as metadata only.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from .errors import ContainerError


@dataclass(frozen=True)
class StoredArtifactContent:
    relative_path: str
    content_hash: str
    size_bytes: int


class ArtifactFileStorage:
    def store(self, artifact_uid: str, content: bytes | BinaryIO) -> StoredArtifactContent:
        raise NotImplementedError

    def read(self, relative_path: str, *, expected_hash: str, expected_size: int) -> bytes:
        raise NotImplementedError

    def remove(self, relative_path: str) -> None:
        raise NotImplementedError


class FileSystemArtifactStorage(ArtifactFileStorage):
    def __init__(self, root_path: Path) -> None:
        self._root_path = Path(root_path).resolve()
        self._root_path.mkdir(parents=True, exist_ok=True)

    def store(self, artifact_uid: str, content: bytes | BinaryIO) -> StoredArtifactContent:
        source: BinaryIO = io.BytesIO(content) if isinstance(content, bytes) else content
        relative_path = f"{artifact_uid}/{uuid4().hex}.blob"
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        try:
            with target.open("xb") as handle:
                while chunk := source.read(1024 * 1024):
                    if not isinstance(chunk, bytes):
                        raise ContainerError("container.storage.invalid_stream")
                    handle.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
        except Exception:
            if target.exists():
                target.unlink()
            raise
        return StoredArtifactContent(relative_path, digest.hexdigest(), size)

    def read(self, relative_path: str, *, expected_hash: str, expected_size: int) -> bytes:
        target = self._resolve(relative_path)
        try:
            content = target.read_bytes()
        except OSError as exc:
            raise ContainerError("container.storage.content_missing") from exc
        actual_hash = hashlib.sha256(content).hexdigest()
        if len(content) != expected_size or actual_hash != expected_hash:
            raise ContainerError("container.storage.integrity_failed")
        return content

    def remove(self, relative_path: str) -> None:
        target = self._resolve(relative_path)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise ContainerError("container.storage.cleanup_failed") from exc

    def _resolve(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ContainerError("container.storage.invalid_path")
        resolved = (self._root_path / candidate).resolve()
        if self._root_path != resolved and self._root_path not in resolved.parents:
            raise ContainerError("container.storage.invalid_path")
        return resolved
