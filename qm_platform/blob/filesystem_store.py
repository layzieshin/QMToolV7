"""Backend-only filesystem blob store with traversal rejection (AP-029 PG00-D)."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .contract import PlatformBlobWriteError, validate_storage_key


class FilesystemBlobStore:
    """Write/read opaque blob bytes under a single backend-managed root."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def resolve_path(self, storage_key: str) -> Path:
        key = validate_storage_key(storage_key)
        candidate = (self._root / Path(key)).resolve()
        root_with_sep = os.path.join(str(self._root), "")
        resolved = str(candidate)
        if resolved != str(self._root) and not resolved.startswith(root_with_sep):
            raise PlatformBlobWriteError("storage_key escapes blob root")
        return candidate

    def write_bytes(self, storage_key: str, payload: bytes) -> str:
        if not payload:
            raise PlatformBlobWriteError("blob payload must not be empty")
        target = self.resolve_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return hashlib.sha256(payload).hexdigest()

    def read_bytes(self, storage_key: str) -> bytes:
        target = self.resolve_path(storage_key)
        if not target.is_file():
            raise PlatformBlobWriteError("blob payload is missing")
        return target.read_bytes()
