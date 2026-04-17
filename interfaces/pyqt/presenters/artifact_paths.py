from __future__ import annotations

from pathlib import Path


def resolve_openable_artifact_paths(*, artifact: object, app_home: Path, artifacts_root: Path) -> list[Path]:
    candidates: list[Path] = []
    metadata = getattr(artifact, "metadata", {}) or {}
    for key in ("absolute_path", "file_path", "path"):
        value = metadata.get(key)
        if not value:
            continue
        raw = Path(value)
        candidate = raw if raw.is_absolute() else app_home / raw
        if _is_allowed_artifact_path(candidate, app_home=app_home, artifacts_root=artifacts_root):
            candidates.append(candidate)
    storage_key = getattr(artifact, "storage_key", None)
    if storage_key:
        storage_path = artifacts_root / storage_key
        if _is_allowed_artifact_path(storage_path, app_home=app_home, artifacts_root=artifacts_root):
            candidates.append(storage_path)
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        token = str(candidate)
        if token in seen:
            continue
        seen.add(token)
        unique.append(candidate)
    return unique


def _is_allowed_artifact_path(candidate: Path, *, app_home: Path, artifacts_root: Path) -> bool:
    try:
        resolved = candidate.resolve(strict=False)
        allowed_app_home = app_home.resolve(strict=False)
        allowed_artifacts_root = artifacts_root.resolve(strict=False)
        return resolved.is_relative_to(allowed_app_home) or resolved.is_relative_to(allowed_artifacts_root)
    except Exception:
        return False
