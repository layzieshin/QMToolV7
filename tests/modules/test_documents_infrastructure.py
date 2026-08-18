from __future__ import annotations

import inspect
import sqlite3
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from modules.documents.contracts import (
    ArtifactSourceType,
    ArtifactType,
    ControlClass,
    DocumentArtifact,
    DocumentStatus,
    SystemRole,
    ValidityExtensionOutcome,
    WorkflowProfile,
)
from modules.documents.artifact_ops import resolve_artifact_path
from modules.documents.errors import DocumentConflictError
from modules.documents.service import DocumentsService
from modules.documents.storage import FileSystemDocumentsStorage, contained_path
from modules.documents.workflow_profile_seed_reader import WorkflowProfileSeedReader
from modules.documents.workflow_profile_store import WorkflowProfileRelationalStore
from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput
from tests.database_helpers import make_docs_repository as SQLiteDocumentsRepository
from tests.database_helpers import make_documents_service_with_profiles


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        output_pdf = getattr(request, "output_pdf", None)
        if isinstance(output_pdf, Path):
            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            output_pdf.write_bytes(b"%PDF-1.4\n%fake-signed\n")
        return request


class _ChainSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        input_pdf = getattr(request, "input_pdf", None)
        output_pdf = getattr(request, "output_pdf", None)
        signer = str(getattr(request, "signer_user", "unknown"))
        if isinstance(output_pdf, Path):
            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            base = b"%PDF-1.4\n"
            if isinstance(input_pdf, Path) and input_pdf.exists():
                base = input_pdf.read_bytes()
            output_pdf.write_bytes(base + f"\n%signed-by:{signer}\n".encode("utf-8"))
        return request


class _FakeAuditLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str, str]] = []

    def emit(self, action: str, actor: str, target: str, result: str, reason: str = "") -> None:
        self.calls.append((action, actor, target, result, reason))


class DocumentsInfrastructureTest(unittest.TestCase):
    def test_seed_reader_loads_default_profiles(self) -> None:
        reader = WorkflowProfileSeedReader()
        payload = reader.read(Path("modules/documents/workflow_profiles.json"))
        profiles = {item.profile_code: item for item in payload["profiles"]}
        profile = profiles["long_release"]
        self.assertEqual(profile.profile_code, "long_release")
        self.assertTrue(profile.four_eyes_required)

    def test_relational_store_bootstrap_preserves_runtime_profile_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SQLiteDocumentsRepository(db_path=root / "documents.db")
            store = WorkflowProfileRelationalStore(
                repo,
                bundled_seed_path=Path("modules/documents/workflow_profiles.json"),
                legacy_profiles_path=root / "missing-workflow-profiles.json",
            )
            store.ensure_seeded(WorkflowProfileSeedReader())
            profile = store.get("Controlled_Short_woSig")
            self.assertEqual(profile.profile_id, "Controlled_Short_woSig")
            self.assertEqual(profile.control_class, ControlClass.CONTROLLED_SHORT)
            self.assertEqual(profile.signature_required_transitions, ())
            self.assertTrue(profile.requires_editors)
            self.assertTrue(profile.requires_reviewers)
            self.assertTrue(profile.requires_approvers)

    def test_sqlite_repository_persists_and_lists_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "documents.db"
            service, _store = make_documents_service_with_profiles(
                db_path,
                signature_api=_FakeSignatureApi(),
            )

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
            storage = FileSystemDocumentsStorage(root / "artifacts")
            service, _store = make_documents_service_with_profiles(
                db_path,
                signature_api=_FakeSignatureApi(),
                storage_port=storage,
            )

            source_docx = root / "source.docx"
            source_docx.write_bytes(b"docx-content")
            state = service.import_existing_docx(
                "DOC-INTAKE",
                1,
                source_docx,
                actor_user_id="qmb",
                actor_role=SystemRole.QMB,
            )
            self.assertEqual(state.status, DocumentStatus.PLANNED)

            newer_docx = root / "source-new.docx"
            newer_docx.write_bytes(b"docx-content-new")
            service.import_existing_docx(
                "DOC-INTAKE",
                1,
                newer_docx,
                actor_user_id="qmb",
                actor_role=SystemRole.QMB,
            )

            artifacts = service.list_artifacts("DOC-INTAKE", 1)
            docx_artifacts = [a for a in artifacts if a.artifact_type == ArtifactType.SOURCE_DOCX]
            self.assertEqual(len(docx_artifacts), 2)
            self.assertEqual(sum(1 for a in docx_artifacts if a.is_current), 1)

    def test_complete_editing_generates_source_pdf_from_docx_and_marks_current(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="qmtool-docs-infra-"))
        db_path = root / "documents.db"
        storage = FileSystemDocumentsStorage(root / "artifacts")
        audit = _FakeAuditLogger()

        def _fake_docx_to_pdf(source: Path, target: Path) -> None:
            target.write_bytes(b"%PDF-1.4\n%fake\n")

        service, _store = make_documents_service_with_profiles(
            db_path,
            storage_port=storage,
            signature_api=_FakeSignatureApi(),
            audit_logger=audit,
        )
        service._docx_to_pdf_converter = _fake_docx_to_pdf

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
        source_pdf = service.ensure_source_pdf_for_signing(state)
        assert source_pdf is not None
        sign_request = SignRequest(
            input_pdf=Path(source_pdf),
            output_pdf=root / "wf-signed.pdf",
            signature_png=None,
            placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
            layout=LabelLayoutInput(show_signature=False, show_name=True, show_date=True),
            overwrite_output=True,
            dry_run=False,
            sign_mode="visual",
            signer_user="ed",
            password="secret",
            reason="test-complete",
        )
        service.complete_editing(state, sign_request=sign_request)

        artifacts = service.list_artifacts("DOC-WF", 1)
        source_pdfs = [a for a in artifacts if a.artifact_type == ArtifactType.SOURCE_PDF]
        self.assertGreaterEqual(len(source_pdfs), 1)
        self.assertEqual(sum(1 for a in source_pdfs if a.is_current), 1)
        self.assertTrue(any(call[0] == "documents.artifact.source_pdf.generated" for call in audit.calls))

    def test_complete_editing_persists_signed_pdf_for_followup_phases(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="qmtool-docs-sign-"))
        db_path = root / "documents.db"
        storage = FileSystemDocumentsStorage(root / "artifacts")
        def _fake_docx_to_pdf(_source: Path, target: Path) -> None:
            target.write_bytes(b"%PDF-1.4\n%source\n")

        service, _store = make_documents_service_with_profiles(
            db_path,
            storage_port=storage,
            signature_api=_FakeSignatureApi(),
        )
        service._docx_to_pdf_converter = _fake_docx_to_pdf

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
            service, _store = make_documents_service_with_profiles(
                db_path,
                signature_api=_FakeSignatureApi(),
            )

            state = service.create_document_version("DOC-DIST", 1, owner_user_id="owner-1")
            service.update_document_header(
                "DOC-DIST",
                distribution_roles=["QMB", "USER"],
                distribution_sites=["HQ"],
                distribution_departments=["QA"],
                actor_user_id="qmb",
                actor_role=SystemRole.QMB,
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

    def test_signature_chain_uses_latest_current_signed_pdf_for_next_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FileSystemDocumentsStorage(root / "artifacts")
            def _fake_docx_to_pdf(_source: Path, target: Path) -> None:
                target.write_bytes(b"%PDF-1.4\n%source\n")

            service, _store = make_documents_service_with_profiles(
                root / "documents.db",
                storage_port=storage,
                signature_api=_ChainSignatureApi(),
            )
            service._docx_to_pdf_converter = _fake_docx_to_pdf

            source_docx = root / "chain.docx"
            source_docx.write_bytes(b"docx-chain")
            state = service.import_existing_docx("DOC-CHAIN", 1, source_docx, actor_user_id="admin", actor_role=SystemRole.ADMIN)
            state = service.assign_workflow_roles(state, editors={"ed"}, reviewers={"rv"}, approvers={"ap"})
            state = service.start_workflow(state, WorkflowProfile.long_release_path())
            source_pdf = service.ensure_source_pdf_for_signing(state)
            assert source_pdf is not None

            edit_request = SignRequest(
                input_pdf=Path(source_pdf),
                output_pdf=root / "signed-edit.pdf",
                signature_png=None,
                placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
                layout=LabelLayoutInput(show_signature=False, show_name=True, show_date=True),
                overwrite_output=True,
                dry_run=False,
                sign_mode="visual",
                signer_user="ed",
                password="pw",
                reason="edit",
            )
            state = service.complete_editing(state, sign_request=edit_request)

            review_request = SignRequest(
                input_pdf=Path(source_pdf),
                output_pdf=root / "signed-review.pdf",
                signature_png=None,
                placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
                layout=LabelLayoutInput(show_signature=False, show_name=True, show_date=True),
                overwrite_output=True,
                dry_run=False,
                sign_mode="visual",
                signer_user="rv",
                password="pw",
                reason="review",
            )
            state = service.accept_review(state, "rv", sign_request=review_request)
            review_artifacts = [
                item
                for item in service.list_artifacts("DOC-CHAIN", 1)
                if item.artifact_type == ArtifactType.SIGNED_PDF and item.is_current
            ]
            self.assertTrue(review_artifacts)
            review_output = service.read_artifact_bytes(review_artifacts[0].artifact_id)
            self.assertIn(b"%signed-by:ed", review_output)
            self.assertIn(b"%signed-by:rv", review_output)

            approve_request = SignRequest(
                input_pdf=Path(source_pdf),
                output_pdf=root / "signed-approve.pdf",
                signature_png=None,
                placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
                layout=LabelLayoutInput(show_signature=False, show_name=True, show_date=True),
                overwrite_output=True,
                dry_run=False,
                sign_mode="visual",
                signer_user="ap",
                password="pw",
                reason="approve",
            )
            state = service.accept_approval(state, "ap", sign_request=approve_request)
            approval_artifacts = [
                item
                for item in service.list_artifacts("DOC-CHAIN", 1)
                if item.artifact_type == ArtifactType.SIGNED_PDF and item.is_current
            ]
            self.assertTrue(approval_artifacts)
            approval_output = service.read_artifact_bytes(approval_artifacts[0].artifact_id)
            self.assertIn(b"%signed-by:ed", approval_output)
            self.assertIn(b"%signed-by:rv", approval_output)
            self.assertIn(b"%signed-by:ap", approval_output)

            signed_artifacts = [a for a in service.list_artifacts("DOC-CHAIN", 1) if a.artifact_type == ArtifactType.SIGNED_PDF]
            self.assertGreaterEqual(len(signed_artifacts), 3)
            self.assertEqual(sum(1 for a in signed_artifacts if a.is_current), 1)

    def test_sqlite_roundtrip_persists_validity_extension_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _store = make_documents_service_with_profiles(
                root / "documents.db",
                signature_api=_FakeSignatureApi(),
            )
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
            loaded = service.get_document_version("DOC-EXT-SQL", 1)
            assert loaded is not None
            self.assertEqual(loaded.last_extended_by, "qmb-1")
            self.assertEqual(loaded.last_extension_reason, "Audit ohne Befund")
            self.assertEqual(loaded.last_extension_review_outcome, ValidityExtensionOutcome.UNCHANGED.value)
            self.assertEqual(loaded.extension_count, extended.extension_count)

    def test_duplicate_create_does_not_insert_second_db_version_or_reset_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "documents.db"
            storage = FileSystemDocumentsStorage(root / "artifacts")
            service, _store = make_documents_service_with_profiles(
                db_path,
                signature_api=_FakeSignatureApi(),
                storage_port=storage,
            )
            source_pdf = root / "source.pdf"
            source_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            state = service.create_document_version("DOC-DUP-DB", 1, owner_user_id="owner-1")
            service.import_existing_pdf(
                "DOC-DUP-DB",
                1,
                source_pdf,
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            )
            state = service.get_document_version("DOC-DUP-DB", 1)
            assert state is not None
            state = service.assign_workflow_roles(
                state,
                editors={"editor-1"},
                reviewers={"reviewer-1"},
                approvers={"approver-1"},
            )
            service.start_workflow(state, WorkflowProfile.long_release_path())
            artifacts_before = service.list_artifacts("DOC-DUP-DB", 1)
            self.assertTrue(artifacts_before)
            before = service.get_document_version("DOC-DUP-DB", 1)
            assert before is not None

            with self.assertRaises(DocumentConflictError):
                service.create_document_version("DOC-DUP-DB", 1, owner_user_id="intruder", title="rewind")
            versions = service._repository.list_versions("DOC-DUP-DB")
            self.assertEqual(len(versions), 1)
            loaded = service.get_document_version("DOC-DUP-DB", 1)
            assert loaded is not None
            self.assertEqual(loaded.status, before.status)
            self.assertEqual(loaded.last_event_id, before.last_event_id)
            self.assertEqual(loaded.assignments.editors, before.assignments.editors)
            self.assertNotEqual(loaded.status, DocumentStatus.PLANNED)
            artifacts_after = service.list_artifacts("DOC-DUP-DB", 1)
            self.assertEqual(
                [item.artifact_id for item in artifacts_after],
                [item.artifact_id for item in artifacts_before],
            )

    def test_storage_uses_object_keys_keeps_legacy_readable_and_contains_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artifacts"
            storage = FileSystemDocumentsStorage(root)
            source = Path(tmp) / "source.pdf"
            source.write_bytes(b"%PDF-1.4\n%%EOF\n")
            stored = storage.store_file_copy(
                source_path=source,
                document_id=r"..\I:\escape/DOC",
                version=1,
                artifact_type="SOURCE_PDF",
            )
            self.assertTrue(stored.storage_key.startswith("objects/"))
            self.assertNotIn("escape", stored.storage_key)
            self.assertNotIn("SOURCE_PDF", stored.storage_key)
            self.assertNotIn("..", stored.storage_key)
            stored_path = Path(stored.file_path).resolve()
            self.assertTrue(stored_path.is_relative_to(root.resolve()))
            self.assertEqual(storage.read_bytes(stored.storage_key), b"%PDF-1.4\n%%EOF\n")

            legacy_key = "DOC-1/v1/SOURCE_PDF/legacy.pdf"
            legacy_path = root / "DOC-1" / "v1" / "SOURCE_PDF" / "legacy.pdf"
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_bytes(b"%PDF-1.4\nlegacy\n")
            self.assertEqual(storage.read_bytes(legacy_key), b"%PDF-1.4\nlegacy\n")

            with self.assertRaises(ValueError):
                storage.resolve_storage_key("../outside.pdf")
            with self.assertRaises(ValueError):
                storage.resolve_storage_key(r"I:\windows\outside.pdf")

    def test_unusual_document_id_stays_fachlich_and_does_not_enter_storage_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FileSystemDocumentsStorage(root / "artifacts")
            service, _store = make_documents_service_with_profiles(
                root / "documents.db",
                signature_api=_FakeSignatureApi(),
                storage_port=storage,
            )
            weird_id = r"DOC..\\WEIRD"
            source_pdf = root / "source.pdf"
            source_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            state = service.create_document_version(weird_id, 1, owner_user_id="owner-1")
            self.assertEqual(state.document_id, weird_id)
            imported = service.import_existing_pdf(
                weird_id,
                1,
                source_pdf,
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            )
            self.assertEqual(imported.document_id, weird_id)
            loaded = service.get_document_version(weird_id, 1)
            assert loaded is not None
            self.assertEqual(loaded.document_id, weird_id)
            artifacts = service.list_artifacts(weird_id, 1)
            self.assertTrue(artifacts)
            for artifact in artifacts:
                self.assertEqual(artifact.document_id, weird_id)
                self.assertTrue(artifact.storage_key.startswith("objects/"))
                self.assertNotIn("WEIRD", artifact.storage_key)
                path = storage.resolve_storage_key(artifact.storage_key)
                self.assertTrue(path.resolve().is_relative_to((root / "artifacts").resolve()))

    def test_pdf_and_docx_import_stamp_event_and_reject_stale_etag(self) -> None:
        from modules.documents.api import DocumentsWorkflowApi

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FileSystemDocumentsStorage(root / "artifacts")
            service, _store = make_documents_service_with_profiles(
                root / "documents.db",
                signature_api=_FakeSignatureApi(),
                storage_port=storage,
            )
            api = DocumentsWorkflowApi(service)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            docx = root / "source.docx"
            docx.write_bytes(b"PK\x03\x04docx-stub")

            pdf_state = service.create_document_version("DOC-IMP-PDF", 1, owner_user_id="owner-1")
            pdf_prior = pdf_state.last_event_id
            imported_pdf = api.import_existing_pdf(
                "DOC-IMP-PDF",
                1,
                pdf,
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
                expected_last_event_id=pdf_prior,
            )
            self.assertIsNotNone(imported_pdf.last_event_id)
            self.assertNotEqual(imported_pdf.last_event_id, pdf_prior)
            self.assertEqual(imported_pdf.last_actor_user_id, "owner-1")
            persisted_pdf = service.get_document_version("DOC-IMP-PDF", 1)
            assert persisted_pdf is not None
            self.assertEqual(persisted_pdf.last_event_id, imported_pdf.last_event_id)
            with self.assertRaises(DocumentConflictError):
                api.import_existing_pdf(
                    "DOC-IMP-PDF",
                    1,
                    pdf,
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                    expected_last_event_id=pdf_prior,
                )
            still_pdf = service.get_document_version("DOC-IMP-PDF", 1)
            assert still_pdf is not None
            self.assertEqual(still_pdf.last_event_id, imported_pdf.last_event_id)

            docx_state = service.create_document_version("DOC-IMP-DOCX", 1, owner_user_id="owner-1")
            docx_prior = docx_state.last_event_id
            imported_docx = api.import_existing_docx(
                "DOC-IMP-DOCX",
                1,
                docx,
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
                expected_last_event_id=docx_prior,
            )
            self.assertNotEqual(imported_docx.last_event_id, docx_prior)
            with self.assertRaises(DocumentConflictError):
                api.import_existing_docx(
                    "DOC-IMP-DOCX",
                    1,
                    docx,
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                    expected_last_event_id=docx_prior,
                )

    def test_sqlite_connections_are_thread_local_and_nested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _store = make_documents_service_with_profiles(
                root / "documents.db",
                signature_api=_FakeSignatureApi(),
            )
            repo = service._repository
            source = inspect.getsource(type(repo))
            self.assertNotIn("check_same_thread=False", source)
            state = service.create_document_version("DOC-SQL-TLS", 1, owner_user_id="owner-1")
            with repo.write_transaction():
                repo.upsert(replace(state, title="outer"))
                with repo.write_transaction():
                    repo.upsert(replace(state, title="inner"))
            nested = repo.get("DOC-SQL-TLS", 1)
            assert nested is not None
            self.assertEqual(nested.title, "inner")

            errors: list[BaseException] = []

            def _writer() -> None:
                with repo.write_transaction():
                    repo.upsert(replace(state, title="held"))
                    time.sleep(0.4)

            def _reader() -> None:
                time.sleep(0.1)
                try:
                    loaded = repo.get("DOC-SQL-TLS", 1)
                    assert loaded is not None
                except sqlite3.ProgrammingError as exc:
                    errors.append(exc)

            writer = threading.Thread(target=_writer)
            reader = threading.Thread(target=_reader)
            writer.start()
            reader.start()
            writer.join()
            reader.join()
            self.assertEqual(errors, [])

            with self.assertRaises(RuntimeError):
                with repo.write_transaction():
                    repo.upsert(replace(state, title="rolled"))
                    raise RuntimeError("boom")
            self.assertIsNone(getattr(repo._txn_local, "conn", None))
            after_rollback = repo.get("DOC-SQL-TLS", 1)
            assert after_rollback is not None
            self.assertEqual(after_rollback.title, "held")

    def test_docx_comment_sync_identity_is_context_and_w_id(self) -> None:
        from zipfile import ZipFile

        from modules.documents.api import DocumentsCommentsApi
        from modules.documents.contracts import WorkflowCommentStatus
        from modules.documents.errors import ValidationError, PermissionDeniedError

        def _write_docx(path: Path, comments: list[tuple[str, str | None, str | None, str]]) -> None:
            ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            nodes = []
            for cid, author, date, text in comments:
                attrs = f'w:id="{cid}"'
                if author:
                    attrs += f' w:author="{author}"'
                if date:
                    attrs += f' w:date="{date}"'
                nodes.append(
                    f'<w:comment {attrs}><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:comment>'
                )
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f'<w:comments xmlns:w="{ns}">{"".join(nodes)}</w:comments>'
            )
            with ZipFile(path, "w") as zf:
                zf.writestr("word/comments.xml", xml)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FileSystemDocumentsStorage(root / "artifacts")
            service, _store = make_documents_service_with_profiles(
                root / "documents.db",
                signature_api=_FakeSignatureApi(),
                storage_port=storage,
            )
            comments_api = DocumentsCommentsApi(service)
            docx = root / "comments.docx"
            _write_docx(
                docx,
                [("1", "Ann", "2026-01-01T00:00:00Z", "first")],
            )
            service.create_document_version("DOC-CMT-SYNC", 1, owner_user_id="owner-1")
            state = service.import_existing_docx(
                "DOC-CMT-SYNC", 1, docx, actor_user_id="owner-1", actor_role=SystemRole.USER
            )
            first = comments_api.sync_docx_comments(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            self.assertEqual(len(first), 1)
            comment_id = first[0].comment_id
            ref_no = first[0].ref_no

            _write_docx(docx, [("1", "Ann", "2026-02-02T00:00:00Z", "first")])
            service.import_existing_docx(
                "DOC-CMT-SYNC", 1, docx, actor_user_id="owner-1", actor_role=SystemRole.USER
            )
            again = comments_api.sync_docx_comments(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            self.assertEqual(len(again), 1)
            self.assertEqual(again[0].comment_id, comment_id)

            _write_docx(docx, [("1", "Ann", None, "first")])
            service.import_existing_docx(
                "DOC-CMT-SYNC", 1, docx, actor_user_id="owner-1", actor_role=SystemRole.USER
            )
            undated = comments_api.sync_docx_comments(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            self.assertEqual(len(undated), 1)
            self.assertEqual(undated[0].comment_id, comment_id)

            _write_docx(docx, [("1", "Ann", "2026-01-01T00:00:00Z", "edited")])
            service.import_existing_docx(
                "DOC-CMT-SYNC", 1, docx, actor_user_id="owner-1", actor_role=SystemRole.USER
            )
            edited = comments_api.sync_docx_comments(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            self.assertEqual(len(edited), 1)
            self.assertEqual(edited[0].comment_id, comment_id)
            self.assertEqual(edited[0].preview_text, "edited")

            _write_docx(
                docx,
                [
                    ("1", "Ann", "2026-01-01T00:00:00Z", "edited"),
                    ("2", "Bob", "2026-01-02T00:00:00Z", "second"),
                ],
            )
            service.import_existing_docx(
                "DOC-CMT-SYNC", 1, docx, actor_user_id="owner-1", actor_role=SystemRole.USER
            )
            two = comments_api.sync_docx_comments(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            self.assertEqual(len(two), 2)
            refs = sorted(item.ref_no for item in two)
            self.assertEqual(len(set(refs)), 2)
            kept = next(item for item in two if item.comment_id == comment_id)
            self.assertEqual(kept.ref_no, ref_no)

            service.set_workflow_comment_status(
                comment_id,
                new_status=WorkflowCommentStatus.RESOLVED,
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
                note="done",
            )
            resolved = comments_api.sync_docx_comments(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            still = next(item for item in resolved if item.comment_id == comment_id)
            self.assertEqual(still.status, WorkflowCommentStatus.RESOLVED)

            with self.assertRaises(PermissionDeniedError):
                comments_api.sync_docx_comments(
                    state, actor_user_id="observer-1", actor_role=SystemRole.USER
                )

            broken = root / "broken.docx"
            broken.write_bytes(b"not-a-zip")
            service.import_existing_docx(
                "DOC-CMT-SYNC", 1, broken, actor_user_id="owner-1", actor_role=SystemRole.USER
            )
            with self.assertRaises(ValidationError):
                comments_api.sync_docx_comments(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            missing = root / "missing.docx"
            with ZipFile(missing, "w") as zf:
                zf.writestr("word/document.xml", "<w:document/>")
            service.import_existing_docx(
                "DOC-CMT-SYNC", 1, missing, actor_user_id="owner-1", actor_role=SystemRole.USER
            )
            with self.assertRaises(ValidationError):
                comments_api.sync_docx_comments(state, actor_user_id="owner-1", actor_role=SystemRole.USER)

    def _resolverless_artifact(
        self,
        storage_key: str,
        metadata: dict[str, str] | None = None,
    ) -> DocumentArtifact:
        return DocumentArtifact(
            artifact_id="art-resolverless-1",
            document_id="DOC-1",
            version=1,
            artifact_type=ArtifactType.SOURCE_PDF,
            source_type=ArtifactSourceType.GENERATED,
            storage_key=storage_key,
            original_filename="source.pdf",
            mime_type="application/pdf",
            sha256="0" * 64,
            size_bytes=1,
            is_current=True,
            metadata=metadata or {},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def test_resolverless_artifact_path_valid_keys_stay_inside_root(self) -> None:
        keys = (
            "DOC-1/v1/SOURCE_PDF/source.pdf",
            "objects/aa/example.pdf",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "storage"
            root.mkdir()
            port = SimpleNamespace(_root_path=root)
            root_resolved = root.resolve(strict=False)
            for key in keys:
                with self.subTest(key=key):
                    resolved = resolve_artifact_path(self._resolverless_artifact(key), port)
                    expected = contained_path(root, key)
                    self.assertEqual(resolved, expected)
                    self.assertIsNotNone(resolved)
                    assert resolved is not None
                    self.assertTrue(resolved.resolve(strict=False).is_relative_to(root_resolved))

    def test_resolverless_artifact_path_invalid_keys_fail_closed(self) -> None:
        keys = (
            "../outside.pdf",
            "subdir/../../outside.pdf",
            "/outside.pdf",
            "~/outside.pdf",
            "C:/outside.pdf",
            r"..\outside.pdf",
        )
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "storage"
            root.mkdir()
            outside = parent / "outside.pdf"
            outside.write_bytes(b"%PDF-1.4\noutside\n")
            self.assertTrue(outside.is_file())
            port = SimpleNamespace(_root_path=root)
            root_resolved = root.resolve(strict=False)
            for key in keys:
                with self.subTest(key=key):
                    resolved = resolve_artifact_path(self._resolverless_artifact(key), port)
                    self.assertIsNone(resolved)
                    if resolved is not None:
                        self.fail(f"storage_key escaped documents storage root: {resolved}")
                    self.assertTrue(outside.is_file())
                    self.assertFalse(outside.resolve(strict=False).is_relative_to(root_resolved))

    def test_resolverless_artifact_path_prefers_callable_resolve_storage_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "storage"
            root.mkdir()
            preferred = root / "from-resolver.pdf"
            preferred.write_bytes(b"resolver")
            calls: list[str] = []

            class _ResolvingPort:
                _root_path = root

                def resolve_storage_key(self, key: str) -> Path:
                    calls.append(key)
                    return preferred

            resolved = resolve_artifact_path(
                self._resolverless_artifact("../outside.pdf"),
                _ResolvingPort(),
            )
            self.assertEqual(calls, ["../outside.pdf"])
            self.assertEqual(resolved, preferred)

    def test_resolverless_artifact_path_resolver_valueerror_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "storage"
            root.mkdir()

            class _FailingResolverPort:
                _root_path = root

                def resolve_storage_key(self, key: str) -> Path:
                    raise ValueError("storage_key escapes documents storage root")

            resolved = resolve_artifact_path(
                self._resolverless_artifact("DOC-1/v1/SOURCE_PDF/source.pdf"),
                _FailingResolverPort(),
            )
            self.assertIsNone(resolved)

    def test_resolverless_artifact_path_legacy_metadata_resolution_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "storage"
            root.mkdir()
            legacy = parent / "legacy.pdf"
            legacy.write_bytes(b"%PDF-1.4\nlegacy\n")
            port = SimpleNamespace(_root_path=root)
            present = self._resolverless_artifact(
                "../outside.pdf",
                metadata={"absolute_path": str(legacy)},
            )
            self.assertEqual(resolve_artifact_path(present, port), Path(str(legacy)))
            missing = self._resolverless_artifact(
                "../outside.pdf",
                metadata={"absolute_path": str(parent / "missing.pdf")},
            )
            self.assertIsNone(resolve_artifact_path(missing, port))


if __name__ == "__main__":
    unittest.main()

