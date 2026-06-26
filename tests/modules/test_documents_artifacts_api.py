from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from modules.documents.api import DocumentsArtifactsApi
from modules.documents.contracts import ArtifactSourceType, ArtifactType, DocumentArtifact


class _FakeDocumentsService:
    def __init__(self, artifacts: list[DocumentArtifact]) -> None:
        self._artifacts = artifacts

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        return [
            artifact
            for artifact in self._artifacts
            if artifact.document_id == document_id and artifact.version == version
        ]


def _artifact(
    *,
    artifact_id: str,
    artifact_type: ArtifactType,
    storage_key: str,
    metadata: dict[str, str] | None = None,
    is_current: bool = True,
) -> DocumentArtifact:
    return DocumentArtifact(
        artifact_id=artifact_id,
        document_id="DOC-1",
        version=1,
        artifact_type=artifact_type,
        source_type=ArtifactSourceType.GENERATED,
        storage_key=storage_key,
        original_filename=Path(storage_key).name,
        mime_type="application/pdf" if storage_key.lower().endswith(".pdf") else "application/octet-stream",
        sha256="0" * 64,
        size_bytes=1,
        is_current=is_current,
        metadata=metadata or {},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_resolves_storage_key_without_metadata_path(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    artifacts_root = app_home / "storage" / "documents" / "artifacts"
    target = artifacts_root / "DOC-1/v1/RELEASED_PDF/released.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"%PDF-1.4\n")
    api = DocumentsArtifactsApi(
        _FakeDocumentsService([
            _artifact(
                artifact_id="a1",
                artifact_type=ArtifactType.RELEASED_PDF,
                storage_key="DOC-1/v1/RELEASED_PDF/released.pdf",
            )
        ]),
        app_home=app_home,
        artifacts_root=artifacts_root,
    )

    ref = api.get_released_pdf_for_reading("DOC-1", 1)

    assert ref is not None
    assert ref.path == target
    assert ref.exists


def test_rejects_metadata_paths_outside_allowed_roots(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    artifacts_root = app_home / "storage" / "documents" / "artifacts"
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\n")
    inside = artifacts_root / "DOC-1/v1/SOURCE_PDF/source.pdf"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"%PDF-1.4\n")
    api = DocumentsArtifactsApi(
        _FakeDocumentsService([
            _artifact(
                artifact_id="a1",
                artifact_type=ArtifactType.SOURCE_PDF,
                storage_key="DOC-1/v1/SOURCE_PDF/source.pdf",
                metadata={"absolute_path": str(outside)},
            )
        ]),
        app_home=app_home,
        artifacts_root=artifacts_root,
    )

    refs = api.get_openable_artifact_refs(
        "DOC-1",
        1,
        artifact_types=(ArtifactType.SOURCE_PDF,),
        suffixes=(".pdf",),
    )

    assert [ref.path for ref in refs] == [inside]


def test_deduplicates_metadata_and_storage_key_candidates(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    artifacts_root = app_home / "storage" / "documents" / "artifacts"
    target = artifacts_root / "DOC-1/v1/SIGNED_PDF/signed.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"%PDF-1.4\n")
    api = DocumentsArtifactsApi(
        _FakeDocumentsService([
            _artifact(
                artifact_id="a1",
                artifact_type=ArtifactType.SIGNED_PDF,
                storage_key="DOC-1/v1/SIGNED_PDF/signed.pdf",
                metadata={"absolute_path": str(target)},
            )
        ]),
        app_home=app_home,
        artifacts_root=artifacts_root,
    )

    refs = api.get_openable_artifact_refs("DOC-1", 1, artifact_types=(ArtifactType.SIGNED_PDF,))

    assert [ref.path for ref in refs] == [target]


def test_prefers_signed_pdf_for_signature_before_source_pdf(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    artifacts_root = app_home / "storage" / "documents" / "artifacts"
    source = artifacts_root / "DOC-1/v1/SOURCE_PDF/source.pdf"
    signed = artifacts_root / "DOC-1/v1/SIGNED_PDF/signed.pdf"
    source.parent.mkdir(parents=True)
    signed.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF-1.4\nsource\n")
    signed.write_bytes(b"%PDF-1.4\nsigned\n")
    api = DocumentsArtifactsApi(
        _FakeDocumentsService([
            _artifact(artifact_id="source", artifact_type=ArtifactType.SOURCE_PDF, storage_key="DOC-1/v1/SOURCE_PDF/source.pdf"),
            _artifact(artifact_id="signed", artifact_type=ArtifactType.SIGNED_PDF, storage_key="DOC-1/v1/SIGNED_PDF/signed.pdf"),
        ]),
        app_home=app_home,
        artifacts_root=artifacts_root,
    )

    ref = api.get_preferred_pdf_artifact("DOC-1", 1)

    assert ref is not None
    assert ref.artifact_id == "signed"
    assert ref.path == signed


def test_review_approval_transition_requires_signed_pdf(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    artifacts_root = app_home / "storage" / "documents" / "artifacts"
    source = artifacts_root / "DOC-1/v1/SOURCE_PDF/source.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF-1.4\nsource\n")
    api = DocumentsArtifactsApi(
        _FakeDocumentsService([
            _artifact(artifact_id="source", artifact_type=ArtifactType.SOURCE_PDF, storage_key="DOC-1/v1/SOURCE_PDF/source.pdf"),
        ]),
        app_home=app_home,
        artifacts_root=artifacts_root,
    )

    ref = api.get_preferred_pdf_artifact("DOC-1", 1, transition="IN_REVIEW->IN_APPROVAL")

    assert ref is None


def test_get_source_docx_for_conversion(tmp_path: Path) -> None:
    app_home = tmp_path / "app"
    artifacts_root = app_home / "storage" / "documents" / "artifacts"
    docx = artifacts_root / "DOC-1/v1/SOURCE_DOCX/source.docx"
    docx.parent.mkdir(parents=True)
    docx.write_bytes(b"docx")
    api = DocumentsArtifactsApi(
        _FakeDocumentsService([
            _artifact(artifact_id="docx", artifact_type=ArtifactType.SOURCE_DOCX, storage_key="DOC-1/v1/SOURCE_DOCX/source.docx"),
        ]),
        app_home=app_home,
        artifacts_root=artifacts_root,
    )

    ref = api.get_source_docx_for_conversion("DOC-1", 1)

    assert ref is not None
    assert ref.path == docx
