from __future__ import annotations

import unittest

from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType, RejectionReason, SystemRole, WorkflowProfile
from modules.documents.errors import PermissionDeniedError, ValidationError
from modules.documents.service import DocumentsService


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


class DocumentsVariantsMatrixTest(unittest.TestCase):
    def _state_for_profile(self, profile: WorkflowProfile, *, document_id: str):
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version(document_id, 1, owner_user_id="owner-1")
        state = service.assign_workflow_roles(
            state,
            editors={"editor-1"},
            reviewers={"reviewer-1"},
            approvers={"approver-1"},
        )
        state = service.start_workflow(state, profile, actor_user_id="owner-1", actor_role=SystemRole.USER)
        return service, state

    def test_abort_matrix_across_active_statuses(self) -> None:
        profile = WorkflowProfile.long_release_path()
        service, state = self._state_for_profile(profile, document_id="DOC-ABORT-MATRIX")

        states: list[tuple[str, object]] = [("IN_PROGRESS", state)]
        in_review = service.complete_editing(
            state,
            sign_request={"step": "edit_complete"},
            actor_user_id="owner-1",
            actor_role=SystemRole.USER,
        )
        states.append(("IN_REVIEW", in_review))
        in_approval = service.accept_review(in_review, "reviewer-1", sign_request={"step": "review_accept"})
        states.append(("IN_APPROVAL", in_approval))

        for label, candidate in states:
            with self.subTest(status=label):
                updated = service.abort_workflow(candidate, actor_user_id="owner-1", actor_role=SystemRole.USER)
                self.assertEqual(updated.status, DocumentStatus.PLANNED)

    def test_reject_paths_return_to_in_progress(self) -> None:
        profile = WorkflowProfile.long_release_path()
        service, state = self._state_for_profile(profile, document_id="DOC-REJECT-MATRIX")
        state = service.complete_editing(state, sign_request={"step": "edit_complete"})

        review_rejected = service.reject_review(
            state,
            "reviewer-1",
            RejectionReason(template_id="R1", template_text="Needs update", free_text="Fix chapter 4"),
        )
        self.assertEqual(review_rejected.status, DocumentStatus.IN_PROGRESS)

        state = service.complete_editing(review_rejected, sign_request={"step": "edit_complete"})
        state = service.accept_review(state, "reviewer-1", sign_request={"step": "review_accept"})
        approval_rejected = service.reject_approval(
            state,
            "approver-1",
            RejectionReason(template_id="A1", template_text="Not acceptable", free_text="Revise annex"),
        )
        self.assertEqual(approval_rejected.status, DocumentStatus.IN_PROGRESS)

    def test_annual_extension_limit_matrix(self) -> None:
        profile = WorkflowProfile.long_release_path()
        service, state = self._state_for_profile(profile, document_id="DOC-YEARLY-MATRIX")
        state = service.complete_editing(state, sign_request={"step": "edit_complete"})
        state = service.accept_review(state, "reviewer-1", sign_request={"step": "review_accept"})
        state = service.accept_approval(state, "approver-1", sign_request={"step": "approve"})

        for expected_count in (1, 2, 3):
            with self.subTest(extension_count=expected_count):
                state, recreate = service.extend_annual_validity(state, signature_present=True)
                self.assertFalse(recreate)
                self.assertEqual(state.extension_count, expected_count)

        same_state, recreate = service.extend_annual_validity(state, signature_present=True)
        self.assertTrue(recreate)
        self.assertEqual(same_state.extension_count, 3)

    def test_four_eyes_combination_matrix(self) -> None:
        four_eyes_profile = WorkflowProfile.long_release_path()
        no_four_eyes_profile = WorkflowProfile(
            profile_id="no_four_eyes",
            label="No Four Eyes",
            phases=(
                DocumentStatus.IN_PROGRESS,
                DocumentStatus.IN_REVIEW,
                DocumentStatus.IN_APPROVAL,
                DocumentStatus.APPROVED,
            ),
            four_eyes_required=False,
            signature_required_transitions=("IN_PROGRESS->IN_REVIEW", "IN_APPROVAL->APPROVED"),
        )
        cases = (
            (four_eyes_profile, True),
            (no_four_eyes_profile, False),
        )

        for profile, must_block in cases:
            with self.subTest(profile=profile.profile_id):
                service = DocumentsService(signature_api=_FakeSignatureApi())
                state = service.create_document_version(f"DOC-4E-{profile.profile_id}", 1, owner_user_id="owner-1")
                state = service.assign_workflow_roles(
                    state,
                    editors={"editor-1"},
                    reviewers={"alice"},
                    approvers={"alice"},
                )
                state = service.start_workflow(state, profile, actor_user_id="owner-1", actor_role=SystemRole.USER)
                state = service.complete_editing(state, sign_request={"step": "edit_complete"})
                # sign_request nur nötig wenn IN_REVIEW->IN_APPROVAL im Profil konfiguriert ist
                review_sign = {"step": "review_accept"} if "IN_REVIEW->IN_APPROVAL" in profile.signature_required_transitions else None
                state = service.accept_review(state, "alice", sign_request=review_sign)
                if must_block:
                    with self.assertRaises(PermissionDeniedError):
                        service.accept_approval(state, "alice", sign_request={"step": "approve"})
                else:
                    approved = service.accept_approval(state, "alice", sign_request={"step": "approve"})
                    self.assertEqual(approved.status, DocumentStatus.APPROVED)

    def test_invalid_control_class_profile_combination_is_blocked(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version(
            "DOC-COMB-1",
            1,
            owner_user_id="owner-1",
            doc_type=DocumentType.EXT,
            control_class=ControlClass.EXTERNAL,
            workflow_profile_id="external_control",
        )
        state = service.assign_workflow_roles(state, editors={"owner-1"}, reviewers={"rev-1"}, approvers={"app-1"})
        with self.assertRaises(ValidationError):
            service.start_workflow(
                state,
                WorkflowProfile.long_release_path(),
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            )

    def test_doc_type_control_class_profile_matrix(self) -> None:
        controlled_short = WorkflowProfile(
            profile_id="fast_path",
            label="Fast path",
            phases=(DocumentStatus.IN_PROGRESS, DocumentStatus.APPROVED),
            four_eyes_required=False,
            control_class=ControlClass.CONTROLLED_SHORT,
            signature_required_transitions=("IN_PROGRESS->IN_REVIEW",),
            requires_editors=True,
            requires_reviewers=False,
            requires_approvers=False,
        )
        external = WorkflowProfile(
            profile_id="external_control",
            label="External control",
            phases=(DocumentStatus.IN_PROGRESS, DocumentStatus.APPROVED),
            four_eyes_required=False,
            control_class=ControlClass.EXTERNAL,
            signature_required_transitions=(),
            requires_editors=False,
            requires_reviewers=False,
            requires_approvers=False,
        )
        record = WorkflowProfile(
            profile_id="record_light",
            label="Record light",
            phases=(DocumentStatus.IN_PROGRESS, DocumentStatus.APPROVED),
            four_eyes_required=False,
            control_class=ControlClass.RECORD,
            signature_required_transitions=(),
            requires_editors=False,
            requires_reviewers=False,
            requires_approvers=False,
        )
        valid_cases = [
            (DocumentType.VA, ControlClass.CONTROLLED, WorkflowProfile.long_release_path()),
            (DocumentType.AA, ControlClass.CONTROLLED_SHORT, controlled_short),
            (DocumentType.EXT, ControlClass.EXTERNAL, external),
            (DocumentType.OTHER, ControlClass.RECORD, record),
        ]
        invalid_cases = [
            (DocumentType.VA, ControlClass.CONTROLLED, external),
            (DocumentType.EXT, ControlClass.EXTERNAL, WorkflowProfile.long_release_path()),
            (DocumentType.AA, ControlClass.CONTROLLED_SHORT, record),
        ]

        for idx, (doc_type, control_class, profile) in enumerate(valid_cases, start=1):
            with self.subTest(case=f"valid-{idx}"):
                service = DocumentsService(signature_api=_FakeSignatureApi())
                state = service.create_document_version(
                    f"DOC-MATRIX-VALID-{idx}",
                    1,
                    owner_user_id="owner-1",
                    doc_type=doc_type,
                    control_class=control_class,
                    workflow_profile_id=profile.profile_id,
                )
                state = service.assign_workflow_roles(
                    state,
                    editors={"owner-1"} if control_class != ControlClass.EXTERNAL else set(),
                    reviewers={"reviewer-1"} if control_class != ControlClass.EXTERNAL else set(),
                    approvers={"approver-1"} if control_class != ControlClass.EXTERNAL else set(),
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )
                started = service.start_workflow(
                    state,
                    profile,
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )
                self.assertEqual(started.status, DocumentStatus.IN_PROGRESS)

        for idx, (doc_type, control_class, profile) in enumerate(invalid_cases, start=1):
            with self.subTest(case=f"invalid-{idx}"):
                service = DocumentsService(signature_api=_FakeSignatureApi())
                state = service.create_document_version(
                    f"DOC-MATRIX-INVALID-{idx}",
                    1,
                    owner_user_id="owner-1",
                    doc_type=doc_type,
                    control_class=control_class,
                    workflow_profile_id=profile.profile_id,
                )
                state = service.assign_workflow_roles(
                    state,
                    editors={"owner-1"} if control_class != ControlClass.EXTERNAL else set(),
                    reviewers={"reviewer-1"} if control_class != ControlClass.EXTERNAL else set(),
                    approvers={"approver-1"} if control_class != ControlClass.EXTERNAL else set(),
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )
                with self.assertRaises(ValidationError):
                    service.start_workflow(
                        state,
                        profile,
                        actor_user_id="owner-1",
                        actor_role=SystemRole.USER,
                    )

    def test_metadata_custom_field_prefix_is_blocked(self) -> None:
        service = DocumentsService(signature_api=_FakeSignatureApi())
        state = service.create_document_version("DOC-META-GUARD", 1, owner_user_id="owner-1")
        with self.assertRaises(ValidationError):
            service.update_version_metadata(
                state,
                custom_fields={"registry.active_version": 7},
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            )


if __name__ == "__main__":
    unittest.main()
