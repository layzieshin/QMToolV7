from __future__ import annotations

import unittest

from dataclasses import replace
from pathlib import Path
import tempfile

from modules.documents.contracts import DocumentStatus, SystemRole, WorkflowProfile
from modules.documents.errors import DocumentConflictError, PermissionDeniedError
from modules.documents.service import DocumentsService
from tests.database_helpers import make_documents_service_with_profiles


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


class DocumentsAuthorizationMatrixTest(unittest.TestCase):
    def _base_state(self, *, document_id: str = "DOC-MATRIX"):
        service = make_documents_service_with_profiles(Path(tempfile.mkdtemp(prefix="qmtool-docs-t-")) / "documents.db", signature_api=_FakeSignatureApi())[0]
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
            ("admin-user", SystemRole.ADMIN, False),
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
            ("admin-user", SystemRole.ADMIN, False),
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
            ("admin-user", SystemRole.ADMIN, False),
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
            ("admin-user", SystemRole.ADMIN, False),
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
            ("admin-user", SystemRole.ADMIN, False),
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

    def test_policy_on_locked_current_rejects_stale_action(self) -> None:
        service, state = self._base_state(document_id="DOC-POLICY-CURRENT")
        started = service.start_workflow(
            state,
            WorkflowProfile.long_release_path(),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        with self.assertRaises(PermissionDeniedError):
            service.mutate_version_if_current(
                started.document_id,
                started.version,
                started.last_event_id,
                lambda current: current,
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
                action="start",
            )

    def _archive_approved_version(self, document_id: str):
        service, state = self._base_state(document_id=document_id)
        state = service.start_workflow(
            state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER
        )
        state = service.complete_editing(
            state, sign_request={"step": "edit_complete"}, actor_user_id="owner-1", actor_role=SystemRole.USER
        )
        state = service.accept_review(state, "reviewer-1", sign_request={"step": "review_accept"})
        state = service.accept_approval(state, "approver-1", sign_request={"step": "approve"})
        archived = service.archive_approved(state, SystemRole.QMB, actor_user_id="qmb-user")
        return service, archived

    def test_new_version_after_archive_requires_qmb_on_public_api(self) -> None:
        from modules.documents.api import DocumentsWorkflowApi

        service, archived = self._archive_approved_version("DOC-NEW-VER")
        api = DocumentsWorkflowApi(service)
        source_token = archived.last_event_id
        with self.assertRaises(PermissionDeniedError):
            api.create_new_version_after_archive(
                archived,
                2,
                expected_last_event_id=source_token,
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
            )
        self.assertIsNone(service.get_document_version(archived.document_id, 2))
        unchanged = service.get_document_version(archived.document_id, archived.version)
        self.assertEqual(unchanged.last_event_id, source_token)
        self.assertIsNone(unchanged.superseded_by_version)

        created = api.create_new_version_after_archive(
            archived,
            2,
            expected_last_event_id=source_token,
            actor_user_id="qmb-user",
            actor_role=SystemRole.QMB,
        )
        self.assertEqual(created.version, 2)
        self.assertEqual(created.status, DocumentStatus.PLANNED)
        self.assertIsNotNone(created.last_event_id)
        self.assertNotEqual(created.last_event_id, "")
        source_after = service.get_document_version(archived.document_id, archived.version)
        self.assertEqual(source_after.superseded_by_version, 2)
        self.assertNotEqual(source_after.last_event_id, source_token)
        self.assertEqual(source_after.last_event_id, created.last_event_id)

        with self.assertRaises(DocumentConflictError):
            api.create_new_version_after_archive(
                archived,
                3,
                expected_last_event_id=source_token,
                actor_user_id="qmb-user",
                actor_role=SystemRole.QMB,
            )
        self.assertIsNone(service.get_document_version(archived.document_id, 3))
        still_v2 = service.get_document_version(archived.document_id, 2)
        self.assertEqual(still_v2.version, 2)
        self.assertEqual(still_v2.last_event_id, created.last_event_id)

    def test_stale_direct_qmb_new_version_conflicts_without_mutation(self) -> None:
        from modules.documents.api import DocumentsWorkflowApi

        service, archived = self._archive_approved_version("DOC-NEW-VER-STALE")
        api = DocumentsWorkflowApi(service)
        stale_token = archived.last_event_id
        # Real product mutation advances the archived version token.
        bumped = api.mutate_version_if_current(
            archived,
            archived.last_event_id,
            lambda current: api.update_version_metadata(
                current,
                title="archived-bump",
                actor_user_id="qmb-user",
                actor_role=SystemRole.QMB,
            ),
            actor_user_id="qmb-user",
            actor_role=SystemRole.QMB,
            action="update_metadata",
        )
        self.assertNotEqual(bumped.last_event_id, stale_token)
        with self.assertRaises(DocumentConflictError):
            api.create_new_version_after_archive(
                archived,
                2,
                expected_last_event_id=stale_token,
                actor_user_id="qmb-user",
                actor_role=SystemRole.QMB,
            )
        self.assertIsNone(service.get_document_version(archived.document_id, 2))
        source = service.get_document_version(archived.document_id, archived.version)
        self.assertIsNone(source.superseded_by_version)
        self.assertEqual(source.last_event_id, bumped.last_event_id)
    def test_no_precondition_default_uses_locked_current_token(self) -> None:
        from modules.documents.api import DocumentsWorkflowApi

        service, state = self._base_state(document_id="DOC-SENTINEL-OK")
        api = DocumentsWorkflowApi(service)
        # Omit expected_last_event_id → legacy sentinel remaps to state.last_event_id.
        started = api.start_workflow(
            state,
            WorkflowProfile.long_release_path(),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        self.assertEqual(started.status, DocumentStatus.IN_PROGRESS)

    def test_no_precondition_stale_caller_state_conflicts(self) -> None:
        from modules.documents.api import DocumentsWorkflowApi

        service, state = self._base_state(document_id="DOC-SENTINEL-STALE")
        api = DocumentsWorkflowApi(service)
        started = api.start_workflow(
            state,
            WorkflowProfile.long_release_path(),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        stale_planned = replace(state, last_event_id=state.last_event_id)
        # Advance token via a real mutation on the started version.
        bumped = api.mutate_version_if_current(
            started,
            started.last_event_id,
            lambda current: api.update_version_metadata(
                current,
                title="post-start-title",
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            ),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
            action="update_metadata",
        )
        with self.assertRaises(DocumentConflictError):
            api.complete_editing(
                stale_planned,
                sign_request={"step": "edit_complete"},
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            )
        current = service.get_document_version(started.document_id, started.version)
        self.assertIsNotNone(current)
        self.assertEqual(current.status, DocumentStatus.IN_PROGRESS)
        self.assertEqual(current.last_event_id, bumped.last_event_id)
        self.assertEqual(current.title, "post-start-title")

    def test_metadata_and_change_request_consume_etag_on_public_api(self) -> None:
        from modules.documents.api import DocumentsWorkflowApi

        service, state = self._base_state(document_id="DOC-META-CR-ETAG")
        api = DocumentsWorkflowApi(service)
        prior_token = state.last_event_id
        updated = api.mutate_version_if_current(
            state,
            state.last_event_id,
            lambda current: api.update_version_metadata(
                current,
                title="Retitled",
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            ),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
            action="update_metadata",
        )
        self.assertEqual(updated.title, "Retitled")
        self.assertIsNotNone(updated.last_event_id)
        self.assertNotEqual(updated.last_event_id, prior_token)
        persisted = service.get_document_version(state.document_id, state.version)
        self.assertEqual(persisted.last_event_id, updated.last_event_id)
        with self.assertRaises(DocumentConflictError):
            api.mutate_version_if_current(
                state,
                prior_token,
                lambda current: api.update_version_metadata(
                    current,
                    title="Again",
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                ),
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
                action="update_metadata",
            )
        still = service.get_document_version(state.document_id, state.version)
        self.assertEqual(still.title, "Retitled")
        self.assertEqual(still.last_event_id, updated.last_event_id)

        with self.assertRaises(PermissionDeniedError):
            api.mutate_version_if_current(
                updated,
                updated.last_event_id,
                lambda current: api.update_version_metadata(
                    current,
                    title="AdminNo",
                    actor_user_id="admin-user",
                    actor_role=SystemRole.ADMIN,
                ),
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
                action="update_metadata",
            )
        denied = service.get_document_version(state.document_id, state.version)
        self.assertEqual(denied.title, "Retitled")
        self.assertEqual(denied.last_event_id, updated.last_event_id)

        cr_prior = updated.last_event_id
        with_cr = api.mutate_version_if_current(
            updated,
            updated.last_event_id,
            lambda current: api.add_change_request(
                current,
                change_id="CR-1",
                reason="fix typo",
                impact_refs=["SOP-1"],
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            ),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
            action="change_requests",
        )
        self.assertNotEqual(with_cr.last_event_id, cr_prior)
        self.assertEqual(len(service.list_change_requests(with_cr)), 1)
        with self.assertRaises(DocumentConflictError):
            api.mutate_version_if_current(
                updated,
                cr_prior,
                lambda current: api.add_change_request(
                    current,
                    change_id="CR-2",
                    reason="dup",
                    impact_refs=[],
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                ),
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
                action="change_requests",
            )
        after_conflict = service.get_document_version(state.document_id, state.version)
        self.assertEqual(len(service.list_change_requests(after_conflict)), 1)
        self.assertEqual(after_conflict.last_event_id, with_cr.last_event_id)

    def _to_in_review(self, document_id: str):
        from modules.documents.api import DocumentsWorkflowApi

        service, state = self._base_state(document_id=document_id)
        api = DocumentsWorkflowApi(service)
        state = api.start_workflow(
            state,
            WorkflowProfile.long_release_path(),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        state = api.complete_editing(
            state,
            sign_request={"step": "edit_complete"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        return service, api, state

    def test_review_and_approval_assignment_negatives_on_public_api(self) -> None:
        from modules.documents.contracts import RejectionReason

        service, api, in_review = self._to_in_review("DOC-REV-API")
        with self.assertRaises(PermissionDeniedError):
            api.accept_review(
                in_review,
                actor_user_id="editor-1",
                actor_role=SystemRole.USER,
                sign_request={"step": "review_accept"},
            )
        with self.assertRaises(PermissionDeniedError):
            api.accept_review(
                in_review,
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
                sign_request={"step": "review_accept"},
            )
        with self.assertRaises(PermissionDeniedError):
            api.reject_review(
                in_review,
                RejectionReason(template_id="T1", template_text="missing", free_text="x"),
                actor_user_id="approver-1",
                actor_role=SystemRole.USER,
            )
        accepted = api.accept_review(
            in_review,
            actor_user_id="reviewer-1",
            actor_role=SystemRole.USER,
            sign_request={"step": "review_accept"},
        )
        self.assertEqual(accepted.status, DocumentStatus.IN_APPROVAL)
        with self.assertRaises(PermissionDeniedError):
            api.accept_approval(
                accepted,
                actor_user_id="reviewer-1",
                actor_role=SystemRole.USER,
                sign_request={"step": "approve"},
            )
        with self.assertRaises(PermissionDeniedError):
            api.reject_approval(
                accepted,
                RejectionReason(template_id="T1", template_text="missing", free_text="x"),
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
            )
        approved = api.accept_approval(
            accepted,
            actor_user_id="approver-1",
            actor_role=SystemRole.USER,
            sign_request={"step": "approve"},
        )
        self.assertEqual(approved.status, DocumentStatus.APPROVED)

    def test_review_and_approval_reject_execute_on_public_api(self) -> None:
        """Positive Public-API execution for review_reject and approval_reject."""
        from modules.documents.contracts import RejectionReason

        reason = RejectionReason(template_id="T-REJ", template_text="needs rework", free_text=None)
        _service, api, in_review = self._to_in_review("DOC-REV-REJ")
        prior = in_review.last_event_id
        rejected_review = api.reject_review(
            in_review,
            reason,
            actor_user_id="reviewer-1",
            actor_role=SystemRole.USER,
            expected_last_event_id=prior,
        )
        self.assertEqual(rejected_review.status, DocumentStatus.IN_PROGRESS)
        self.assertNotEqual(rejected_review.last_event_id, prior)

        again = api.complete_editing(
            rejected_review,
            sign_request={"step": "edit_complete"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        in_approval = api.accept_review(
            again,
            actor_user_id="reviewer-1",
            actor_role=SystemRole.USER,
            sign_request={"step": "review_accept"},
        )
        token_before_approval_reject = in_approval.last_event_id
        rejected_approval = api.reject_approval(
            in_approval,
            reason,
            actor_user_id="approver-1",
            actor_role=SystemRole.USER,
            expected_last_event_id=token_before_approval_reject,
        )
        self.assertEqual(rejected_approval.status, DocumentStatus.IN_PROGRESS)
        self.assertNotEqual(rejected_approval.last_event_id, token_before_approval_reject)
        with self.assertRaises(DocumentConflictError):
            api.reject_approval(
                in_approval,
                reason,
                actor_user_id="approver-1",
                actor_role=SystemRole.USER,
                expected_last_event_id=token_before_approval_reject,
            )

    def test_assign_start_abort_execute_on_public_api(self) -> None:
        """Positive and negative Public-API execution for assign_roles, start, abort."""
        from modules.documents.api import DocumentsWorkflowApi

        service, state = self._base_state(document_id="DOC-ASA-API")
        api = DocumentsWorkflowApi(service)
        with self.assertRaises(PermissionDeniedError):
            api.assign_workflow_roles(
                state,
                editors={"editor-1"},
                reviewers={"reviewer-1"},
                approvers={"approver-1"},
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
                expected_last_event_id=state.last_event_id,
            )
        assigned = api.assign_workflow_roles(
            state,
            editors={"editor-2"},
            reviewers={"reviewer-1"},
            approvers={"approver-1"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
            expected_last_event_id=state.last_event_id,
        )
        self.assertEqual(assigned.assignments.editors, frozenset({"editor-2"}))
        self.assertNotEqual(assigned.last_event_id, state.last_event_id)

        with self.assertRaises(PermissionDeniedError):
            api.start_workflow(
                assigned,
                WorkflowProfile.long_release_path(),
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
                expected_last_event_id=assigned.last_event_id,
            )
        started = api.start_workflow(
            assigned,
            WorkflowProfile.long_release_path(),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
            expected_last_event_id=assigned.last_event_id,
        )
        self.assertEqual(started.status, DocumentStatus.IN_PROGRESS)
        self.assertNotEqual(started.last_event_id, assigned.last_event_id)

        with self.assertRaises(PermissionDeniedError):
            api.abort_workflow(
                started,
                actor_user_id="editor-2",
                actor_role=SystemRole.USER,
                expected_last_event_id=started.last_event_id,
            )
        aborted = api.abort_workflow(
            started,
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
            expected_last_event_id=started.last_event_id,
        )
        self.assertEqual(aborted.status, DocumentStatus.PLANNED)
        self.assertNotEqual(aborted.last_event_id, started.last_event_id)

    def test_archive_extend_metadata_cr_header_admin_negatives_and_stale(self) -> None:
        from modules.documents.api import DocumentsCommentsApi, DocumentsWorkflowApi
        from modules.documents.contracts import WorkflowCommentContext

        service, archived = self._archive_approved_version("DOC-LIFE-API")
        # Re-build an APPROVED state for archive/extend/metadata/CR coverage.
        service2, state = self._base_state(document_id="DOC-APPROVED-API")
        api = DocumentsWorkflowApi(service2)
        state = api.start_workflow(
            state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER
        )
        state = api.complete_editing(
            state, sign_request={"step": "edit_complete"}, actor_user_id="owner-1", actor_role=SystemRole.USER
        )
        state = api.accept_review(
            state, actor_user_id="reviewer-1", actor_role=SystemRole.USER, sign_request={"step": "review_accept"}
        )
        approved = api.accept_approval(
            state, actor_user_id="approver-1", actor_role=SystemRole.USER, sign_request={"step": "approve"}
        )

        with self.assertRaises(PermissionDeniedError):
            api.mutate_version_if_current(
                approved,
                approved.last_event_id,
                lambda current: api.archive_approved(current, SystemRole.ADMIN, actor_user_id="admin-user"),
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
                action="archive",
            )
        with self.assertRaises(PermissionDeniedError):
            api.mutate_version_if_current(
                approved,
                approved.last_event_id,
                lambda current: current,
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
                action="extend_validity",
            )
        with self.assertRaises(PermissionDeniedError):
            api.mutate_version_if_current(
                approved,
                approved.last_event_id,
                lambda current: api.update_version_metadata(
                    current, title="nope", actor_user_id="admin-user", actor_role=SystemRole.ADMIN
                ),
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
                action="update_metadata",
            )
        with self.assertRaises(PermissionDeniedError):
            api.mutate_version_if_current(
                approved,
                approved.last_event_id,
                lambda current: api.add_change_request(
                    current,
                    change_id="CR-ADMIN",
                    reason="nope",
                    impact_refs=[],
                    actor_user_id="admin-user",
                    actor_role=SystemRole.ADMIN,
                ),
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
                action="change_requests",
            )

        header = service2.get_document_header(approved.document_id)
        self.assertIsNotNone(header)
        with self.assertRaises(PermissionDeniedError):
            service2.update_document_header_if_current(
                approved.document_id,
                expected_updated_at=header.updated_at.isoformat(),
                actor_user_id="admin-user",
                actor_role=SystemRole.ADMIN,
                department="X",
            )

        # comments: not allowed on APPROVED/ARCHIVED
        comments_api = DocumentsCommentsApi(service2)
        with self.assertRaises(PermissionDeniedError):
            comments_api.create_pdf_workflow_comment_if_current(
                approved,
                expected_last_event_id=approved.last_event_id,
                context=WorkflowCommentContext.PDF_REVIEW,
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
                page_number=1,
                comment_text="late",
            )

        # stale archive token via real metadata mutation → conflict, no status change
        stale_token = approved.last_event_id
        bumped = api.mutate_version_if_current(
            approved,
            approved.last_event_id,
            lambda current: api.update_version_metadata(
                current,
                title="approved-bump",
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            ),
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
            action="update_metadata",
        )
        with self.assertRaises(DocumentConflictError):
            api.mutate_version_if_current(
                approved,
                stale_token,
                lambda current: api.archive_approved(current, SystemRole.QMB, actor_user_id="qmb-user"),
                actor_user_id="qmb-user",
                actor_role=SystemRole.QMB,
                action="archive",
            )
        current = service2.get_document_version(approved.document_id, approved.version)
        self.assertEqual(current.status, DocumentStatus.APPROVED)
        self.assertEqual(current.last_event_id, bumped.last_event_id)

        archived_ok = api.mutate_version_if_current(
            bumped,
            bumped.last_event_id,
            lambda current: api.archive_approved(current, SystemRole.QMB, actor_user_id="qmb-user"),
            actor_user_id="qmb-user",
            actor_role=SystemRole.QMB,
            action="archive",
        )
        self.assertEqual(archived_ok.status, DocumentStatus.ARCHIVED)
        self.assertEqual(archived.status, DocumentStatus.ARCHIVED)

        # extend_validity: admin deny already above; QMB positive on APPROVED via mutate
        service3, state3 = self._base_state(document_id="DOC-EXTEND-API")
        api3 = DocumentsWorkflowApi(service3)
        state3 = api3.start_workflow(
            state3, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER
        )
        state3 = api3.complete_editing(
            state3, sign_request={"step": "edit_complete"}, actor_user_id="owner-1", actor_role=SystemRole.USER
        )
        state3 = api3.accept_review(
            state3, actor_user_id="reviewer-1", actor_role=SystemRole.USER, sign_request={"step": "review_accept"}
        )
        approved3 = api3.accept_approval(
            state3, actor_user_id="approver-1", actor_role=SystemRole.USER, sign_request={"step": "approve"}
        )
        from modules.documents.contracts import ValidityExtensionOutcome

        extended, is_maxed = api3.mutate_version_if_current(
            approved3,
            approved3.last_event_id,
            lambda current: api3.extend_annual_validity(
                current,
                actor_user_id="qmb-user",
                signature_present=True,
                duration_days=365,
                reason="annual",
                review_outcome=ValidityExtensionOutcome.UNCHANGED,
            ),
            actor_user_id="qmb-user",
            actor_role=SystemRole.QMB,
            action="extend_validity",
        )
        self.assertFalse(is_maxed)
        self.assertEqual(extended.extension_count, 1)
        self.assertNotEqual(extended.last_event_id, approved3.last_event_id)

    def test_open_source_reauthorization_on_artifact_read_path(self) -> None:
        from datetime import datetime, timezone

        from modules.documents.api import DocumentsArtifactsApi, DocumentsWorkflowApi
        from modules.documents.contracts import ArtifactType
        from modules.documents.storage import FileSystemDocumentsStorage
        from modules.usermanagement.contracts import issue_user_context

        root = Path(tempfile.mkdtemp(prefix="qmtool-docs-open-"))
        storage = FileSystemDocumentsStorage(root / "artifacts")
        service = make_documents_service_with_profiles(
            root / "documents.db",
            signature_api=_FakeSignatureApi(),
            storage_port=storage,
        )[0]
        pdf = root / "source.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        state = service.create_document_version("DOC-OPEN", 1, owner_user_id="owner-1")
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"reviewer-1"},
            approvers={"approver-1"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        service.import_existing_pdf(
            "DOC-OPEN", 1, pdf, actor_user_id="owner-1", actor_role=SystemRole.USER
        )
        api = DocumentsWorkflowApi(service)
        api.start_workflow(
            state, WorkflowProfile.long_release_path(), actor_user_id="owner-1", actor_role=SystemRole.USER
        )
        artifacts = [a for a in service.list_artifacts("DOC-OPEN", 1) if a.artifact_type == ArtifactType.SOURCE_PDF]
        self.assertTrue(artifacts)
        artifact_id = artifacts[0].artifact_id
        artifacts_api = DocumentsArtifactsApi(service, app_home=root, artifacts_root=root / "artifacts")

        def _actor(user_id: str) -> object:
            return issue_user_context(
                user_id=user_id,
                session_id=f"{user_id}-session",
                request_id=f"{user_id}-request",
                username=user_id,
                global_roles=frozenset({"USER"}),
                is_qmb=False,
                authenticated_at=datetime.now(timezone.utc),
            )

        editor = _actor("editor-1")
        reviewer = _actor("reviewer-1")
        allowed = artifacts_api.get_artifact_by_id_for_actor(artifact_id, editor)
        self.assertIsNotNone(allowed)
        data = artifacts_api.read_artifact_bytes_for_actor(artifact_id, editor)
        self.assertTrue(data.startswith(b"%PDF"))
        denied_meta = artifacts_api.get_artifact_by_id_for_actor(artifact_id, reviewer)
        self.assertIsNone(denied_meta)
        with self.assertRaises(PermissionDeniedError):
            artifacts_api.read_artifact_bytes_for_actor(artifact_id, reviewer)

    def test_header_and_comment_status_token_families(self) -> None:
        from modules.documents.api import DocumentsCommentsApi, DocumentsWorkflowApi
        from modules.documents.contracts import WorkflowCommentContext, WorkflowCommentStatus
        from modules.documents.errors import CommentConflictError, HeaderConflictError

        service, api, in_review = self._to_in_review("DOC-TOKEN-FAM")
        header = service.get_document_header(in_review.document_id)
        self.assertIsNotNone(header)
        prior = header.updated_at.isoformat()
        updated_header = service.update_document_header_if_current(
            in_review.document_id,
            expected_updated_at=prior,
            actor_user_id="qmb-user",
            actor_role=SystemRole.QMB,
            department="QA",
        )
        self.assertEqual(updated_header.department, "QA")
        self.assertNotEqual(updated_header.updated_at.isoformat(), prior)
        with self.assertRaises(HeaderConflictError):
            service.update_document_header_if_current(
                in_review.document_id,
                expected_updated_at=prior,
                actor_user_id="qmb-user",
                actor_role=SystemRole.QMB,
                department="Other",
            )
        still = service.get_document_header(in_review.document_id)
        self.assertEqual(still.department, "QA")

        comments_api = DocumentsCommentsApi(service)
        created = comments_api.create_pdf_workflow_comment_if_current(
            in_review,
            expected_last_event_id=in_review.last_event_id,
            context=WorkflowCommentContext.PDF_REVIEW,
            actor_user_id="reviewer-1",
            actor_role=SystemRole.USER,
            page_number=1,
            comment_text="note",
        )
        status_token = created.updated_at.isoformat()
        changed = comments_api.set_workflow_comment_status_if_current(
            created.comment_id,
            expected_updated_at=status_token,
            new_status=WorkflowCommentStatus.RESOLVED,
            actor_user_id="reviewer-1",
            actor_role=SystemRole.USER,
        )
        self.assertEqual(changed.status, WorkflowCommentStatus.RESOLVED)
        self.assertNotEqual(changed.updated_at.isoformat(), status_token)
        with self.assertRaises(CommentConflictError):
            comments_api.set_workflow_comment_status_if_current(
                created.comment_id,
                expected_updated_at=status_token,
                new_status=WorkflowCommentStatus.ACTIVE,
                actor_user_id="reviewer-1",
                actor_role=SystemRole.USER,
            )

    def test_sixteen_action_execution_coverage_table(self) -> None:
        """Coverage *index* for all ACTION_IDS → primary execution test methods.

        This is not itself the execution matrix: it only asserts every ACTION_ID
        maps to a named test method that exists. Positive/negative Public-API
        or HTTP execution evidence lives in those referenced methods.
        """
        from modules.documents.workflow_policy import ACTION_IDS

        coverage = {
            "assign_roles": "test_assign_start_abort_execute_on_public_api",
            "start": "test_assign_start_abort_execute_on_public_api",
            "open_source": "test_open_source_reauthorization_on_artifact_read_path",
            "complete_editing": "test_complete_editing_authorization_matrix",
            "review_accept": "test_review_and_approval_assignment_negatives_on_public_api",
            "review_reject": "test_review_and_approval_reject_execute_on_public_api",
            "approval_accept": "test_review_and_approval_assignment_negatives_on_public_api",
            "approval_reject": "test_review_and_approval_reject_execute_on_public_api",
            "abort": "test_assign_start_abort_execute_on_public_api",
            "archive": "test_archive_extend_metadata_cr_header_admin_negatives_and_stale",
            "extend_validity": "test_archive_extend_metadata_cr_header_admin_negatives_and_stale",
            "new_version": "test_new_version_after_archive_requires_qmb_on_public_api",
            "update_metadata": "test_metadata_and_change_request_consume_etag_on_public_api",
            "update_header": "test_header_and_comment_status_token_families",
            "comments": "test_comments_allowed_during_preparation_on_public_api",
            "change_requests": "test_metadata_and_change_request_consume_etag_on_public_api",
        }
        self.assertEqual(set(coverage), set(ACTION_IDS))
        for action_id, method_name in coverage.items():
            with self.subTest(action_id=action_id):
                self.assertTrue(callable(getattr(self, method_name)))

    def test_comments_allowed_during_preparation_on_public_api(self) -> None:
        from modules.documents.api import DocumentsCommentsApi, DocumentsWorkflowApi
        from modules.documents.contracts import WorkflowCommentContext

        service, api, in_review = self._to_in_review("DOC-CMT-API")
        comments_api = DocumentsCommentsApi(service)
        created = comments_api.create_pdf_workflow_comment_if_current(
            in_review,
            expected_last_event_id=in_review.last_event_id,
            context=WorkflowCommentContext.PDF_REVIEW,
            actor_user_id="reviewer-1",
            actor_role=SystemRole.USER,
            page_number=1,
            comment_text="note",
        )
        self.assertEqual(created.document_id, in_review.document_id)


if __name__ == "__main__":
    unittest.main()
