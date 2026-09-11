from __future__ import annotations

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
