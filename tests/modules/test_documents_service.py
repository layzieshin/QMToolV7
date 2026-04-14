from __future__ import annotations

import unittest

from modules.documents.contracts import (
    DocumentStatus,
    RejectionReason,
    SystemRole,
    WorkflowProfile,
)
from modules.documents.errors import PermissionDeniedError, ValidationError
from modules.documents.service import DocumentsService


class _FakeSignatureApi:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def sign_with_fixed_position(self, request: object) -> object:
        self.calls.append(request)
        return request


class DocumentsServiceTest(unittest.TestCase):
    def test_long_release_profile_enforces_four_eyes(self) -> None:
        signature_api = _FakeSignatureApi()
        service = DocumentsService(signature_api=signature_api)
        state = service.create_document_version("DOC-1", 1)
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"alice"},
            approvers={"alice", "bob"},
        )
        state = service.start_workflow(state, WorkflowProfile.long_release_path())
        state = service.complete_editing(state, sign_request={"step": "edit_complete"})
        state = service.accept_review(state, "alice")
        with self.assertRaises(PermissionDeniedError):
            service.accept_approval(state, "alice", sign_request={"step": "approve"})
        state = service.accept_approval(state, "bob", sign_request={"step": "approve"})
        self.assertEqual(state.status, DocumentStatus.APPROVED)
        self.assertEqual(len(signature_api.calls), 2)

    def test_custom_profile_can_disable_four_eyes(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-2", 1)
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"alice"},
            approvers={"alice"},
        )
        profile = WorkflowProfile(
            profile_id="custom_fast",
            label="Custom Fast Path",
            phases=(
                DocumentStatus.IN_PROGRESS,
                DocumentStatus.IN_REVIEW,
                DocumentStatus.IN_APPROVAL,
                DocumentStatus.APPROVED,
            ),
            four_eyes_required=False,
        )
        state = service.start_workflow(state, profile)
        state = service.complete_editing(state)
        state = service.accept_review(state, "alice")
        state = service.accept_approval(state, "alice")
        self.assertEqual(state.status, DocumentStatus.APPROVED)

    def test_reject_requires_text_or_template(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-3", 1)
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"rev-1"},
            approvers={"app-1"},
        )
        state = service.start_workflow(state, WorkflowProfile.long_release_path())
        state = service.complete_editing(state, sign_request={"step": "edit_complete"})
        with self.assertRaises(ValidationError):
            service.reject_review(state, "rev-1", RejectionReason())
        state = service.reject_review(
            state,
            "rev-1",
            RejectionReason(template_id="TPL-1", template_text="Missing references", free_text="Add SOP link."),
        )
        self.assertEqual(state.status, DocumentStatus.IN_PROGRESS)

    def test_archive_approved_requires_qmb_or_admin(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-4", 1)
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"rev-1"},
            approvers={"app-1"},
        )
        state = service.start_workflow(state, WorkflowProfile.long_release_path())
        state = service.complete_editing(state, sign_request={"step": "edit_complete"})
        state = service.accept_review(state, "rev-1")
        state = service.accept_approval(state, "app-1", sign_request={"step": "approve"})
        with self.assertRaises(PermissionDeniedError):
            service.archive_approved(state, SystemRole.USER)
        state = service.archive_approved(state, SystemRole.QMB)
        self.assertEqual(state.status, DocumentStatus.ARCHIVED)

    def test_annual_extension_limited_to_three_per_version(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-5", 1)
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"rev-1"},
            approvers={"app-1"},
        )
        state = service.start_workflow(state, WorkflowProfile.long_release_path())
        state = service.complete_editing(state, sign_request={"step": "edit_complete"})
        state = service.accept_review(state, "rev-1")
        state = service.accept_approval(state, "app-1", sign_request={"step": "approve"})

        state, must_recreate = service.extend_annual_validity(state, signature_present=True)
        self.assertFalse(must_recreate)
        state, must_recreate = service.extend_annual_validity(state, signature_present=True)
        self.assertFalse(must_recreate)
        state, must_recreate = service.extend_annual_validity(state, signature_present=True)
        self.assertFalse(must_recreate)
        self.assertEqual(state.extension_count, 3)

        state_after_limit, must_recreate = service.extend_annual_validity(state, signature_present=True)
        self.assertTrue(must_recreate)
        self.assertEqual(state_after_limit.extension_count, 3)

    def test_pool_query_lists_documents_by_status(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        planned = service.create_document_version("DOC-PLAN", 1)
        approved = service.create_document_version("DOC-APP", 1)
        approved = service.assign_workflow_roles(
            approved,
            editors={"editor-1"},
            reviewers={"rev-1"},
            approvers={"app-1"},
        )
        approved = service.start_workflow(approved, WorkflowProfile.long_release_path())
        approved = service.complete_editing(approved, sign_request={"step": "edit_complete"})
        approved = service.accept_review(approved, "rev-1")
        approved = service.accept_approval(approved, "app-1", sign_request={"step": "approve"})

        planned_entries = service.list_by_status(DocumentStatus.PLANNED)
        approved_entries = service.list_by_status(DocumentStatus.APPROVED)
        self.assertEqual([(d.document_id, d.version) for d in planned_entries], [("DOC-PLAN", 1)])
        self.assertEqual([(d.document_id, d.version) for d in approved_entries], [("DOC-APP", 1)])

    def test_signature_required_transition_fails_without_request(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-SIG", 1)
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"rev-1"},
            approvers={"app-1"},
        )
        state = service.start_workflow(state, WorkflowProfile.long_release_path())
        with self.assertRaises(ValidationError):
            service.complete_editing(state)

    def test_workflow_start_requires_all_role_sets(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-ROLE", 1)
        with self.assertRaises(ValidationError):
            service.start_workflow(state, WorkflowProfile.long_release_path())

    def test_owner_cannot_change_roles_after_first_edit_signature(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-OWNER", 1, owner_user_id="owner-1")
        state = service.assign_workflow_roles(
            state,
            editors={"owner-1"},
            reviewers={"rev-1"},
            approvers={"app-1"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        state = service.start_workflow(
            state,
            WorkflowProfile.long_release_path(),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        state = service.complete_editing(
            state,
            sign_request={"step": "edit_complete"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        with self.assertRaises(PermissionDeniedError):
            service.assign_workflow_roles(
                state,
                editors={"owner-1", "editor-2"},
                reviewers={"rev-1"},
                approvers={"app-1"},
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            )

    def test_qmb_can_only_change_roles_of_open_phases(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-QMB", 1, owner_user_id="owner-1")
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"reviewer-1"},
            approvers={"approver-1"},
        )
        state = service.start_workflow(state, WorkflowProfile.long_release_path())
        state = service.complete_editing(state, sign_request={"step": "edit_complete"})
        with self.assertRaises(PermissionDeniedError):
            service.assign_workflow_roles(
                state,
                editors={"editor-2"},
                reviewers={"reviewer-1"},
                approvers={"approver-1"},
                actor_user_id="qmb",
                actor_role=SystemRole.QMB,
            )
        updated = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"reviewer-2"},
            approvers={"approver-2"},
            actor_user_id="qmb",
            actor_role=SystemRole.QMB,
        )
        self.assertEqual(updated.assignments.reviewers, frozenset({"reviewer-2"}))
        self.assertEqual(updated.assignments.approvers, frozenset({"approver-2"}))


if __name__ == "__main__":
    unittest.main()

