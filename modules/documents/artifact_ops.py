"""Artifact operations for documents module.

Internal module — extracted from service.py (Phase 4A).
Covers: artifact creation, path resolution, PDF conversion, release PDF generation.
"""
from __future__ import annotations

import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .contracts import (
    ArtifactSourceType,
    ArtifactType,
    DocumentArtifact,
    DocumentVersionState,
)
from .errors import ValidationError
from .repository import DocumentsRepository
from .storage import DocumentsStoragePort

from typing import Callable


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def resolve_artifact_path(artifact: DocumentArtifact, storage_port: DocumentsStoragePort | None) -> Path | None:
    for key in ("absolute_path", "file_path", "path"):
        value = artifact.metadata.get(key)
        if value:
            candidate = Path(value)
            if candidate.exists():
                return candidate
    root = getattr(storage_port, "_root_path", None)
    if isinstance(root, Path):
        return root / artifact.storage_key
    return None


def resolve_source_pdf_path(
    state: DocumentVersionState,
    repository: DocumentsRepository | None,
    storage_port: DocumentsStoragePort | None,
) -> Path | None:
    if repository is None:
        return None
    artifacts = repository.list_artifacts(state.document_id, state.version)
    for artifact in sorted(artifacts, key=lambda item: 0 if item.is_current else 1):
        if artifact.artifact_type != ArtifactType.SOURCE_PDF:
            continue
        resolved = resolve_artifact_path(artifact, storage_port)
        if resolved is not None and resolved.exists() and resolved.suffix.lower() == ".pdf":
            return resolved
    return None


def resolve_source_docx_path(
    state: DocumentVersionState,
    repository: DocumentsRepository | None,
    storage_port: DocumentsStoragePort | None,
) -> Path | None:
    if repository is None:
        return None
    artifacts = repository.list_artifacts(state.document_id, state.version)
    for artifact in sorted(artifacts, key=lambda item: 0 if item.is_current else 1):
        if artifact.artifact_type != ArtifactType.SOURCE_DOCX:
            continue
        resolved = resolve_artifact_path(artifact, storage_port)
        if resolved is not None and resolved.exists() and resolved.suffix.lower() == ".docx":
            return resolved
    return None


def convert_docx_to_temp_pdf(
    state: DocumentVersionState,
    source_docx: Path,
    docx_to_pdf_converter: Callable[[Path, Path], None] | None = None,
) -> Path:
    output_name = f"{state.document_id}_{state.version}_source.pdf"
    with tempfile.TemporaryDirectory(prefix="qmtool-docx2pdf-") as tmp_dir:
        out_path = Path(tmp_dir) / output_name
        try:
            if docx_to_pdf_converter is not None:
                docx_to_pdf_converter(source_docx, out_path)
            else:
                try:
                    from docx2pdf import convert
                except ImportError as exc:
                    raise ValidationError(
                        "docx2pdf is required to convert SOURCE_DOCX before editing completion"
                    ) from exc
                convert(str(source_docx), str(out_path))
            if not out_path.exists() or out_path.stat().st_size == 0:
                raise ValidationError(f"docx to pdf conversion produced no output: {source_docx}")
            persisted = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}_source.pdf"
            shutil.copy2(out_path, persisted)
            return persisted
        except Exception as exc:
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(f"docx to pdf conversion failed: {exc}") from exc


def create_artifact(
    *,
    state: DocumentVersionState,
    source_path: Path,
    artifact_type: ArtifactType,
    source_type: ArtifactSourceType,
    metadata: dict[str, str],
    repository: DocumentsRepository,
    storage_port: DocumentsStoragePort,
) -> DocumentArtifact:
    stored = storage_port.store_file_copy(
        source_path=source_path,
        document_id=state.document_id,
        version=state.version,
        artifact_type=artifact_type.value,
    )
    artifact = DocumentArtifact(
        artifact_id=uuid.uuid4().hex,
        document_id=state.document_id,
        version=state.version,
        artifact_type=artifact_type,
        source_type=source_type,
        storage_key=stored.storage_key,
        original_filename=source_path.name,
        mime_type=stored.mime_type,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        is_current=True,
        metadata=metadata,
        created_at=_utcnow(),
    )
    repository.add_artifact(artifact)
    repository.mark_current_artifact(
        document_id=state.document_id,
        version=state.version,
        artifact_type=artifact_type,
        artifact_id=artifact.artifact_id,
    )
    return artifact


def protect_pdf_copy(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.constants import UserAccessPermissions

        reader = PdfReader(str(source_path))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(
            user_password="",
            owner_password=uuid.uuid4().hex,
            permissions_flag=UserAccessPermissions.PRINT,
        )
        with target_path.open("wb") as fh:
            writer.write(fh)
    except Exception:
        shutil.copy2(source_path, target_path)


def resolve_release_pdf_source_path(
    state: DocumentVersionState,
    repository: DocumentsRepository,
    storage_port: DocumentsStoragePort | None,
) -> Path | None:
    artifacts = repository.list_artifacts(state.document_id, state.version)
    priorities = [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF, ArtifactType.RELEASED_PDF]
    ordered = sorted(artifacts, key=lambda item: (0 if item.is_current else 1, item.created_at), reverse=False)
    for artifact_type in priorities:
        current_candidates = [a for a in ordered if a.artifact_type == artifact_type and a.is_current]
        for artifact in current_candidates:
            resolved = resolve_artifact_path(artifact, storage_port)
            if resolved is not None and resolved.exists() and resolved.suffix.lower() == ".pdf":
                return resolved
    for artifact_type in priorities:
        fallback_candidates = [a for a in ordered if a.artifact_type == artifact_type]
        for artifact in reversed(fallback_candidates):
            resolved = resolve_artifact_path(artifact, storage_port)
            if resolved is not None and resolved.exists() and resolved.suffix.lower() == ".pdf":
                return resolved
    return None

