from __future__ import annotations

from modules.documents.api import ArtifactType, DocumentStatus


class DocumentsWorkflowPresenter:
    """Maps backend ``available_actions`` names to PyQt UI keys. Fail-closed."""

    _ADAPTER_KEYS = {
        "assign_roles": "assign_roles",
        "start": "start",
        "open_source": "edit",
        "complete_editing": "complete",
        "review_accept": "review_accept",
        "review_reject": "review_reject",
        "approval_accept": "approval_accept",
        "approval_reject": "approval_reject",
        "abort": "abort",
        "archive": "archive",
        "extend_validity": "extend_validity",
        "new_version": "new_version",
        "update_metadata": "update_metadata",
        "update_header": "update_header",
        "comments": "comments",
        "change_requests": "change_requests",
    }

    @staticmethod
    def default_artifact_priority(status: DocumentStatus) -> list[ArtifactType]:
        if status in (DocumentStatus.PLANNED, DocumentStatus.IN_PROGRESS):
            return [ArtifactType.SOURCE_DOCX]
        if status in (DocumentStatus.IN_REVIEW, DocumentStatus.IN_APPROVAL):
            return [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF]
        if status in (DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
            return [ArtifactType.RELEASED_PDF]
        return []

    @classmethod
    def visible_actions_for_context(
        cls,
        state: object | None,
        *,
        user_id: str | None,
        can_create_new_documents: bool = False,
        **_ignored: object,
    ) -> set[str]:
        """Return UI keys from backend actions only.

        Missing/invalid ``available_actions`` yield no mutation keys.
        ``can_create_new_documents`` must come from the backend capability.
        Extra kwargs (legacy ``user_role``) are ignored and never used for policy.
        """
        visible: set[str] = set()
        if can_create_new_documents:
            visible.add("new")
        if state is None or not user_id:
            return visible

        supplied = getattr(state, "available_actions", None)
        if not isinstance(supplied, (list, tuple, set, frozenset)):
            return visible
        for action in supplied:
            if not isinstance(action, str):
                continue
            ui_key = cls._ADAPTER_KEYS.get(action)
            if ui_key is not None:
                visible.add(ui_key)
        return visible
