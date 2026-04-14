from __future__ import annotations

from pathlib import Path

from .contracts import (
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentTaskItem,
    RecentDocumentItem,
    ReleasedDocumentItem,
    ReviewActionItem,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
    RejectionReason,
    SystemRole,
    WorkflowProfile,
)
from .service import DocumentsService


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

    def accept_review(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._service.accept_review(state, actor_user_id, actor_role=actor_role)

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
        signature_present: bool,
    ) -> tuple[DocumentVersionState, bool]:
        return self._service.extend_annual_validity(state, signature_present=signature_present)

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
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

