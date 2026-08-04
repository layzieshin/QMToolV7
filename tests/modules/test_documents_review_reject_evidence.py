import json
import tempfile
import unittest
from pathlib import Path

from modules.documents.contracts import DocumentStatus, RejectionReason, SystemRole, WorkflowProfile
from modules.documents.errors import InvalidTransitionError, PermissionDeniedError
from modules.documents.service import DocumentsService
from tests.database_helpers import make_documents_service_with_profiles
from pathlib import Path
import tempfile
from qm_platform.events.event_bus import EventBus
from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.logging.audit_logger import AuditLogger


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


class DocumentsReviewRejectEvidenceTest(unittest.TestCase):
    @staticmethod
    def _rejection_reason() -> RejectionReason:
        return RejectionReason(
            template_id="RR-1",
            template_text="Missing evidence",
            free_text="Add the referenced SOP section.",
        )

    @staticmethod
    def _service(*, event_bus: EventBus | None = None, audit_file: Path | None = None) -> DocumentsService:
        audit_logger = AuditLogger(audit_file) if audit_file is not None else None
        root = Path(tempfile.mkdtemp(prefix="qmtool-docs-review-"))
        service, _ = make_documents_service_with_profiles(
            root / "documents.db",
            event_bus=event_bus,
            audit_logger=audit_logger,
            signature_api=_FakeSignatureApi(),
        )
        return service

    @staticmethod
    def _state_in_review(service: DocumentsService, *, document_id: str = "DOC-REVIEW-REJECT"):
        state = service.create_document_version(document_id, 1, owner_user_id="owner-1")
        state = service.assign_workflow_roles(
            state,
            editors={"owner-1"},
            reviewers={"reviewer-1"},
            approvers={"approver-1"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        state = service.start_workflow(
            state,
            WorkflowProfile.long_release_path(),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        return service.complete_editing(
            state,
            sign_request={"step": "edit_complete"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )

    def test_reject_review_is_only_allowed_in_review_status(self) -> None:
        service = self._service()
        state = service.create_document_version("DOC-REJECT-STATUS", 1, owner_user_id="owner-1")
        state = service.assign_workflow_roles(
            state,
            editors={"owner-1"},
            reviewers={"reviewer-1"},
            approvers={"approver-1"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )

        with self.assertRaises(InvalidTransitionError):
            service.reject_review(state, "reviewer-1", self._rejection_reason())

    def test_reject_review_actor_must_be_assigned_reviewer(self) -> None:
        service = self._service()
        state = self._state_in_review(service, document_id="DOC-REJECT-ACTOR")

        with self.assertRaises(PermissionDeniedError):
            service.reject_review(state, "not-a-reviewer", self._rejection_reason())

    def test_reject_review_records_event_and_audit_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_file = Path(tmp) / "audit.log"
            event_bus = EventBus()
            events: list[EventEnvelope] = []
            event_bus.subscribe("domain.documents.review.rejected.v1", lambda event: events.append(event))
            service = self._service(event_bus=event_bus, audit_file=audit_file)
            state = self._state_in_review(service, document_id="DOC-REJECT-EVIDENCE")

            updated = service.reject_review(state, "reviewer-1", self._rejection_reason())

            self.assertEqual(updated.status, DocumentStatus.IN_PROGRESS)
            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event.name, "domain.documents.review.rejected.v1")
            self.assertTrue(event.event_id)
            self.assertTrue(event.correlation_id)
            # Baseline remains ketten-eingeschraenkt: default correlation is not a chain claim.
            self.assertIsNone(event.causation_id)
            self.assertEqual(event.actor_user_id, "reviewer-1")
            self.assertEqual(event.payload["actor_user_id"], "reviewer-1")
            self.assertEqual(event.payload["document_id"], "DOC-REJECT-EVIDENCE")
            self.assertEqual(event.payload["version"], 1)

            audit_entries = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines()]
            review_reject_entries = [
                entry
                for entry in audit_entries
                if entry["action"] == "documents.workflow.review.rejected"
            ]
            self.assertEqual(len(review_reject_entries), 1)
            audit_entry = review_reject_entries[0]
            self.assertEqual(audit_entry["actor"], "reviewer-1")
            self.assertEqual(audit_entry["target"], "DOC-REJECT-EVIDENCE:1")
            self.assertEqual(audit_entry["reason"], "Missing evidence")
            self.assertNotIn("correlation_id", audit_entry)
            self.assertNotIn("causation_id", audit_entry)


if __name__ == "__main__":
    unittest.main()
