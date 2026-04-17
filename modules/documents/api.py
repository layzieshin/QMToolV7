from __future__ import annotations

from pathlib import Path

from .contracts import (
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentReadReceipt,
    DocumentReadSession,
    DocumentTaskItem,
    RecentDocumentItem,
    ReleasedDocumentItem,
    ReviewActionItem,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
    RejectionReason,
    SystemRole,
    ValidityExtensionOutcome,
    WorkflowCommentContext,
    WorkflowCommentDetail,
    WorkflowCommentListItem,
    WorkflowCommentRecord,
    WorkflowCommentStatus,
    PdfReadProgress,
    TrackedPdfReadSession,
    WorkflowProfile,
)
from .errors import DocumentWorkflowError
from .service import DocumentsService

__all__ = [
    "DocumentsApi",
    "DocumentWorkflowError",
    "ControlClass", "DocumentArtifact", "DocumentHeader", "DocumentTaskItem",
    "RecentDocumentItem", "ReleasedDocumentItem", "ReviewActionItem",
    "DocumentStatus", "DocumentType", "DocumentVersionState",
    "RejectionReason", "SystemRole", "ValidityExtensionOutcome", "WorkflowProfile",
]


class DocumentsPoolApi:
    def __init__(self, service: DocumentsService) -> None:
        self._service = service

    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        return self._service.list_by_status(status)

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        return self._service.list_artifacts(document_id, version)

    def get_header(self, document_id: str) -> DocumentHeader | None:
        return self._service.get_document_header(document_id)

    def list_tasks_for_user(self, user_id: str, role: str, scope: str | None = None) -> list[DocumentTaskItem]:
        return self._service.list_tasks_for_user(user_id, role, scope=scope)

    def list_review_actions_for_user(self, user_id: str, role: str) -> list[ReviewActionItem]:
        return self._service.list_review_actions_for_user(user_id, role)

    def list_recent_documents_for_user(self, user_id: str, role: str) -> list[RecentDocumentItem]:
        return self._service.list_recent_documents_for_user(user_id, role)

    def list_current_released_documents(self) -> list[ReleasedDocumentItem]:
        return self._service.list_current_released_documents()


class DocumentsWorkflowApi:
    def __init__(self, service: DocumentsService) -> None:
        self._service = service

    def create_document_version(
        self,
        document_id: str,
        version: int,
        *,
        owner_user_id: str | None = None,
        title: str = "",
        description: str | None = None,
        doc_type: DocumentType = DocumentType.OTHER,
        control_class: ControlClass | None = None,
        workflow_profile_id: str = "long_release",
        custom_fields: dict[str, object] | None = None,
    ) -> DocumentVersionState:
        return self._service.create_document_version(
            document_id,
            version,
            owner_user_id=owner_user_id,
            title=title,
            description=description,
            doc_type=doc_type,
            control_class=control_class,
            workflow_profile_id=workflow_profile_id,
            custom_fields=custom_fields,
        )

    def import_existing_pdf(
        self,
        document_id: str,
        version: int,
        source_path: Path,
        *,
        actor_user_id: str,
        actor_role: SystemRole,
    ) -> DocumentVersionState:
        return self._service.import_existing_pdf(
            document_id,
            version,
            source_path,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def import_existing_docx(
        self,
        document_id: str,
        version: int,
        source_path: Path,
        *,
        actor_user_id: str,
        actor_role: SystemRole,
    ) -> DocumentVersionState:
        return self._service.import_existing_docx(
            document_id,
            version,
            source_path,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def create_from_template(
        self,
        document_id: str,
        version: int,
        template_path: Path,
        *,
        actor_user_id: str,
        actor_role: SystemRole,
    ) -> DocumentVersionState:
        return self._service.create_from_template(
            document_id,
            version,
            template_path,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def assign_workflow_roles(
        self,
        state: DocumentVersionState,
        *,
        editors: set[str],
        reviewers: set[str],
        approvers: set[str],
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.assign_workflow_roles(
            state,
            editors=editors,
            reviewers=reviewers,
            approvers=approvers,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def start_workflow(
        self,
        state: DocumentVersionState,
        profile: WorkflowProfile,
        *,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.start_workflow(state, profile, actor_user_id=actor_user_id, actor_role=actor_role)

    def complete_editing(
        self,
        state: DocumentVersionState,
        *,
        sign_request: object | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.complete_editing(
            state,
            sign_request=sign_request,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def ensure_source_pdf_for_signing(
        self,
        state: DocumentVersionState,
        *,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> Path | None:
        return self._service.ensure_source_pdf_for_signing(
            state,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def accept_review(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        *,
        sign_request: object | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.accept_review(
            state,
            actor_user_id,
            sign_request=sign_request,
            actor_role=actor_role,
        )

    def reject_review(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        reason: RejectionReason,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.reject_review(state, actor_user_id, reason, actor_role=actor_role)

    def accept_approval(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        *,
        sign_request: object | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.accept_approval(
            state,
            actor_user_id,
            sign_request=sign_request,
            actor_role=actor_role,
        )

    def reject_approval(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        reason: RejectionReason,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.reject_approval(state, actor_user_id, reason, actor_role=actor_role)

    def abort_workflow(
        self,
        state: DocumentVersionState,
        *,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.abort_workflow(state, actor_user_id=actor_user_id, actor_role=actor_role)

    def archive_approved(
        self,
        state: DocumentVersionState,
        actor_role: SystemRole,
        actor_user_id: str | None = None,
    ) -> DocumentVersionState:
        return self._service.archive_approved(state, actor_role, actor_user_id=actor_user_id)

    def extend_annual_validity(
        self,
        state: DocumentVersionState,
        *,
        actor_user_id: str,
        signature_present: bool,
        duration_days: int,
        reason: str,
        review_outcome: ValidityExtensionOutcome,
    ) -> tuple[DocumentVersionState, bool]:
        return self._service.extend_annual_validity(
            state,
            actor_user_id=actor_user_id,
            signature_present=signature_present,
            duration_days=duration_days,
            reason=reason,
            review_outcome=review_outcome,
        )

    def create_new_version_after_archive(self, state: DocumentVersionState, next_version: int) -> DocumentVersionState:
        return self._service.create_new_version_after_archive(state, next_version)

    def update_version_metadata(
        self,
        state: DocumentVersionState,
        *,
        title: str | None = None,
        description: str | None = None,
        valid_until=None,
        next_review_at=None,
        custom_fields: dict[str, object] | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.update_version_metadata(
            state,
            title=title,
            description=description,
            valid_until=valid_until,
            next_review_at=next_review_at,
            custom_fields=custom_fields,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def add_change_request(
        self,
        state: DocumentVersionState,
        *,
        change_id: str,
        reason: str,
        impact_refs: list[str] | tuple[str, ...],
        actor_user_id: str,
        actor_role: SystemRole,
    ) -> DocumentVersionState:
        return self._service.add_change_request(
            state,
            change_id=change_id,
            reason=reason,
            impact_refs=impact_refs,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def list_change_requests(self, state: DocumentVersionState) -> list[dict[str, object]]:
        return self._service.list_change_requests(state)

    def update_document_header(
        self,
        document_id: str,
        *,
        doc_type: DocumentType | None = None,
        control_class: ControlClass | None = None,
        workflow_profile_id: str | None = None,
        department: str | None = None,
        site: str | None = None,
        regulatory_scope: str | None = None,
        distribution_roles: list[str] | None = None,
        distribution_sites: list[str] | None = None,
        distribution_departments: list[str] | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentHeader:
        return self._service.update_document_header(
            document_id,
            doc_type=doc_type,
            control_class=control_class,
            workflow_profile_id=workflow_profile_id,
            department=department,
            site=site,
            regulatory_scope=regulatory_scope,
            distribution_roles=distribution_roles,
            distribution_sites=distribution_sites,
            distribution_departments=distribution_departments,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )


class DocumentsReadApi:
    """Read-Confirmation API for training integration (§6.1)."""

    def __init__(self, service: DocumentsService) -> None:
        self._service = service

    def open_released_document_for_training(
        self, user_id: str, document_id: str, version: int
    ) -> DocumentReadSession:
        return self._service.open_released_document_for_training(user_id, document_id, version)

    def confirm_released_document_read(
        self, user_id: str, document_id: str, version: int, *, source: str
    ) -> DocumentReadReceipt:
        return self._service.confirm_released_document_read(user_id, document_id, version, source=source)

    def get_read_receipt(
        self, user_id: str, document_id: str, version: int
    ) -> DocumentReadReceipt | None:
        return self._service.get_read_receipt(user_id, document_id, version)

    def start_tracked_pdf_read(
        self,
        user_id: str,
        document_id: str,
        version: int,
        *,
        artifact_id: str | None,
        total_pages: int,
        source: str,
        min_seconds_per_page: int = 10,
    ) -> TrackedPdfReadSession:
        return self._service.start_tracked_pdf_read(
            user_id,
            document_id,
            version,
            artifact_id=artifact_id,
            total_pages=total_pages,
            source=source,
            min_seconds_per_page=min_seconds_per_page,
        )

    def record_page_dwell(self, session_id: str, *, page_number: int, dwell_seconds: int) -> PdfReadProgress:
        return self._service.record_page_dwell(session_id, page_number=page_number, dwell_seconds=dwell_seconds)

    def get_pdf_read_progress(self, session_id: str) -> PdfReadProgress:
        return self._service.get_pdf_read_progress(session_id)

    def finalize_tracked_pdf_read(self, session_id: str, *, source: str) -> DocumentReadReceipt | None:
        return self._service.finalize_tracked_pdf_read(session_id, source=source)


class DocumentsCommentsApi:
    def __init__(self, service: DocumentsService) -> None:
        self._service = service

    def list_workflow_comments(
        self,
        state: DocumentVersionState,
        *,
        context: WorkflowCommentContext,
        actor_user_id: str,
        actor_role: SystemRole,
    ) -> list[WorkflowCommentListItem]:
        return self._service.list_workflow_comments(
            state, context=context, actor_user_id=actor_user_id, actor_role=actor_role
        )

    def get_workflow_comment_detail(
        self, comment_id: str, *, actor_user_id: str, actor_role: SystemRole
    ) -> WorkflowCommentDetail:
        return self._service.get_workflow_comment_detail(
            comment_id, actor_user_id=actor_user_id, actor_role=actor_role
        )

    def sync_docx_comments(
        self, state: DocumentVersionState, *, actor_user_id: str, actor_role: SystemRole
    ) -> list[WorkflowCommentListItem]:
        return self._service.sync_docx_comments(state, actor_user_id=actor_user_id, actor_role=actor_role)

    def create_pdf_workflow_comment(
        self,
        state: DocumentVersionState,
        *,
        context: WorkflowCommentContext,
        actor_user_id: str,
        actor_role: SystemRole,
        page_number: int,
        comment_text: str,
        anchor_json: str | None = None,
    ) -> WorkflowCommentRecord:
        return self._service.create_pdf_workflow_comment(
            state,
            context=context,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            page_number=page_number,
            comment_text=comment_text,
            anchor_json=anchor_json,
        )

    def set_workflow_comment_status(
        self,
        comment_id: str,
        *,
        new_status: WorkflowCommentStatus,
        actor_user_id: str,
        actor_role: SystemRole,
        note: str | None = None,
    ) -> WorkflowCommentRecord:
        return self._service.set_workflow_comment_status(
            comment_id,
            new_status=new_status,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            note=note,
        )

