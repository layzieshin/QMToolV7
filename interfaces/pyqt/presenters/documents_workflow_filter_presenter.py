from __future__ import annotations

from dataclasses import dataclass

from modules.documents.contracts import DocumentStatus


@dataclass(frozen=True)
class QuickFilterPreset:
    scope: str
    status_filter: str | DocumentStatus


class DocumentsWorkflowFilterPresenter:
    @staticmethod
    def preset(mode: str) -> QuickFilterPreset:
        if mode == "tasks":
            return QuickFilterPreset(scope="tasks", status_filter="ALL")
        if mode == "review":
            return QuickFilterPreset(scope="all", status_filter=DocumentStatus.IN_REVIEW)
        if mode == "approval":
            return QuickFilterPreset(scope="all", status_filter=DocumentStatus.IN_APPROVAL)
        return QuickFilterPreset(scope="all", status_filter="ALL")

    @staticmethod
    def filter_rows(
        rows: list[object],
        *,
        scope: str,
        user_id: str | None,
        owner_contains: str,
        title_contains: str,
        workflow_active: str,
        active_version: str,
    ) -> list[object]:
        filtered = list(rows)
        if user_id and scope != "all":
            if scope == "mine":
                filtered = [r for r in filtered if str(r.owner_user_id or "") == str(user_id)]
            elif scope == "tasks":
                filtered = [r for r in filtered if r.status in (DocumentStatus.IN_PROGRESS, DocumentStatus.IN_REVIEW, DocumentStatus.IN_APPROVAL)]
        if owner_contains:
            filtered = [r for r in filtered if owner_contains in str(r.owner_user_id or "").lower()]
        if title_contains:
            filtered = [r for r in filtered if title_contains in str(r.title or "").lower()]
        if workflow_active in ("true", "false"):
            want = workflow_active == "true"
            filtered = [r for r in filtered if bool(r.workflow_active) is want]
        if active_version in ("true", "false"):
            want = active_version == "true"
            filtered = [r for r in filtered if ((getattr(r, "active_version", None) is not None) is want)]
        filtered.sort(key=lambda r: (r.document_id, r.version), reverse=True)
        return filtered
