from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from modules.documents.api import (
    ACTION_IDS,
    action_descriptors_for_actor,
    available_actions_for_actor,
)
from modules.documents.contracts import DocumentStatus, SystemRole, WorkflowProfile
from modules.usermanagement.contracts import issue_user_context
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from tests.database_helpers import make_documents_service_with_profiles


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


def _actor(*, user_id: str, role: str, is_qmb: bool = False):
    return issue_user_context(
        user_id=user_id,
        session_id="sess-test",
        request_id="req-test",
        organization_id=INSTALLATION_ORGANIZATION_ID,
        username=user_id,
        global_roles=frozenset({role}),
        is_qmb=is_qmb,
        authenticated_at=datetime.now(timezone.utc),
    )


def _planned_state(*, document_id: str = "DOC-DESC"):
    service, _profiles = make_documents_service_with_profiles(
        Path(tempfile.mkdtemp(prefix="qmtool-docs-desc-")) / "documents.db"
    )
    state = service.create_document_version(document_id, 1, owner_user_id="owner-1")
    state = service.assign_workflow_roles(
        state,
        editors={"editor-1"},
        reviewers={"reviewer-1"},
        approvers={"approver-1"},
    )
    return state


def test_action_descriptors_cover_all_action_ids() -> None:
    state = _planned_state()
    actor = _actor(user_id="owner-1", role="User")
    descriptors = action_descriptors_for_actor(state, actor)
    expected_codes = set(ACTION_IDS) | {"preview", "download"}
    assert {descriptor.code for descriptor in descriptors} == expected_codes
    assert [descriptor.code for descriptor in descriptors] == sorted(expected_codes)


def test_enabled_codes_match_available_actions_for_actor() -> None:
    state = _planned_state(document_id="DOC-DESC-ENABLED")
    actor = _actor(user_id="owner-1", role="User")
    descriptors = action_descriptors_for_actor(state, actor)
    enabled_codes = sorted(descriptor.code for descriptor in descriptors if descriptor.enabled)
    assert enabled_codes == sorted(available_actions_for_actor(state, actor))


def test_disabled_descriptors_include_disabled_reason() -> None:
    state = _planned_state(document_id="DOC-DESC-DISABLED")
    actor = _actor(user_id="observer-1", role="User")
    descriptors = action_descriptors_for_actor(state, actor)
    disabled = [descriptor for descriptor in descriptors if not descriptor.enabled]
    assert disabled
    for descriptor in disabled:
        assert descriptor.disabled_reason
        assert isinstance(descriptor.disabled_reason, str)


def test_descriptor_metadata_for_reject_archive_and_abort() -> None:
    state = _planned_state(document_id="DOC-DESC-META")
    actor = _actor(user_id="owner-1", role="User")
    by_code = {descriptor.code: descriptor for descriptor in action_descriptors_for_actor(state, actor)}

    for code in ("review_reject", "approval_reject"):
        descriptor = by_code[code]
        assert descriptor.requires_reason is True
        assert descriptor.requires_confirmation is False
        assert descriptor.destructive is False
        assert descriptor.severity == "warning"
        assert descriptor.label_key == f"documents.action.{code}"

    for code in ("abort", "archive"):
        descriptor = by_code[code]
        assert descriptor.requires_reason is False
        assert descriptor.requires_confirmation is True
        assert descriptor.destructive is True
        assert descriptor.severity == "danger"

    change_requests = by_code["change_requests"]
    assert change_requests.requires_reason is True
    assert change_requests.requires_confirmation is False
    assert change_requests.destructive is False
    assert change_requests.severity == "warning"

    extend_validity = by_code["extend_validity"]
    assert extend_validity.requires_reason is True
    assert extend_validity.requires_confirmation is False
    assert extend_validity.destructive is False
    assert extend_validity.severity == "warning"

    start = by_code["start"]
    assert start.requires_reason is False
    assert start.requires_confirmation is False
    assert start.destructive is False
    assert start.severity == "info"


def _in_progress_state(
    *,
    document_id: str,
    profile: WorkflowProfile,
    editor_id: str = "editor-1",
) -> object:
    service, _profiles = make_documents_service_with_profiles(
        Path(tempfile.mkdtemp(prefix="qmtool-docs-desc-meta-")) / "documents.db"
    )
    state = service.create_document_version(document_id, 1, owner_user_id="owner-1")
    state = service.assign_workflow_roles(
        state,
        editors={editor_id},
        reviewers={"reviewer-1"},
        approvers={"approver-1"},
    )
    return service.start_workflow(
        state,
        profile,
        actor_user_id="owner-1",
        actor_role=SystemRole.USER,
    )


def test_workflow_action_metadata_from_server_decision() -> None:
    state = _in_progress_state(
        document_id="DOC-META-SIGNED",
        profile=WorkflowProfile.long_release_path(),
    )
    editor_actor = _actor(user_id="editor-1", role="User")
    observer_actor = _actor(user_id="observer-1", role="User")
    editor_by_code = {
        descriptor.code: descriptor
        for descriptor in action_descriptors_for_actor(state, editor_actor)
    }
    observer_by_code = {
        descriptor.code: descriptor
        for descriptor in action_descriptors_for_actor(state, observer_actor)
    }

    complete_editing = editor_by_code["complete_editing"]
    assert complete_editing.enabled is True
    assert complete_editing.signature_required is True
    assert complete_editing.assignment_kind == "editor"

    observer_complete = observer_by_code["complete_editing"]
    assert observer_complete.enabled is False
    assert observer_complete.disabled_reason
    assert observer_complete.signature_required is True
    assert observer_complete.assignment_kind == "editor"

    assign_roles = editor_by_code["assign_roles"]
    assert assign_roles.assignment_kind == "workflow_roles"
    assert assign_roles.signature_required is False

    for code in ("preview", "download"):
        artifact = editor_by_code[code]
        assert artifact.signature_required is False
        assert artifact.assignment_kind is None


def test_workflow_action_metadata_without_signature_requirement() -> None:
    state = _in_progress_state(
        document_id="DOC-META-NO-SIG",
        profile=WorkflowProfile.long_release_path(),
    )
    state = replace(
        state,
        workflow_profile=replace(
            WorkflowProfile.long_release_path(),
            signature_required_transitions=(),
        ),
    )
    editor_actor = _actor(user_id="editor-1", role="User")
    by_code = {
        descriptor.code: descriptor
        for descriptor in action_descriptors_for_actor(state, editor_actor)
    }
    complete_editing = by_code["complete_editing"]
    assert complete_editing.enabled is True
    assert complete_editing.signature_required is False
    assert complete_editing.assignment_kind == "editor"


def test_review_and_approval_action_metadata_follow_server_decision() -> None:
    service, _profiles = make_documents_service_with_profiles(
        Path(tempfile.mkdtemp(prefix="qmtool-docs-desc-review-")) / "documents.db",
        signature_api=_FakeSignatureApi(),
    )
    state = service.create_document_version("DOC-META-REVIEW", 1, owner_user_id="owner-1")
    state = service.assign_workflow_roles(
        state,
        editors={"editor-1"},
        reviewers={"reviewer-1"},
        approvers={"approver-1"},
    )
    profile = WorkflowProfile.long_release_path()
    state = service.start_workflow(
        state,
        profile,
        actor_user_id="owner-1",
        actor_role=SystemRole.USER,
    )
    state = service.complete_editing(
        state,
        sign_request={"step": "edit_complete"},
        actor_user_id="editor-1",
        actor_role=SystemRole.USER,
    )
    reviewer_actor = _actor(user_id="reviewer-1", role="User")
    review_by_code = {
        descriptor.code: descriptor
        for descriptor in action_descriptors_for_actor(state, reviewer_actor)
    }
    review_accept = review_by_code["review_accept"]
    assert review_accept.enabled is True
    assert review_accept.signature_required is True
    assert review_accept.assignment_kind == "reviewer"
    review_reject = review_by_code["review_reject"]
    assert review_reject.signature_required is False
    assert review_reject.assignment_kind == "reviewer"

    state = service.accept_review(
        state,
        "reviewer-1",
        sign_request={"step": "review_accept"},
    )
    approver_actor = _actor(user_id="approver-1", role="User")
    approval_by_code = {
        descriptor.code: descriptor
        for descriptor in action_descriptors_for_actor(state, approver_actor)
    }
    approval_accept = approval_by_code["approval_accept"]
    assert approval_accept.enabled is True
    assert approval_accept.signature_required is True
    assert approval_accept.assignment_kind == "approver"
    approval_reject = approval_by_code["approval_reject"]
    assert approval_reject.signature_required is False
    assert approval_reject.assignment_kind == "approver"


def test_active_workflow_owner_sees_abort_enabled_with_reason_on_observer() -> None:
    service, _profiles = make_documents_service_with_profiles(
        Path(tempfile.mkdtemp(prefix="qmtool-docs-desc-active-")) / "documents.db"
    )
    state = service.create_document_version("DOC-ACTIVE", 1, owner_user_id="owner-1")
    state = service.assign_workflow_roles(
        state,
        editors={"editor-1"},
        reviewers={"reviewer-1"},
        approvers={"approver-1"},
    )
    state = service.start_workflow(
        state,
        WorkflowProfile.long_release_path(),
        actor_user_id="owner-1",
        actor_role=SystemRole.USER,
    )
    assert state.status == DocumentStatus.IN_PROGRESS

    owner_actor = _actor(user_id="owner-1", role="User")
    observer_actor = _actor(user_id="observer-1", role="User")
    owner_abort = next(item for item in action_descriptors_for_actor(state, owner_actor) if item.code == "abort")
    observer_abort = next(item for item in action_descriptors_for_actor(state, observer_actor) if item.code == "abort")
    assert owner_abort.enabled is True
    assert owner_abort.disabled_reason is None
    assert observer_abort.enabled is False
    assert observer_abort.disabled_reason
