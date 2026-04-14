from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet


class EncryptedTrainingBlobStore:
    def __init__(self, root: Path, key_file: Path) -> None:
        self._root = root
        self._key_file = key_file
        self._root.mkdir(parents=True, exist_ok=True)
        self._key_file.parent.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(self._load_or_create_key())

    def put_bytes(self, payload: bytes, extension: str = ".json") -> str:
        ext = extension if extension.startswith(".") else f".{extension}"
        storage_key = f"{uuid4().hex}{ext}.enc"
        target = self._root / storage_key
        target.write_bytes(self._fernet.encrypt(payload))
        return storage_key

    def get_bytes(self, storage_key: str) -> bytes:
        source = self._root / storage_key
        return self._fernet.decrypt(source.read_bytes())

    def _load_or_create_key(self) -> bytes:
        if self._key_file.exists():
            return self._key_file.read_bytes()
        key = Fernet.generate_key()
        self._key_file.write_bytes(key)
        return key
