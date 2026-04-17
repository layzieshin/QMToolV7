from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.documents.contracts import RejectionReason, SystemRole, ValidityExtensionOutcome, WorkflowProfile
from modules.documents.service import DocumentsService
from modules.documents.sqlite_repository import SQLiteDocumentsRepository
from modules.registry.projection_api import RegistryProjectionApi
from modules.registry.sqlite_repository import SQLiteRegistryRepository
from modules.registry.service import RegistryService
from modules.documents.storage import FileSystemDocumentsStorage
from qm_platform.events.event_bus import EventBus
from qm_platform.events.event_envelope import EventEnvelope


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


class DocumentsEventContractsTest(unittest.TestCase):
    @staticmethod
    def _write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    @staticmethod
    def _subscribe_all(bus: EventBus, names: list[str], sink: list[EventEnvelope]) -> None:
        for name in names:
            bus.subscribe(name, lambda event: sink.append(event))

    def test_intake_events_publish_expected_payload_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = EventBus()
            events: list[EventEnvelope] = []
            self._subscribe_all(
                bus,
                [
                    "domain.documents.artifact.imported.v1",
                    "domain.documents.template.created.v1",
                ],
                events,
            )

            repo = SQLiteDocumentsRepository(db_path=root / "documents.db", schema_path=Path("modules/documents/schema.sql"))
            storage = FileSystemDocumentsStorage(root / "artifacts")
            registry = RegistryService(
                SQLiteRegistryRepository(db_path=root / "registry.db", schema_path=Path("modules/registry/schema.sql"))
            )
            service = DocumentsService(
                event_bus=bus,
                repository=repo,
                storage_port=storage,
                signature_api=_FakeSignatureApi(),
                registry_projection_api=RegistryProjectionApi(registry),
            )

            pdf = root / "source.pdf"
            dotx = root / "template.dotx"
            self._write_bytes(pdf, b"%PDF-1.4\n%%EOF\n")
            self._write_bytes(dotx, b"dotx-bytes")

            service.import_existing_pdf("DOC-EVT-1", 1, pdf, actor_user_id="owner-1", actor_role=SystemRole.USER)
            service.create_from_template("DOC-EVT-2", 1, dotx, actor_user_id="owner-2", actor_role=SystemRole.USER)

            imported = [e for e in events if e.name == "domain.documents.artifact.imported.v1"]
            created = [e for e in events if e.name == "domain.documents.template.created.v1"]
            self.assertEqual(len(imported), 1)
            self.assertEqual(len(created), 1)

            imported_payload = imported[0].payload
            self.assertEqual(imported[0].module_id, "documents")
            self.assertEqual(imported_payload["document_id"], "DOC-EVT-1")
            self.assertEqual(imported_payload["version"], 1)
            self.assertIn("artifact_id", imported_payload)
            self.assertIsNotNone(imported[0].event_id)
            self.assertIsNotNone(imported[0].occurred_at_utc)
            self.assertEqual(imported[0].actor_user_id, "owner-1")

            created_payload = created[0].payload
            self.assertEqual(created[0].module_id, "documents")
            self.assertEqual(created_payload["document_id"], "DOC-EVT-2")
            self.assertEqual(created_payload["version"], 1)
            self.assertIn("artifact_id", created_payload)
            self.assertIsNotNone(created[0].event_id)
            self.assertIsNotNone(created[0].occurred_at_utc)
            self.assertEqual(created[0].actor_user_id, "owner-2")

    def test_workflow_events_publish_expected_payload_fields(self) -> None:
        bus = EventBus()
        events: list[EventEnvelope] = []
        names = [
            "domain.documents.workflow.started.v1",
            "domain.documents.editing.completed.v1",
            "domain.documents.review.accepted.v1",
            "domain.documents.review.rejected.v1",
            "domain.documents.approval.accepted.v1",
            "domain.documents.approval.rejected.v1",
            "domain.documents.workflow.aborted.v1",
            "domain.documents.archived.v1",
            "domain.documents.validity.extended.v1",
        ]
        self._subscribe_all(bus, names, events)

        service = DocumentsService(event_bus=bus, signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-EVT-WF", 1, owner_user_id="owner-1")
        state = service.assign_workflow_roles(state, editors={"owner-1"}, reviewers={"reviewer-1"}, approvers={"approver-1"})
        state = service.start_workflow(state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER)
        state = service.complete_editing(
            state,
            sign_request={"step": "edit_complete"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        state = service.reject_review(
            state,
            "reviewer-1",
            RejectionReason(template_id="R1", template_text="Needs rework", free_text="Please fix section 2"),
        )
        state = service.complete_editing(
            state,
            sign_request={"step": "edit_complete"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        state = service.accept_review(state, "reviewer-1", sign_request={"step": "review_accept"})
        state = service.reject_approval(
            state,
            "approver-1",
            RejectionReason(template_id="A1", template_text="Insufficient evidence", free_text="Add references"),
        )
        state = service.abort_workflow(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
        state = service.start_workflow(state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER)
        state = service.complete_editing(
            state,
            sign_request={"step": "edit_complete"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        state = service.accept_review(state, "reviewer-1", sign_request={"step": "review_accept"})
        state = service.accept_approval(state, "approver-1", sign_request={"step": "approve"})
        state, _ = service.extend_annual_validity(
            state,
            actor_user_id="qmb-1",
            signature_present=True,
            duration_days=365,
            reason="Jahresreview ohne inhaltliche Aenderung",
            review_outcome=ValidityExtensionOutcome.UNCHANGED,
        )
        service.archive_approved(state, SystemRole.QMB)

        by_name = {name: [e for e in events if e.name == name] for name in names}
        for name in names:
            with self.subTest(event=name):
                self.assertGreaterEqual(len(by_name[name]), 1)
                payload = by_name[name][0].payload
                self.assertEqual(payload["document_id"], "DOC-EVT-WF")
                self.assertEqual(payload["version"], 1)
                self.assertTrue(by_name[name][0].event_id)
                self.assertTrue(by_name[name][0].occurred_at_utc)

        self.assertIn("profile_id", by_name["domain.documents.workflow.started.v1"][0].payload)
        self.assertIn("to_status", by_name["domain.documents.editing.completed.v1"][0].payload)
        self.assertIn("actor_user_id", by_name["domain.documents.review.accepted.v1"][0].payload)
        self.assertIn("actor_user_id", by_name["domain.documents.review.rejected.v1"][0].payload)
        self.assertIn("actor_user_id", by_name["domain.documents.approval.accepted.v1"][0].payload)
        self.assertIn("actor_user_id", by_name["domain.documents.approval.rejected.v1"][0].payload)
        self.assertIn("actor_role", by_name["domain.documents.archived.v1"][0].payload)
        self.assertIn("extension_count", by_name["domain.documents.validity.extended.v1"][0].payload)
        self.assertIn("duration_days", by_name["domain.documents.validity.extended.v1"][0].payload)
        self.assertIn("reason", by_name["domain.documents.validity.extended.v1"][0].payload)

    def test_registry_reaction_after_approval_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = EventBus()
            repo = SQLiteDocumentsRepository(db_path=root / "documents.db", schema_path=Path("modules/documents/schema.sql"))
            registry = RegistryService(
                SQLiteRegistryRepository(db_path=root / "registry.db", schema_path=Path("modules/registry/schema.sql"))
            )
            service = DocumentsService(
                event_bus=bus,
                repository=repo,
                signature_api=_FakeSignatureApi(),
                registry_projection_api=RegistryProjectionApi(registry),
            )
            state = service.create_document_version("DOC-EVT-REG", 1, owner_user_id="owner-1")
            state = service.assign_workflow_roles(state, editors={"owner-1"}, reviewers={"reviewer-1"}, approvers={"approver-1"})
            state = service.start_workflow(state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER)
            state = service.complete_editing(state, sign_request={"step": "edit_complete"}, actor_user_id="owner-1", actor_role=SystemRole.USER)
            state = service.accept_review(state, "reviewer-1", sign_request={"step": "review_accept"})
            service.accept_approval(state, "approver-1", sign_request={"step": "approve"})
            entry = registry.get_entry("DOC-EVT-REG")
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertEqual(entry.active_version, 1)
            self.assertEqual(entry.register_state.value, "VALID")

    def test_registry_projection_stays_consistent_with_documents_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SQLiteDocumentsRepository(db_path=root / "documents.db", schema_path=Path("modules/documents/schema.sql"))
            registry = RegistryService(
                SQLiteRegistryRepository(db_path=root / "registry.db", schema_path=Path("modules/registry/schema.sql"))
            )
            service = DocumentsService(
                repository=repo,
                signature_api=_FakeSignatureApi(),
                registry_projection_api=RegistryProjectionApi(registry),
            )
            state = service.create_document_version("DOC-EVT-CONSIST", 1, owner_user_id="owner-1")
            entry = registry.get_entry("DOC-EVT-CONSIST")
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertEqual(entry.register_state.value, "INVALID")
            self.assertIsNone(entry.active_version)

            state = service.assign_workflow_roles(state, editors={"owner-1"}, reviewers={"reviewer-1"}, approvers={"approver-1"})
            state = service.start_workflow(state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER)
            entry = registry.get_entry("DOC-EVT-CONSIST")
            assert entry is not None
            self.assertEqual(entry.register_state.value, "IN_PROGRESS")
            self.assertTrue(entry.is_findable)

            state = service.complete_editing(state, sign_request={"step": "edit_complete"}, actor_user_id="owner-1", actor_role=SystemRole.USER)
            state = service.accept_review(state, "reviewer-1", sign_request={"step": "review_accept"})
            state = service.accept_approval(state, "approver-1", sign_request={"step": "approve"})
            entry = registry.get_entry("DOC-EVT-CONSIST")
            assert entry is not None
            self.assertEqual(entry.register_state.value, "VALID")
            self.assertEqual(entry.active_version, 1)

            service.archive_approved(state, SystemRole.QMB, actor_user_id="qmb-1")
            entry = registry.get_entry("DOC-EVT-CONSIST")
            assert entry is not None
            self.assertEqual(entry.register_state.value, "ARCHIVED")
            self.assertIsNone(entry.active_version)
            self.assertFalse(entry.is_findable)


if __name__ == "__main__":
    unittest.main()
