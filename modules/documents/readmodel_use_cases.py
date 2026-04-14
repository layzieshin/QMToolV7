from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from modules.documents.contracts import (
    DocumentStatus,
    DocumentTaskItem,
    RecentDocumentItem,
    ReleasedDocumentItem,
    ReviewActionItem,
)


class DocumentsReadmodelUseCases:
    """Read-focused use-cases extracted from DocumentsService."""

    def __init__(
        self,
        *,
        iter_states: Callable[[], Iterable[object]],
        matches_user_context: Callable[[object, str, str], bool],
    ) -> None:
        self._iter_states = iter_states
        self._matches_user_context = matches_user_context

    def list_tasks_for_user(self, user_id: str, role: str, scope: str | None = None) -> list[DocumentTaskItem]:
        _ = scope
        items: list[DocumentTaskItem] = []
        for state in self._iter_states():
            if not self._matches_user_context(state, user_id, role):
                continue
            if state.status in (DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
                continue
            items.append(
                DocumentTaskItem(
                    document_id=state.document_id,
                    version=state.version,
                    title=state.title,
                    status=state.status,
                    owner_user_id=state.owner_user_id,
                    workflow_active=state.workflow_active,
                    last_actor_user_id=state.last_actor_user_id,
                )
            )
        return sorted(items, key=lambda item: (item.document_id, item.version))

    def list_review_actions_for_user(self, user_id: str, role: str) -> list[ReviewActionItem]:
        role_upper = role.upper()
        items: list[ReviewActionItem] = []
        for state in self._iter_states():
            if state.status == DocumentStatus.IN_REVIEW and (role_upper in ("ADMIN", "QMB") or user_id in state.assignments.reviewers):
                items.append(
                    ReviewActionItem(
                        document_id=state.document_id,
                        version=state.version,
                        title=state.title,
                        status=state.status,
                        action_required="review",
                        owner_user_id=state.owner_user_id,
                    )
                )
            if state.status == DocumentStatus.IN_APPROVAL and (
                role_upper in ("ADMIN", "QMB") or user_id in state.assignments.approvers
            ):
                items.append(
                    ReviewActionItem(
                        document_id=state.document_id,
                        version=state.version,
                        title=state.title,
                        status=state.status,
                        action_required="approval",
                        owner_user_id=state.owner_user_id,
                    )
                )
        return sorted(items, key=lambda item: (item.document_id, item.version))

    def list_recent_documents_for_user(self, user_id: str, role: str) -> list[RecentDocumentItem]:
        items: list[RecentDocumentItem] = []
        for state in self._iter_states():
            if not self._matches_user_context(state, user_id, role):
                continue
            items.append(
                RecentDocumentItem(
                    document_id=state.document_id,
                    version=state.version,
                    title=state.title,
                    status=state.status,
                    owner_user_id=state.owner_user_id,
                    last_event_at=state.last_event_at,
                )
            )
        return sorted(items, key=lambda item: item.last_event_at or datetime.min, reverse=True)

    def list_current_released_documents(self) -> list[ReleasedDocumentItem]:
        items: list[ReleasedDocumentItem] = []
        for state in self._iter_states():
            if state.status != DocumentStatus.APPROVED:
                continue
            if state.superseded_by_version is not None:
                continue
            items.append(
                ReleasedDocumentItem(
                    document_id=state.document_id,
                    version=state.version,
                    title=state.title,
                    valid_until=state.valid_until,
                    released_at=state.released_at,
                    owner_user_id=state.owner_user_id,
                )
            )
        return sorted(items, key=lambda item: (item.document_id, item.version))
