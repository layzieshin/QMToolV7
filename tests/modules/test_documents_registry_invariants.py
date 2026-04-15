from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType, SystemRole, WorkflowProfile
from modules.documents.errors import PermissionDeniedError, ValidationError
from modules.documents.profile_store import WorkflowProfileStoreJSON
from modules.documents.service import DocumentsService
from modules.documents.sqlite_repository import SQLiteDocumentsRepository
from modules.registry.projection_api import RegistryProjectionApi
from modules.registry.sqlite_repository import SQLiteRegistryRepository
from modules.registry.service import RegistryService


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


class DocumentsRegistryInvariantsTest(unittest.TestCase):
    def _service(self, root: Path) -> DocumentsService:
        docs_repo = SQLiteDocumentsRepository(
            db_path=root / "documents.db",
            schema_path=Path("modules/documents/schema.sql"),
        )
        reg_repo = SQLiteRegistryRepository(
            db_path=root / "registry.db",
            schema_path=Path("modules/registry/schema.sql"),
        )
        return DocumentsService(
            repository=docs_repo,
            profile_store=WorkflowProfileStoreJSON(Path("modules/documents/workflow_profiles.json")),
            signature_api=_FakeSignatureApi(),
            registry_projection_api=RegistryProjectionApi(RegistryService(reg_repo)),
        )

    def test_new_approval_supersedes_previous_approved_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(Path(tmp))

            v1 = service.create_document_version("DOC-SUP", 1, owner_user_id="owner-1")
            v1 = service.assign_workflow_roles(v1, editors={"ed"}, reviewers={"rv"}, approvers={"ap"})
            v1 = service.start_workflow(v1, WorkflowProfile.long_release_path())
            v1 = service.complete_editing(v1, sign_request={"step": "edit"})
            v1 = service.accept_review(v1, "rv", sign_request={"step": "review_accept"})
            v1 = service.accept_approval(v1, "ap", sign_request={"step": "approve"})
            self.assertEqual(v1.status, DocumentStatus.APPROVED)

            v2 = service.create_document_version("DOC-SUP", 2, owner_user_id="owner-1")
            v2 = service.assign_workflow_roles(v2, editors={"ed"}, reviewers={"rv"}, approvers={"ap"})
            v2 = service.start_workflow(v2, WorkflowProfile.long_release_path())
            v2 = service.complete_editing(v2, sign_request={"step": "edit"})
            v2 = service.accept_review(v2, "rv", sign_request={"step": "review_accept"})
            v2 = service.accept_approval(v2, "ap", sign_request={"step": "approve"})
            self.assertEqual(v2.status, DocumentStatus.APPROVED)

            old = service.get_document_version("DOC-SUP", 1)
            self.assertIsNotNone(old)
            assert old is not None
            self.assertEqual(old.status, DocumentStatus.ARCHIVED)
            self.assertEqual(old.superseded_by_version, 2)

            approved_versions = service.list_by_status(DocumentStatus.APPROVED)
            self.assertEqual([(s.document_id, s.version) for s in approved_versions if s.document_id == "DOC-SUP"], [("DOC-SUP", 2)])

    def test_registry_tracks_active_version_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_repo = SQLiteDocumentsRepository(
                db_path=root / "documents.db",
                schema_path=Path("modules/documents/schema.sql"),
            )
            reg_repo = SQLiteRegistryRepository(
                db_path=root / "registry.db",
                schema_path=Path("modules/registry/schema.sql"),
            )
            registry = RegistryService(reg_repo)
            service = DocumentsService(
                repository=docs_repo,
                signature_api=_FakeSignatureApi(),
                registry_projection_api=RegistryProjectionApi(registry),
            )

            state = service.create_document_version("DOC-REG", 1, owner_user_id="owner-1")
            state = service.assign_workflow_roles(state, editors={"ed"}, reviewers={"rv"}, approvers={"ap"})
            state = service.start_workflow(state, WorkflowProfile.long_release_path())
            state = service.complete_editing(state, sign_request={"step": "edit"})
            state = service.accept_review(state, "rv", sign_request={"step": "review_accept"})
            state = service.accept_approval(state, "ap", sign_request={"step": "approve"})

            entry = registry.get_entry("DOC-REG")
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertEqual(entry.active_version, 1)
            self.assertTrue(entry.is_findable)
            self.assertEqual(entry.register_state.value, "VALID")

            state = service.archive_approved(state, SystemRole.QMB, actor_user_id="qmb")
            self.assertEqual(state.status, DocumentStatus.ARCHIVED)
            archived = registry.get_entry("DOC-REG")
            self.assertIsNotNone(archived)
            assert archived is not None
            self.assertIsNone(archived.active_version)
            self.assertFalse(archived.is_findable)
            self.assertEqual(archived.register_state.value, "ARCHIVED")

    def test_external_profile_rejects_internal_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(Path(tmp))
            state = service.create_document_version(
                "DOC-EXT",
                1,
                owner_user_id="owner-1",
                doc_type=DocumentType.EXT,
                control_class=ControlClass.EXTERNAL,
                workflow_profile_id="external_control",
            )
            state = service.assign_workflow_roles(state, editors={"ed"}, reviewers={"rv"}, approvers={"ap"})
            profile = service.get_profile("external_control")
            with self.assertRaisesRegex(Exception, "external documents must not have internal workflow assignments"):
                service.start_workflow(state, profile, actor_user_id="owner-1", actor_role=SystemRole.USER)

    def test_header_update_requires_privileged_actor_and_keeps_steering_fields_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(Path(tmp))
            service.create_document_version(
                "DOC-HDR-IMM",
                1,
                owner_user_id="owner-1",
                doc_type=DocumentType.VA,
                control_class=ControlClass.CONTROLLED,
                workflow_profile_id="long_release",
            )
            with self.assertRaises(PermissionDeniedError):
                service.update_document_header(
                    "DOC-HDR-IMM",
                    doc_type=DocumentType.FB,
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )
            with self.assertRaises(ValidationError):
                service.update_document_header(
                    "DOC-HDR-IMM",
                    doc_type=DocumentType.FB,
                    actor_user_id="qmb-1",
                    actor_role=SystemRole.QMB,
                )
            with self.assertRaises(ValidationError):
                service.update_document_header(
                    "DOC-HDR-IMM",
                    control_class=ControlClass.RECORD,
                    actor_user_id="admin-1",
                    actor_role=SystemRole.ADMIN,
                )

    def test_header_profile_change_rejects_control_class_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(Path(tmp))
            service.create_document_version(
                "DOC-HDR-PROFILE",
                1,
                owner_user_id="owner-1",
                doc_type=DocumentType.VA,
                control_class=ControlClass.CONTROLLED,
                workflow_profile_id="long_release",
            )
            with self.assertRaisesRegex(ValidationError, "does not match document control_class"):
                service.update_document_header(
                    "DOC-HDR-PROFILE",
                    workflow_profile_id="external_control",
                    actor_user_id="admin-1",
                    actor_role=SystemRole.ADMIN,
                )

    def test_metadata_update_requires_actor_and_rejects_unsafe_custom_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(Path(tmp))
            state = service.create_document_version("DOC-META-GUARDS", 1, owner_user_id="owner-1")
            with self.assertRaisesRegex(ValidationError, "actor_user_id and actor_role are required"):
                service.update_version_metadata(state, title="X")
            with self.assertRaisesRegex(ValidationError, "validity dates can only be updated"):
                service.update_version_metadata(
                    state,
                    valid_until=datetime.now(timezone.utc),
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )
            with self.assertRaisesRegex(ValidationError, "forbidden steering prefix"):
                service.update_version_metadata(
                    state,
                    custom_fields={"workflow.step": "hack"},
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )
            with self.assertRaisesRegex(ValidationError, "invalid"):
                service.update_version_metadata(
                    state,
                    custom_fields={"bad key": "x"},
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )


if __name__ == "__main__":
    unittest.main()
