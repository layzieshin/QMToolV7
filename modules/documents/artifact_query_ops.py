from __future__ import annotations

from pathlib import Path

from .contracts import ArtifactType, DocumentArtifact, OpenableArtifactRef


def resolve_openable_artifact_refs(
    *,
    artifact: DocumentArtifact,
    app_home: Path,
    artifacts_root: Path,
    suffixes: tuple[str, ...] = (),
    existing_only: bool = True,
) -> list[OpenableArtifactRef]:
    suffix_filter = tuple(value.lower() for value in suffixes)
    refs: list[OpenableArtifactRef] = []
    seen: set[str] = set()
    for candidate in _candidate_paths(artifact=artifact, app_home=app_home, artifacts_root=artifacts_root):
        if not _is_allowed_artifact_path(candidate, app_home=app_home, artifacts_root=artifacts_root):
            continue
        if suffix_filter and candidate.suffix.lower() not in suffix_filter:
            continue
        exists = candidate.exists()
        if existing_only and not exists:
            continue
        token = str(candidate)
        if token in seen:
            continue
        seen.add(token)
        refs.append(
            OpenableArtifactRef(
                artifact_id=artifact.artifact_id,
                document_id=artifact.document_id,
                version=artifact.version,
                artifact_type=artifact.artifact_type,
                path=candidate,
                is_current=artifact.is_current,
                exists=exists,
            )
        )
    return refs


def sort_artifacts_current_first(artifacts: list[DocumentArtifact]) -> list[DocumentArtifact]:
    return sorted(artifacts, key=lambda artifact: 0 if artifact.is_current else 1)


def preferred_pdf_artifact_types(transition: str | None = None, *, purpose: str = "signature") -> tuple[ArtifactType, ...]:
    transition_key = (transition or "").strip().upper()
    if purpose == "reading":
        return (ArtifactType.RELEASED_PDF,)
    if transition_key in {"IN_REVIEW->IN_APPROVAL", "IN_APPROVAL->APPROVED"}:
        return (ArtifactType.SIGNED_PDF,)
    if transition_key == "EXTEND_VALIDITY":
        return (ArtifactType.SIGNED_PDF, ArtifactType.RELEASED_PDF)
    return (ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF, ArtifactType.RELEASED_PDF)


def _candidate_paths(*, artifact: DocumentArtifact, app_home: Path, artifacts_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for key in ("absolute_path", "file_path", "path"):
        value = artifact.metadata.get(key)
        if not value:
            continue
        raw = Path(value)
        candidates.append(raw if raw.is_absolute() else app_home / raw)
    if artifact.storage_key:
        candidates.append(artifacts_root / artifact.storage_key)
    return candidates


def _is_allowed_artifact_path(candidate: Path, *, app_home: Path, artifacts_root: Path) -> bool:
    try:
        resolved = candidate.resolve(strict=False)
        allowed_app_home = app_home.resolve(strict=False)
        allowed_artifacts_root = artifacts_root.resolve(strict=False)
        return resolved.is_relative_to(allowed_app_home) or resolved.is_relative_to(allowed_artifacts_root)
    except Exception:
        return False
