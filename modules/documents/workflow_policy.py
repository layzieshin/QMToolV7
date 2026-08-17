"""Single J04-M0 workflow authorization policy.

The policy is deliberately limited to the relational/read-model workflow
already supported by M0. Unsupported assignment policies are rejected by the
profile store; this module does not invent M1 workflow state.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import DocumentStatus, DocumentVersionState, SystemRole


ACTION_IDS = frozenset(
    {
        "assign_roles",
        "start",
        "open_source",
        "complete_editing",
        "review_accept",
        "review_reject",
        "approval_accept",
        "approval_reject",
        "abort",
        "archive",
        "extend_validity",
        "new_version",
        "update_metadata",
        "update_header",
        "comments",
        "change_requests",
    }
)


@dataclass(frozen=True)
class WorkflowDecision:
    allowed: bool
    reason: str
    signature_required: bool = False
    assignment_kind: str | None = None


def _transition_signature_required(state: DocumentVersionState, transition: str) -> bool:
    profile = getattr(state, "workflow_profile", None)
    return bool(profile and transition in set(profile.signature_required_transitions))


def evaluate_workflow_action(
    state: DocumentVersionState,
    *,
    user_id: str,
    role: SystemRole,
    action: str,
) -> WorkflowDecision:
    user_id = str(user_id).strip()
    if not user_id:
        return WorkflowDecision(False, "user_id is required")
    is_qmb = role == SystemRole.QMB
    is_owner = state.owner_user_id == user_id

    if action == "assign_roles":
        allowed = is_qmb or (is_owner and not bool(getattr(state, "edit_signature_done", False)))
        return WorkflowDecision(allowed, "owner or QMB required", assignment_kind="workflow_roles")
    if action == "start":
        allowed = state.status == DocumentStatus.PLANNED and not state.workflow_active and (is_owner or is_qmb)
        return WorkflowDecision(allowed, "owner or QMB may start a planned workflow")
    if action == "open_source":
        assignment = {
            DocumentStatus.IN_PROGRESS: (state.assignments.editors, "editor"),
            DocumentStatus.IN_REVIEW: (state.assignments.reviewers, "reviewer"),
            DocumentStatus.IN_APPROVAL: (state.assignments.approvers, "approver"),
        }.get(state.status, (frozenset(), None))
        allowed = is_qmb or user_id in assignment[0]
        return WorkflowDecision(allowed, "assignment required", assignment_kind=assignment[1])
    if action == "complete_editing":
        allowed = state.status == DocumentStatus.IN_PROGRESS and (is_qmb or is_owner or user_id in state.assignments.editors)
        return WorkflowDecision(
            allowed,
            "assigned editor, owner, or QMB required",
            signature_required=_transition_signature_required(state, "IN_PROGRESS->IN_REVIEW"),
            assignment_kind="editor",
        )
    if action in {"review_accept", "review_reject"}:
        allowed = state.status == DocumentStatus.IN_REVIEW and user_id in state.assignments.reviewers
        return WorkflowDecision(
            allowed,
            "assigned reviewer required",
            signature_required=(
                action == "review_accept"
                and _transition_signature_required(state, "IN_REVIEW->IN_APPROVAL")
            ),
            assignment_kind="reviewer",
        )
    if action in {"approval_accept", "approval_reject"}:
        four_eyes_block = (
            action == "approval_accept"
            and bool(
                getattr(state, "workflow_profile", None)
                and state.workflow_profile.four_eyes_required
            )
            and user_id in getattr(state, "reviewed_by", frozenset())
        )
        allowed = state.status == DocumentStatus.IN_APPROVAL and user_id in state.assignments.approvers and not four_eyes_block
        return WorkflowDecision(
            allowed,
            "assigned approver required and four-eyes rule must hold",
            signature_required=(
                action == "approval_accept"
                and _transition_signature_required(state, "IN_APPROVAL->APPROVED")
            ),
            assignment_kind="approver",
        )
    if action == "abort":
        allowed = state.workflow_active and state.status in {
            DocumentStatus.IN_PROGRESS,
            DocumentStatus.IN_REVIEW,
            DocumentStatus.IN_APPROVAL,
        } and (is_owner or is_qmb)
        return WorkflowDecision(allowed, "owner or QMB may abort an active workflow")
    if action in {"archive", "extend_validity"}:
        allowed = state.status == DocumentStatus.APPROVED and is_qmb
        return WorkflowDecision(allowed, "effective QMB required")
    if action == "new_version":
        return WorkflowDecision(state.status == DocumentStatus.ARCHIVED and is_qmb, "effective QMB required")
    if action in {"update_metadata", "change_requests"}:
        return WorkflowDecision(is_owner or is_qmb, "owner or QMB required")
    if action == "update_header":
        return WorkflowDecision(is_qmb, "effective QMB required")
    if action == "comments":
        return WorkflowDecision(
            state.status in {
                DocumentStatus.PLANNED,
                DocumentStatus.IN_PROGRESS,
                DocumentStatus.IN_REVIEW,
                DocumentStatus.IN_APPROVAL,
            },
            "comments are available only during active document preparation",
        )
    return WorkflowDecision(False, "unsupported workflow action")


def available_workflow_actions(
    state: DocumentVersionState,
    *,
    user_id: str,
    role: SystemRole,
) -> frozenset[str]:
    return frozenset(
        action
        for action in ACTION_IDS
        if evaluate_workflow_action(state, user_id=user_id, role=role, action=action).allowed
    )
