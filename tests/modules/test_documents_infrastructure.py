from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.documents.contracts import ArtifactType, DocumentStatus, SystemRole, WorkflowProfile
from modules.documents.profile_store import WorkflowProfileStoreJSON
from modules.documents.service import DocumentsService
from modules.documents.sqlite_repository import SQLiteDocumentsRepository
from modules.documents.storage import FileSystemDocumentsStorage


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


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
            approved = service.accept_review(approved, "rv")
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


if __name__ == "__main__":
    unittest.main()

