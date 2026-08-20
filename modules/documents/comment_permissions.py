from __future__ import annotations

from .contracts import DocumentVersionState, DocumentStatus, SystemRole, WorkflowCommentContext
from .errors import PermissionDeniedError, ValidationError


def ensure_workflow_comment_access(
    state: DocumentVersionState,
    *,
    context: WorkflowCommentContext,
    actor_user_id: str,
    actor_role: SystemRole,
) -> None:
    if actor_role == SystemRole.QMB:
        return
    if context == WorkflowCommentContext.DOCX_EDIT:
        allowed = set(state.assignments.editors)
        if state.owner_user_id:
            allowed.add(state.owner_user_id)
    elif context == WorkflowCommentContext.PDF_REVIEW:
        if state.status != DocumentStatus.IN_REVIEW:
            raise ValidationError("PDF_REVIEW comments are only allowed in IN_REVIEW")
        allowed = set(state.assignments.reviewers)
    else:
        if state.status != DocumentStatus.IN_APPROVAL:
            raise ValidationError("PDF_APPROVAL comments are only allowed in IN_APPROVAL")
        allowed = set(state.assignments.approvers)
    if actor_user_id not in allowed:
        raise PermissionDeniedError("actor is not allowed to access comments in this context")


def ensure_workflow_comment_read_access(
    state: DocumentVersionState,
    *,
    context: WorkflowCommentContext,
    actor_user_id: str,
    actor_role: SystemRole,
) -> None:
    """Authorize reading an existing comment without requiring its phase to be active."""
    if actor_role == SystemRole.QMB:
        return
    if context == WorkflowCommentContext.DOCX_EDIT:
        allowed = set(state.assignments.editors)
        if state.owner_user_id:
            allowed.add(state.owner_user_id)
    elif context == WorkflowCommentContext.PDF_REVIEW:
        allowed = set(state.assignments.reviewers)
    else:
        allowed = set(state.assignments.approvers)
    if actor_user_id not in allowed:
        raise PermissionDeniedError("actor is not allowed to access comments in this context")
