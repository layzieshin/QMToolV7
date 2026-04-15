from __future__ import annotations

import unittest

from modules.documents.contracts import DocumentStatus, SystemRole, WorkflowProfile
from modules.documents.errors import PermissionDeniedError
from modules.documents.service import DocumentsService


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


class DocumentsAuthorizationMatrixTest(unittest.TestCase):
    def _base_state(self, *, document_id: str = "DOC-MATRIX"):
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version(document_id, 1, owner_user_id="owner-1")
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"reviewer-1"},
            approvers={"approver-1"},
        )
        return service, state

    def test_start_workflow_owner_systemrole_matrix(self) -> None:
        cases = (
            ("owner-1", SystemRole.USER, True),
            ("other-user", SystemRole.USER, False),
            ("qmb-user", SystemRole.QMB, True),
            ("admin-user", SystemRole.ADMIN, True),
        )
        for actor_user_id, actor_role, allowed in cases:
            with self.subTest(actor_user_id=actor_user_id, actor_role=actor_role.value):
                service, state = self._base_state(document_id=f"DOC-START-{actor_user_id}")
                if allowed:
                    updated = service.start_workflow(
                        state,
                        WorkflowProfile.long_release_path(),
                        actor_user_id=actor_user_id,
                        actor_role=actor_role,
                    )
                    self.assertEqual(updated.status, DocumentStatus.IN_PROGRESS)
                else:
                    with self.assertRaises(PermissionDeniedError):
                        service.start_workflow(
                            state,
                            WorkflowProfile.long_release_path(),
                            actor_user_id=actor_user_id,
                            actor_role=actor_role,
                        )

    def test_complete_editing_authorization_matrix(self) -> None:
        cases = (
            ("owner-1", SystemRole.USER, True),
            ("editor-1", SystemRole.USER, True),
            ("other-user", SystemRole.USER, False),
            ("qmb-user", SystemRole.QMB, True),
            ("admin-user", SystemRole.ADMIN, True),
        )
        for actor_user_id, actor_role, allowed in cases:
            with self.subTest(actor_user_id=actor_user_id, actor_role=actor_role.value):
                service, state = self._base_state(document_id=f"DOC-EDIT-{actor_user_id}")
                state = service.start_workflow(state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER)
                if allowed:
                    updated = service.complete_editing(
                        state,
                        sign_request={"step": "edit_complete"},
                        actor_user_id=actor_user_id,
                        actor_role=actor_role,
                    )
                    self.assertEqual(updated.status, DocumentStatus.IN_REVIEW)
                else:
                    with self.assertRaises(PermissionDeniedError):
                        service.complete_editing(
                            state,
                            sign_request={"step": "edit_complete"},
                            actor_user_id=actor_user_id,
                            actor_role=actor_role,
                        )

    def test_abort_workflow_owner_systemrole_matrix(self) -> None:
        cases = (
            ("owner-1", SystemRole.USER, True),
            ("other-user", SystemRole.USER, False),
            ("qmb-user", SystemRole.QMB, True),
            ("admin-user", SystemRole.ADMIN, True),
        )
        for actor_user_id, actor_role, allowed in cases:
            with self.subTest(actor_user_id=actor_user_id, actor_role=actor_role.value):
                service, state = self._base_state(document_id=f"DOC-ABORT-{actor_user_id}")
                state = service.start_workflow(state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER)
                state = service.complete_editing(
                    state,
                    sign_request={"step": "edit_complete"},
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )
                if allowed:
                    updated = service.abort_workflow(state, actor_user_id=actor_user_id, actor_role=actor_role)
                    self.assertEqual(updated.status, DocumentStatus.PLANNED)
                else:
                    with self.assertRaises(PermissionDeniedError):
                        service.abort_workflow(state, actor_user_id=actor_user_id, actor_role=actor_role)

    def test_assign_roles_owner_gate_before_after_first_signature(self) -> None:
        before_cases = (
            ("owner-1", SystemRole.USER, True),
            ("other-user", SystemRole.USER, False),
            ("qmb-user", SystemRole.QMB, True),
            ("admin-user", SystemRole.ADMIN, True),
        )
        for actor_user_id, actor_role, allowed in before_cases:
            with self.subTest(phase="before_signature", actor_user_id=actor_user_id, actor_role=actor_role.value):
                service, state = self._base_state(document_id=f"DOC-ASSIGN-B-{actor_user_id}")
                if allowed:
                    updated = service.assign_workflow_roles(
                        state,
                        editors={"editor-2"},
                        reviewers={"reviewer-2"},
                        approvers={"approver-2"},
                        actor_user_id=actor_user_id,
                        actor_role=actor_role,
                    )
                    self.assertEqual(updated.assignments.editors, frozenset({"editor-2"}))
                else:
                    with self.assertRaises(PermissionDeniedError):
                        service.assign_workflow_roles(
                            state,
                            editors={"editor-2"},
                            reviewers={"reviewer-2"},
                            approvers={"approver-2"},
                            actor_user_id=actor_user_id,
                            actor_role=actor_role,
                        )

        after_cases = (
            ("owner-1", SystemRole.USER, False),
            ("qmb-user", SystemRole.QMB, True),
            ("admin-user", SystemRole.ADMIN, True),
        )
        for actor_user_id, actor_role, allowed in after_cases:
            with self.subTest(phase="after_signature", actor_user_id=actor_user_id, actor_role=actor_role.value):
                service, state = self._base_state(document_id=f"DOC-ASSIGN-A-{actor_user_id}")
                state = service.start_workflow(state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER)
                state = service.complete_editing(
                    state,
                    sign_request={"step": "edit_complete"},
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )
                if allowed:
                    updated = service.assign_workflow_roles(
                        state,
                        editors={"editor-1"},
                        reviewers={"reviewer-2"},
                        approvers={"approver-2"},
                        actor_user_id=actor_user_id,
                        actor_role=actor_role,
                    )
                    self.assertEqual(updated.assignments.reviewers, frozenset({"reviewer-2"}))
                else:
                    with self.assertRaises(PermissionDeniedError):
                        service.assign_workflow_roles(
                            state,
                            editors={"editor-1"},
                            reviewers={"reviewer-2"},
                            approvers={"approver-2"},
                            actor_user_id=actor_user_id,
                            actor_role=actor_role,
                        )

    def test_qmb_strict_previous_phase_locks_matrix(self) -> None:
        service, state = self._base_state(document_id="DOC-QMB-LOCKS")
        state = service.start_workflow(state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER)
        state = service.complete_editing(
            state,
            sign_request={"step": "edit_complete"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        with self.assertRaises(PermissionDeniedError):
            service.assign_workflow_roles(
                state,
                editors={"editor-2"},
                reviewers={"reviewer-1"},
                approvers={"approver-1"},
                actor_user_id="qmb-user",
                actor_role=SystemRole.QMB,
            )
        updated = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"reviewer-2"},
            approvers={"approver-2"},
            actor_user_id="qmb-user",
            actor_role=SystemRole.QMB,
        )
        self.assertEqual(updated.assignments.reviewers, frozenset({"reviewer-2"}))
        self.assertEqual(updated.assignments.approvers, frozenset({"approver-2"}))

        updated = service.accept_review(updated, "reviewer-2", sign_request={"step": "review_accept"})
        with self.assertRaises(PermissionDeniedError):
            service.assign_workflow_roles(
                updated,
                editors={"editor-1"},
                reviewers={"reviewer-9"},
                approvers={"approver-2"},
                actor_user_id="qmb-user",
                actor_role=SystemRole.QMB,
            )
        allowed = service.assign_workflow_roles(
            updated,
            editors={"editor-1"},
            reviewers={"reviewer-2"},
            approvers={"approver-9"},
            actor_user_id="qmb-user",
            actor_role=SystemRole.QMB,
        )
        self.assertEqual(allowed.assignments.approvers, frozenset({"approver-9"}))

        allowed = service.accept_approval(allowed, "approver-9", sign_request={"step": "approve"})
        with self.assertRaises(PermissionDeniedError):
            service.assign_workflow_roles(
                allowed,
                editors={"editor-1"},
                reviewers={"reviewer-2"},
                approvers={"approver-1"},
                actor_user_id="qmb-user",
                actor_role=SystemRole.QMB,
            )


if __name__ == "__main__":
    unittest.main()
