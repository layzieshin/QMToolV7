"""Read-only residual settings archive with DB-anchored SHA-256 integrity (J02 Bucket C)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .atomic_io import atomic_write_bytes, atomic_write_text
from .errors import (
    ResidualArchiveIntegrityError,
    ResidualPolicyInvalidError,
    ResidualPolicyMissingError,
    ResidualPolicyUnknownError,
)
from .key_classification import SettingKeyRef, classify_key, SettingBucket
from .residual_allowlist import residual_allowlist_keys


RESIDUAL_ARCHIVE_REL = "storage/platform/settings_residual_archive/settings.json"
RESIDUAL_HASH_REL = "storage/platform/settings_residual_archive/settings.json.sha256"


def _schema_type_ok(value: Any, expected: str | None) -> bool:
    if expected is None:
        return True
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


@dataclass
class ResidualSettingsStore:
    """Loads allowlisted Bucket-C keys from a byte-archived settings.json.

    ``expected_sha256`` must come from ``platform_settings_integrity``. The sidecar
    ``settings.json.sha256`` is only a backup convenience.
    """

    archive_path: Path
    hash_path: Path
    expected_sha256: str | None = None

    @classmethod
    def under_app_home(
        cls,
        app_home: Path,
        *,
        expected_sha256: str | None = None,
    ) -> ResidualSettingsStore:
        return cls(
            archive_path=app_home / RESIDUAL_ARCHIVE_REL,
            hash_path=app_home / RESIDUAL_HASH_REL,
            expected_sha256=expected_sha256,
        )

    def exists(self) -> bool:
        return self.archive_path.is_file()

    def sha256(self) -> str:
        return hashlib.sha256(self.archive_path.read_bytes()).hexdigest()

    def verify(self) -> str:
        if not self.archive_path.is_file():
            raise ResidualArchiveIntegrityError("residual archive missing")
        digest = self.sha256()
        if self.expected_sha256 is None:
            raise ResidualArchiveIntegrityError(
                "residual archive hash is not DB-anchored; refusing sidecar-only trust"
            )
        if digest != self.expected_sha256:
            raise ResidualArchiveIntegrityError(
                f"residual archive sha256 mismatch: expected={self.expected_sha256} actual={digest}"
            )
        return digest

    def load_raw(self) -> dict[str, Any]:
        self.verify()
        payload = json.loads(self.archive_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ResidualArchiveIntegrityError("residual archive root must be an object")
        return payload

    def load_policy_module(self, module_id: str) -> dict[str, Any]:
        payload = self.load_raw()
        module_blob = payload.get(module_id, {})
        if not isinstance(module_blob, dict):
            return {}
        allowed = residual_allowlist_keys()
        out: dict[str, Any] = {}
        for key, value in module_blob.items():
            ref = SettingKeyRef(module_id, str(key))
            if ref in allowed:
                out[str(key)] = value
        return out

    def list_policy_keys(self) -> set[tuple[str, str]]:
        if not self.exists():
            return set()
        payload = self.load_raw()
        allowed = residual_allowlist_keys()
        found: set[tuple[str, str]] = set()
        for module_id, blob in payload.items():
            if not isinstance(blob, dict):
                continue
            for key in blob:
                ref = SettingKeyRef(str(module_id), str(key))
                if ref in allowed:
                    found.add(ref.as_tuple())
        return found

    def assert_complete_against_expected(
        self,
        expected_by_module: Mapping[str, tuple[str, ...]],
        *,
        schema_by_module: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Fail-closed completeness + unknown + basic schema type checks."""
        payload = self.load_raw()
        allowed = residual_allowlist_keys()
        schema_by_module = schema_by_module or {}

        for module_id, blob in payload.items():
            if not isinstance(blob, dict):
                raise ResidualPolicyInvalidError(
                    f"residual module payload must be an object: {module_id}"
                )
            for key in blob:
                ref = SettingKeyRef(str(module_id), str(key))
                if classify_key(str(module_id), str(key)) is not SettingBucket.RESIDUAL_POLICY:
                    raise ResidualPolicyUnknownError(
                        f"residual archive contains non-C or unknown key: {module_id}.{key}"
                    )
                if ref not in allowed:
                    raise ResidualPolicyUnknownError(
                        f"residual archive contains key outside allowlist: {module_id}.{key}"
                    )

        missing: list[str] = []
        for module_id, keys in expected_by_module.items():
            blob = payload.get(module_id)
            if blob is None:
                missing.extend(f"{module_id}.{key}" for key in keys)
                continue
            if not isinstance(blob, dict):
                raise ResidualPolicyInvalidError(
                    f"residual module payload must be an object: {module_id}"
                )
            props = ((schema_by_module.get(module_id) or {}).get("properties") or {})
            for key in keys:
                if key not in blob:
                    missing.append(f"{module_id}.{key}")
                    continue
                expected_type = (props.get(key) or {}).get("type") if isinstance(props.get(key), dict) else None
                if not _schema_type_ok(blob[key], expected_type):
                    raise ResidualPolicyInvalidError(
                        f"residual value type invalid for {module_id}.{key}"
                    )
        if missing:
            raise ResidualPolicyMissingError(
                "residual archive missing required Bucket-C keys: " + ", ".join(sorted(missing))
            )


def write_residual_archive_bytes(app_home: Path, raw: bytes) -> tuple[Path, str]:
    """Atomically write residual archive bytes and a non-authoritative sidecar hash."""
    digest = hashlib.sha256(raw).hexdigest()
    store = ResidualSettingsStore.under_app_home(app_home)
    atomic_write_bytes(store.archive_path, raw)
    atomic_write_text(store.hash_path, f"{digest}  settings.json\n")
    return store.archive_path, digest


def archive_settings_json(source: Path, app_home: Path) -> tuple[Path, str]:
    """Byte-copy source settings.json into residual archive (atomic)."""
    return write_residual_archive_bytes(app_home, source.read_bytes())
