from __future__ import annotations

from modules.documents.contracts import ArtifactType, DocumentStatus


class DocumentsWorkflowPresenter:
    @staticmethod
    def default_artifact_priority(status: DocumentStatus) -> list[ArtifactType]:
        if status in (DocumentStatus.PLANNED, DocumentStatus.IN_PROGRESS):
            return [ArtifactType.SOURCE_DOCX]
        if status in (DocumentStatus.IN_REVIEW, DocumentStatus.IN_APPROVAL):
            return [ArtifactType.SOURCE_PDF, ArtifactType.SIGNED_PDF]
        if status in (DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
            return [ArtifactType.RELEASED_PDF, ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF]
        return []

    @staticmethod
    def visible_actions(status: DocumentStatus) -> set[str]:
        mapping = {
            DocumentStatus.PLANNED: {"start", "details"},
            DocumentStatus.IN_PROGRESS: {"edit", "complete", "abort", "details"},
            DocumentStatus.IN_REVIEW: {"review_accept", "review_reject", "abort", "details"},
            DocumentStatus.IN_APPROVAL: {"approval_accept", "approval_reject", "abort", "details"},
            DocumentStatus.APPROVED: {"archive", "details"},
            DocumentStatus.ARCHIVED: {"details"},
        }
        return mapping.get(status, {"details"})
