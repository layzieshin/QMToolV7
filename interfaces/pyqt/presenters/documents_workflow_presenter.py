from __future__ import annotations

from modules.documents.contracts import ArtifactType, DocumentStatus, SystemRole


class DocumentsWorkflowPresenter:
    @staticmethod
    def default_artifact_priority(status: DocumentStatus) -> list[ArtifactType]:
        if status in (DocumentStatus.PLANNED, DocumentStatus.IN_PROGRESS):
            return [ArtifactType.SOURCE_DOCX]
        if status in (DocumentStatus.IN_REVIEW, DocumentStatus.IN_APPROVAL):
            return [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF]
        if status in (DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
            return [ArtifactType.RELEASED_PDF]
        return []

    @staticmethod
    def visible_actions(status: DocumentStatus) -> set[str]:
        mapping = {
            DocumentStatus.PLANNED: {"start", "details"},
            DocumentStatus.IN_PROGRESS: {"edit", "complete", "abort", "details"},
            DocumentStatus.IN_REVIEW: {"edit", "review_accept", "review_reject", "abort", "details"},
            DocumentStatus.IN_APPROVAL: {"edit", "approval_accept", "approval_reject", "abort", "details"},
            DocumentStatus.APPROVED: {"archive", "details"},
            DocumentStatus.ARCHIVED: {"details"},
        }
        return mapping.get(status, {"details"})

    @staticmethod
    def _assigned_users_for_status(state: object) -> set[str]:
        assignments = getattr(state, "assignments", None)
        if assignments is None:
            return set()
        status = getattr(state, "status", None)
        if status == DocumentStatus.IN_PROGRESS:
            return set(getattr(assignments, "editors", set()))
        if status == DocumentStatus.IN_REVIEW:
            return set(getattr(assignments, "reviewers", set()))
        if status == DocumentStatus.IN_APPROVAL:
            return set(getattr(assignments, "approvers", set()))
        return (
            set(getattr(assignments, "editors", set()))
            | set(getattr(assignments, "reviewers", set()))
            | set(getattr(assignments, "approvers", set()))
        )

    @staticmethod
    def visible_actions_for_context(
        state: object | None,
        *,
        user_id: str | None,
        user_role: SystemRole | None,
        can_create_new_documents: bool = False,
    ) -> set[str]:
        visible: set[str] = set()
        if can_create_new_documents:
            visible.add("new")
        if state is None or not user_id:
            return visible

        owner_id = str(getattr(state, "owner_user_id", "") or "")
        is_owner = owner_id == user_id
        is_qmb = user_role == SystemRole.QMB
        is_admin = user_role == SystemRole.ADMIN
        status = getattr(state, "status", None)
        workflow_active = bool(getattr(state, "workflow_active", False))
        assignments = getattr(state, "assignments", None)
        status_actions = DocumentsWorkflowPresenter.visible_actions(status) if isinstance(status, DocumentStatus) else set()

        if "start" in status_actions and not workflow_active and is_owner:
            visible.add("start")
        if "abort" in status_actions and workflow_active and (is_qmb or is_owner):
            visible.add("abort")

        if "edit" in status_actions and user_id in DocumentsWorkflowPresenter._assigned_users_for_status(state):
            visible.add("edit")

        if "complete" in status_actions and assignments is not None and user_id in set(assignments.editors):
            visible.add("complete")
        if "review_accept" in status_actions and assignments is not None and user_id in set(assignments.reviewers):
            visible.update({"review_accept", "review_reject"})
        if "approval_accept" in status_actions and assignments is not None and user_id in set(assignments.approvers):
            visible.update({"approval_accept", "approval_reject"})
        if "archive" in status_actions and (is_qmb or is_admin):
            visible.add("archive")
        return visible

