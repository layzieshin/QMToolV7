from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.documents.contracts import ArtifactType, DocumentStatus, SystemRole, ValidityExtensionOutcome, WorkflowProfile
from modules.documents.profile_store import WorkflowProfileStoreJSON
from modules.documents.service import DocumentsService
from modules.documents.sqlite_repository import SQLiteDocumentsRepository
from modules.documents.storage import FileSystemDocumentsStorage
from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        output_pdf = getattr(request, "output_pdf", None)
        if isinstance(output_pdf, Path):
            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            output_pdf.write_bytes(b"%PDF-1.4\n%fake-signed\n")
        return request


class _FakeAuditLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str, str]] = []

    def emit(self, action: str, actor: str, target: str, result: str, reason: str = "") -> None:
        self.calls.append((action, actor, target, result, reason))


class DocumentsInfrastructureTest(unittest.TestCase):
    def test_profile_store_loads_default_profiles(self) -> None:
        file_path = Path("modules/documents/workflow_profiles.json")
        store = WorkflowProfileStoreJSON(file_path)
        profile = store.get("long_release")
        self.assertEqual(profile.profile_id, "long_release")
        self.assertTrue(profile.four_eyes_required)

    def test_sqlite_repository_persists_and_lists_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "documents.db"
            schema_path = Path("modules/documents/schema.sql")
            repo = SQLiteDocumentsRepository(db_path=db_path, schema_path=schema_path)
            service = DocumentsService(repository=repo, signature_api=_FakeSignatureApi())

            planned = service.create_document_version("DOC-PERSIST-1", 1)
            approved = service.create_document_version("DOC-PERSIST-2", 1)
            approved = service.assign_workflow_roles(
                approved,
                editors={"ed"},
                reviewers={"rv"},
                approvers={"ap"},
            )
            approved = service.start_workflow(approved, WorkflowProfile.long_release_path())
            approved = service.complete_editing(approved, sign_request={"step": "edit_complete"})
            approved = service.accept_review(approved, "rv", sign_request={"step": "review_accept"})
            approved = service.accept_approval(approved, "ap", sign_request={"step": "approve"})

            self.assertEqual(planned.status, DocumentStatus.PLANNED)
            entries = service.list_by_status(DocumentStatus.APPROVED)
            self.assertEqual([(e.document_id, e.version) for e in entries], [("DOC-PERSIST-2", 1)])

    def test_intake_creates_immutable_artifact_registry_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "documents.db"
            schema_path = Path("modules/documents/schema.sql")
            storage = FileSystemDocumentsStorage(root / "artifacts")
            repo = SQLiteDocumentsRepository(db_path=db_path, schema_path=schema_path)
            service = DocumentsService(repository=repo, storage_port=storage, signature_api=_FakeSignatureApi())

            source_docx = root / "source.docx"
            source_docx.write_bytes(b"docx-content")
            state = service.import_existing_docx(
                "DOC-INTAKE",
                1,
                source_docx,
                actor_user_id="admin",
                actor_role=SystemRole.ADMIN,
            )
            self.assertEqual(state.status, DocumentStatus.PLANNED)

            newer_docx = root / "source-new.docx"
            newer_docx.write_bytes(b"docx-content-new")
            service.import_existing_docx(
                "DOC-INTAKE",
                1,
                newer_docx,
                actor_user_id="admin",
                actor_role=SystemRole.ADMIN,
            )

            artifacts = service.list_artifacts("DOC-INTAKE", 1)
            docx_artifacts = [a for a in artifacts if a.artifact_type == ArtifactType.SOURCE_DOCX]
            self.assertEqual(len(docx_artifacts), 2)
            self.assertEqual(sum(1 for a in docx_artifacts if a.is_current), 1)

    def test_complete_editing_generates_source_pdf_from_docx_and_marks_current(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="qmtool-docs-infra-"))
        db_path = root / "documents.db"
        schema_path = Path("modules/documents/schema.sql")
        storage = FileSystemDocumentsStorage(root / "artifacts")
        repo = SQLiteDocumentsRepository(db_path=db_path, schema_path=schema_path)
        audit = _FakeAuditLogger()

        def _fake_docx_to_pdf(source: Path, target: Path) -> None:
            target.write_bytes(b"%PDF-1.4\n%fake\n")

        service = DocumentsService(
            repository=repo,
            storage_port=storage,
            signature_api=_FakeSignatureApi(),
            audit_logger=audit,
            docx_to_pdf_converter=_fake_docx_to_pdf,
        )

        source_docx = root / "workflow.docx"
        source_docx.write_bytes(b"docx-content")
        state = service.import_existing_docx(
            "DOC-WF",
            1,
            source_docx,
            actor_user_id="admin",
            actor_role=SystemRole.ADMIN,
        )
        state = service.assign_workflow_roles(state, editors={"ed"}, reviewers={"rv"}, approvers={"ap"})
        state = service.start_workflow(state, WorkflowProfile.long_release_path())
        service.complete_editing(state, sign_request={"step": "edit_complete"})

        artifacts = service.list_artifacts("DOC-WF", 1)
        source_pdfs = [a for a in artifacts if a.artifact_type == ArtifactType.SOURCE_PDF]
        self.assertGreaterEqual(len(source_pdfs), 1)
        self.assertEqual(sum(1 for a in source_pdfs if a.is_current), 1)
        self.assertTrue(any(call[0] == "documents.artifact.source_pdf.generated" for call in audit.calls))

    def test_complete_editing_persists_signed_pdf_for_followup_phases(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="qmtool-docs-sign-"))
        db_path = root / "documents.db"
        schema_path = Path("modules/documents/schema.sql")
        storage = FileSystemDocumentsStorage(root / "artifacts")
        repo = SQLiteDocumentsRepository(db_path=db_path, schema_path=schema_path)

        def _fake_docx_to_pdf(_source: Path, target: Path) -> None:
            target.write_bytes(b"%PDF-1.4\n%source\n")

        service = DocumentsService(
            repository=repo,
            storage_port=storage,
            signature_api=_FakeSignatureApi(),
            docx_to_pdf_converter=_fake_docx_to_pdf,
        )

        source_docx = root / "review.docx"
        source_docx.write_bytes(b"docx-review")
        state = service.import_existing_docx(
            "DOC-SIGNED",
            1,
            source_docx,
            actor_user_id="admin",
            actor_role=SystemRole.ADMIN,
        )
        state = service.assign_workflow_roles(state, editors={"ed"}, reviewers={"rv"}, approvers={"ap"})
        state = service.start_workflow(state, WorkflowProfile.long_release_path())
        source_pdf = service.ensure_source_pdf_for_signing(state)
        self.assertIsNotNone(source_pdf)
        sign_request = SignRequest(
            input_pdf=Path(source_pdf),
            output_pdf=root / "signed-in-progress.pdf",
            signature_png=None,
            placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
            layout=LabelLayoutInput(show_signature=False, show_name=True, show_date=True),
            overwrite_output=True,
            dry_run=False,
            sign_mode="visual",
            signer_user="ed",
            password="secret",
            reason="test-transition",
        )
        service.complete_editing(state, sign_request=sign_request)

        artifacts = service.list_artifacts("DOC-SIGNED", 1)
        signed_pdfs = [a for a in artifacts if a.artifact_type == ArtifactType.SIGNED_PDF]
        self.assertGreaterEqual(len(signed_pdfs), 1)
        self.assertEqual(sum(1 for a in signed_pdfs if a.is_current), 1)

    def test_approval_freezes_distribution_snapshot_into_custom_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "documents.db"
            schema_path = Path("modules/documents/schema.sql")
            repo = SQLiteDocumentsRepository(db_path=db_path, schema_path=schema_path)
            service = DocumentsService(repository=repo, signature_api=_FakeSignatureApi())

            state = service.create_document_version("DOC-DIST", 1, owner_user_id="owner-1")
            service.update_document_header(
                "DOC-DIST",
                distribution_roles=["QMB", "USER"],
                distribution_sites=["HQ"],
                distribution_departments=["QA"],
                actor_user_id="admin",
                actor_role=SystemRole.ADMIN,
            )
            state = service.assign_workflow_roles(
                state,
                editors={"editor-1"},
                reviewers={"rev-1"},
                approvers={"app-1"},
            )
            state = service.start_workflow(state, WorkflowProfile.long_release_path())
            state = service.complete_editing(state, sign_request={"step": "edit_complete"})
            state = service.accept_review(state, "rev-1", sign_request={"step": "review_accept"})
            state = service.accept_approval(state, "app-1", sign_request={"step": "approve"})
            snapshot = state.custom_fields.get("distribution_snapshot")
            self.assertIsInstance(snapshot, dict)
            if isinstance(snapshot, dict):
                self.assertEqual(snapshot.get("roles"), ["QMB", "USER"])
                self.assertEqual(snapshot.get("sites"), ["HQ"])
                self.assertEqual(snapshot.get("departments"), ["QA"])

    def test_sqlite_roundtrip_persists_validity_extension_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SQLiteDocumentsRepository(db_path=root / "documents.db", schema_path=Path("modules/documents/schema.sql"))
            service = DocumentsService(repository=repo, signature_api=_FakeSignatureApi())
            state = service.create_document_version("DOC-EXT-SQL", 1, owner_user_id="owner-1")
            state = service.assign_workflow_roles(state, editors={"e"}, reviewers={"r"}, approvers={"a"})
            state = service.start_workflow(state, WorkflowProfile.long_release_path())
            state = service.complete_editing(state, sign_request={"step": "edit_complete"})
            state = service.accept_review(state, "r", sign_request={"step": "review_accept"})
            state = service.accept_approval(state, "a", sign_request={"step": "approve"})
            extended, _ = service.extend_annual_validity(
                state,
                actor_user_id="qmb-1",
                signature_present=True,
                duration_days=120,
                reason="Audit ohne Befund",
                review_outcome=ValidityExtensionOutcome.UNCHANGED,
            )
            loaded = repo.get("DOC-EXT-SQL", 1)
            assert loaded is not None
            self.assertEqual(loaded.last_extended_by, "qmb-1")
            self.assertEqual(loaded.last_extension_reason, "Audit ohne Befund")
            self.assertEqual(loaded.last_extension_review_outcome, ValidityExtensionOutcome.UNCHANGED.value)
            self.assertEqual(loaded.extension_count, extended.extension_count)


if __name__ == "__main__":
    unittest.main()

