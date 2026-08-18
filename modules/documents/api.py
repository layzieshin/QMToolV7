from __future__ import annotations

from pathlib import Path

from .artifact_query_ops import preferred_pdf_artifact_types, resolve_openable_artifact_refs, sort_artifacts_current_first
from .contracts import (
    ArtifactSourceType,
    ArtifactType,
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
    OpenableArtifactRef,
    RejectionReason,
    SystemRole,
    ValidityExtensionOutcome,
    WorkflowCommentContext,
    WorkflowCommentDetail,
    WorkflowCommentListItem,
    WorkflowCommentRecord,
    WorkflowCommentSourceKind,
    WorkflowCommentStatus,
    PdfReadProgress,
    TrackedPdfReadSession,
    WorkflowProfile,
    control_class_for,
)
from .docx_to_pdf import convert_docx_to_pdf as _convert_docx_to_pdf
from .docx_to_pdf import docx_conversion_available as _docx_conversion_available
from .docx_to_pdf import prepare_frozen_stdio as _prepare_frozen_stdio
from .errors import (
    DocumentConflictError,
    HeaderConflictError,
    CommentConflictError,
    DocumentWorkflowError,
    DocumentsFeatureUnavailableError,
    PermissionDeniedError,
    ValidationError,
)
from modules.usermanagement.api import UserContext

from .actor_context import actor_user_and_role
from .capabilities import (
    ACTION_IDS,
    available_actions_for_actor,
    compute_available_actions,
    compute_global_capabilities,
)
from .service import DocumentsService
from .state_transport import (
    document_version_state_from_json,
    document_version_state_from_payload,
    document_version_state_to_json,
    document_version_state_to_payload,
)

__all__ = [
    "DocumentsApi",
    "DocumentConflictError",
    "HeaderConflictError",
    "CommentConflictError",
    "DocumentWorkflowError",
    "DocumentsFeatureUnavailableError",
    "PermissionDeniedError",
    "ValidationError",
    "convert_docx_to_pdf",
    "docx_conversion_available",
    "prepare_docx_conversion_runtime",
    "build_workflow_sign_request_from_intent",
    "DocumentsArtifactsApi",
    "DocumentsCommentsApi",
    "DocumentsPoolApi",
    "DocumentsReadApi",
    "DocumentsWorkflowApi",
    "ArtifactSourceType",
    "ArtifactType",
    "ControlClass",
    "DocumentArtifact",
    "DocumentHeader",
    "DocumentTaskItem",
    "OpenableArtifactRef",
    "RecentDocumentItem",
    "ReleasedDocumentItem",
    "ReviewActionItem",
    "DocumentStatus",
    "DocumentType",
    "DocumentVersionState",
    "RejectionReason",
    "SystemRole",
    "ValidityExtensionOutcome",
    "WorkflowProfile",
    "WorkflowCommentStatus",
    "WorkflowCommentSourceKind",
    "control_class_for",
    "document_version_state_from_json",
    "document_version_state_from_payload",
    "document_version_state_to_json",
    "document_version_state_to_payload",
    "ACTION_IDS",
    "available_actions_for_actor",
    "compute_available_actions",
    "compute_global_capabilities",
    "artifact_to_public_payload",
]


_NO_PRECONDITION = object()


def prepare_docx_conversion_runtime() -> None:
    """Prepare runtime stdio for DOCX conversion in frozen/windowed environments."""
    _prepare_frozen_stdio()


def convert_docx_to_pdf(source: Path, target: Path) -> None:
    """Convert DOCX to PDF through the public documents API surface."""
    _convert_docx_to_pdf(source, target)


def docx_conversion_available() -> bool:
    """Return whether the backend DOCX conversion dependency is available."""
    return _docx_conversion_available()


def build_workflow_sign_request_from_intent(
    *,
    state: DocumentVersionState,
    transition: str,
    sign_intent: dict[str, object],
    actor: UserContext,
    signature_api: object,
    documents_service: DocumentsService,
    scratch_root: Path,
) -> object:
    """Build a module SignRequest for a signed workflow transition on the backend host."""
    from .sign_intent_builder import build_workflow_sign_request_from_intent as _build

    return _build(
        state=state,
        transition=transition,
        sign_intent=sign_intent,
        actor=actor,
        signature_api=signature_api,
        documents_service=documents_service,
        scratch_root=scratch_root,
    )


def artifact_to_public_payload(artifact: DocumentArtifact) -> dict[str, object]:
    """Serialize artifact metadata without leaking server storage locations."""
    private_metadata_keys = {"absolute_path", "file_path", "path", "source", "generated_from", "storage_key"}
    return {
        "artifact_id": artifact.artifact_id,
        "document_id": artifact.document_id,
        "version": artifact.version,
        "artifact_type": artifact.artifact_type.value,
        "source_type": artifact.source_type.value,
        "original_filename": artifact.original_filename,
        "mime_type": artifact.mime_type,
        "sha256": artifact.sha256,
        "size_bytes": artifact.size_bytes,
        "is_current": artifact.is_current,
        "metadata": {
            key: value
            for key, value in artifact.metadata.items()
            if key.lower() not in private_metadata_keys and not key.lower().endswith("_path")
        },
        "created_at": artifact.created_at.isoformat(),
    }


class DocumentsPoolApi:
    def __init__(self, service: DocumentsService) -> None:
        self._service = service

    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        return self._service.list_by_status(status)

    def list_by_status_for_actor(self, status: DocumentStatus, actor: UserContext) -> list[DocumentVersionState]:
        user_id, role = actor_user_and_role(actor)
        return self._service.list_by_status_for_actor(status, actor_user_id=user_id, actor_role=role)

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        return self._service.list_artifacts(document_id, version)

    def get_document_version(self, document_id: str, version: int) -> DocumentVersionState | None:
        return self._service.get_document_version(document_id, version)

    def get_document_version_for_actor(
        self, document_id: str, version: int, actor: UserContext
    ) -> DocumentVersionState | None:
        user_id, role = actor_user_and_role(actor)
        return self._service.get_document_version_for_actor(
            document_id, version, actor_user_id=user_id, actor_role=role
        )

    def get_header(self, document_id: str) -> DocumentHeader | None:
        return self._service.get_document_header(document_id)

    def get_header_for_actor(self, document_id: str, actor: UserContext) -> DocumentHeader | None:
        user_id, role = actor_user_and_role(actor)
        return self._service.get_document_header_for_actor(
            document_id,
            actor_user_id=user_id,
            actor_role=role,
        )

    def list_tasks_for_user(self, user_id: str, role: str, scope: str | None = None) -> list[DocumentTaskItem]:
        return self._service.list_tasks_for_user(user_id, role, scope=scope)

    def list_tasks_for_actor(self, actor: UserContext, scope: str | None = None) -> list[DocumentTaskItem]:
        user_id, role = actor_user_and_role(actor)
        return self._service.list_tasks_for_user(user_id, role.value, scope=scope)

    def list_review_actions_for_user(self, user_id: str, role: str) -> list[ReviewActionItem]:
        return self._service.list_review_actions_for_user(user_id, role)

    def list_review_actions_for_actor(self, actor: UserContext) -> list[ReviewActionItem]:
        user_id, role = actor_user_and_role(actor)
        return self._service.list_review_actions_for_user(user_id, role.value)

    def list_recent_documents_for_user(self, user_id: str, role: str) -> list[RecentDocumentItem]:
        return self._service.list_recent_documents_for_user(user_id, role)

    def list_recent_documents_for_actor(self, actor: UserContext) -> list[RecentDocumentItem]:
        user_id, role = actor_user_and_role(actor)
        return self._service.list_recent_documents_for_user(user_id, role.value)

    def list_current_released_documents(self) -> list[ReleasedDocumentItem]:
        return self._service.list_current_released_documents()


class DocumentsArtifactsApi:
    def __init__(self, service: DocumentsService, *, app_home: Path, artifacts_root: Path) -> None:
        self._service = service
        self._app_home = app_home
        self._artifacts_root = artifacts_root

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        return self._service.list_artifacts(document_id, version)

    def list_artifacts_for_actor(
        self, document_id: str, version: int, actor: UserContext
    ) -> list[DocumentArtifact]:
        user_id, role = actor_user_and_role(actor)
        state = self._service.get_document_version_for_actor(
            document_id,
            version,
            actor_user_id=user_id,
            actor_role=role,
        )
        if state is None:
            return []
        return self._service.list_artifacts(state.document_id, state.version)

    def get_artifact_by_id(self, artifact_id: str) -> DocumentArtifact | None:
        return self._service.get_artifact_by_id(artifact_id)

    def get_artifact_by_id_for_actor(self, artifact_id: str, actor: UserContext) -> DocumentArtifact | None:
        user_id, role = actor_user_and_role(actor)
        return self._service.get_artifact_by_id_for_actor(
            artifact_id, actor_user_id=user_id, actor_role=role
        )

    def read_artifact_bytes(self, artifact_id: str) -> bytes:
        return self._service.read_artifact_bytes(artifact_id)

    def read_artifact_bytes_for_actor(self, artifact_id: str, actor: UserContext) -> bytes:
        user_id, role = actor_user_and_role(actor)
        return self._service.read_artifact_bytes_for_actor(
            artifact_id, actor_user_id=user_id, actor_role=role
        )

    def resolve_artifact_paths(
        self,
        artifact: DocumentArtifact,
        *,
        suffixes: tuple[str, ...] = (),
        existing_only: bool = True,
    ) -> list[OpenableArtifactRef]:
        return resolve_openable_artifact_refs(
            artifact=artifact,
            app_home=self._app_home,
            artifacts_root=self._artifacts_root,
            suffixes=suffixes,
            existing_only=existing_only,
        )

    def get_openable_artifact_refs(
        self,
        document_id: str,
        version: int,
        *,
        artifact_types: tuple[ArtifactType, ...],
        suffixes: tuple[str, ...] = (),
        current_first: bool = True,
        existing_only: bool = True,
    ) -> list[OpenableArtifactRef]:
        artifacts = self._service.list_artifacts(document_id, version)
        ordered = sort_artifacts_current_first(artifacts) if current_first else artifacts
        refs: list[OpenableArtifactRef] = []
        for artifact_type in artifact_types:
            for artifact in ordered:
                if artifact.artifact_type != artifact_type:
                    continue
                refs.extend(
                    self.resolve_artifact_paths(
                        artifact,
                        suffixes=suffixes,
                        existing_only=existing_only,
                    )
                )
        return refs

    def get_preferred_pdf_artifact(
        self,
        document_id: str,
        version: int,
        *,
        transition: str | None = None,
        purpose: str = "signature",
    ) -> OpenableArtifactRef | None:
        refs = self.get_openable_artifact_refs(
            document_id,
            version,
            artifact_types=preferred_pdf_artifact_types(transition, purpose=purpose),
            suffixes=(".pdf",),
            current_first=True,
            existing_only=True,
        )
        return refs[0] if refs else None

    def get_released_pdf_for_reading(self, document_id: str, version: int) -> OpenableArtifactRef | None:
        refs = self.get_openable_artifact_refs(
            document_id,
            version,
            artifact_types=(ArtifactType.RELEASED_PDF,),
            suffixes=(".pdf",),
            current_first=True,
            existing_only=True,
        )
        return refs[0] if refs else None

    def get_source_docx_for_conversion(self, document_id: str, version: int) -> OpenableArtifactRef | None:
        refs = self.get_openable_artifact_refs(
            document_id,
            version,
            artifact_types=(ArtifactType.SOURCE_DOCX,),
            suffixes=(".docx",),
            current_first=True,
            existing_only=True,
        )
        return refs[0] if refs else None


class DocumentsWorkflowApi:
    def __init__(self, service: DocumentsService) -> None:
        self._service = service

    def build_workflow_sign_request_from_intent(
        self,
        *,
        state: DocumentVersionState,
        transition: str,
        sign_intent: dict[str, object],
        actor: UserContext,
        signature_api: object,
        scratch_root: Path,
    ) -> object:
        """Build a server-owned signing request without exposing service internals."""
        return build_workflow_sign_request_from_intent(
            state=state,
            transition=transition,
            sign_intent=sign_intent,
            actor=actor,
            signature_api=signature_api,
            documents_service=self._service,
            scratch_root=scratch_root,
        )

    def mutate_version_if_current(
        self,
        state,
        expected_last_event_id,
        operation,
        *,
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        action: str | None = None,
        owner_or_privileged: bool = False,
    ):
        """Apply a public optimistic-lock boundary for a version mutation.

        Visibility and authorization run on the locked ``current`` state before
        the ETag compare. When ``action`` is set, workflow policy remains the
        fachliche owner. Import uses ``owner_or_privileged`` for the existing
        Owner/QMB rule.
        """
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if expected_last_event_id is _NO_PRECONDITION:
            expected_last_event_id = state.last_event_id
        return self._service.mutate_version_if_current(
            state.document_id,
            state.version,
            expected_last_event_id,
            operation,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action,
            owner_or_privileged=owner_or_privileged,
        )

    def _assert_workflow_policy(self, state, *, actor_user_id: str, actor_role: SystemRole, action: str) -> None:
        self._service.assert_workflow_action(
            state,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action,
        )

    # Compatibility alias for existing in-module callers. Backend transport
    # code must use the public method above.
    def _mutate_current(self, state, expected_last_event_id, operation, **kwargs):
        return self.mutate_version_if_current(state, expected_last_event_id, operation, **kwargs)

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
        workflow_profile_id: str | None = None,
        custom_fields: dict[str, object] | None = None,
        actor: UserContext | None = None,
        delegated_create_allowed: bool = False,
    ) -> DocumentVersionState:
        if actor is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        user_id, role = actor_user_and_role(actor)
        if role != SystemRole.QMB and not delegated_create_allowed:
            raise PermissionDeniedError("effective QMB or delegated create permission required")
        if owner_user_id is None:
            owner_user_id = user_id
        elif owner_user_id != user_id and role != SystemRole.QMB:
            raise PermissionDeniedError("only an effective QMB may assign a different owner")
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
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None or actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        operation = lambda _current: self._service.import_existing_pdf(
            document_id,
            version,
            source_path,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        if expected_last_event_id is _NO_PRECONDITION:
            return operation(None)
        return self._service.mutate_version_if_current(
            document_id,
            version,
            expected_last_event_id,
            operation,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            owner_or_privileged=True,
        )

    def import_existing_docx(
        self,
        document_id: str,
        version: int,
        source_path: Path,
        *,
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None or actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        operation = lambda _current: self._service.import_existing_docx(
            document_id,
            version,
            source_path,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        if expected_last_event_id is _NO_PRECONDITION:
            return operation(None)
        return self._service.mutate_version_if_current(
            document_id,
            version,
            expected_last_event_id,
            operation,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            owner_or_privileged=True,
        )

    def create_from_template(
        self,
        document_id: str,
        version: int,
        template_path: Path,
        *,
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        delegated_create_allowed: bool = False,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None or actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        existing = self._service.get_document_version(document_id, version)
        if existing is None:
            if actor is None:
                raise PermissionDeniedError("confirmed UserContext is required")
            if actor_role != SystemRole.QMB and not delegated_create_allowed:
                raise PermissionDeniedError("effective QMB or delegated create permission required")
        return self._service.create_from_template(
            document_id,
            version,
            template_path,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def get_profile(self, profile_id: str) -> WorkflowProfile:
        return self._service.get_profile(profile_id)

    def list_workflow_profile_definitions(
        self,
        *,
        actor: object,
        include_inactive: bool = True,
    ) -> list[dict[str, object]]:
        return self._service.list_workflow_profile_definitions(actor=actor, include_inactive=include_inactive)

    def list_workflow_profile_versions(
        self,
        profile_code: str,
        *,
        actor: object,
    ) -> list[dict[str, object]]:
        return self._service.list_workflow_profile_versions(profile_code, actor=actor)

    def create_workflow_profile_definition(
        self,
        payload: dict[str, object],
        *,
        actor: object,
        change_reason: str,
    ) -> dict[str, object]:
        return self._service.create_workflow_profile_definition(payload, actor=actor, change_reason=change_reason)

    def create_workflow_profile_version(
        self,
        profile_code: str,
        payload: dict[str, object],
        *,
        actor: object,
        change_reason: str,
    ) -> dict[str, object]:
        return self._service.create_workflow_profile_version(
            profile_code,
            payload,
            actor=actor,
            change_reason=change_reason,
        )

    def activate_workflow_profile_definition(
        self,
        profile_code: str,
        *,
        actor: object,
        change_reason: str,
    ) -> dict[str, object]:
        return self._service.set_workflow_profile_active(
            profile_code,
            actor=actor,
            is_active=True,
            change_reason=change_reason,
        )

    def deactivate_workflow_profile_definition(
        self,
        profile_code: str,
        *,
        actor: object,
        change_reason: str,
    ) -> dict[str, object]:
        return self._service.set_workflow_profile_active(
            profile_code,
            actor=actor,
            is_active=False,
            change_reason=change_reason,
        )

    def bind_document_type_default_profile(
        self,
        doc_type: DocumentType,
        profile_code: str,
        *,
        actor: object,
        change_reason: str,
    ) -> dict[str, object]:
        return self._service.bind_document_type_default_profile(
            doc_type,
            profile_code,
            actor=actor,
            change_reason=change_reason,
        )

    def list_profile_ids_for_control_class(self, control_class: ControlClass) -> list[str]:
        return self._service.list_profile_ids_for_control_class(control_class)

    def assign_workflow_roles(
        self,
        state: DocumentVersionState,
        *,
        editors: set[str],
        reviewers: set[str],
        approvers: set[str],
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None or actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        return self.mutate_version_if_current(
            state,
            expected_last_event_id,
            lambda current: self._service.assign_workflow_roles(
                current,
                editors=editors,
                reviewers=reviewers,
                approvers=approvers,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="assign_roles",
        )

    def start_workflow(
        self,
        state: DocumentVersionState,
        profile: WorkflowProfile | None = None,
        *,
        profile_id: str | None = None,
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        """Start workflow using the document's bound ``workflow_profile_id``.

        ``profile`` / ``profile_id`` are optional compatibility checks only and
        must match the stored binding when provided. The binding is never changed.
        """
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None or actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        return self.mutate_version_if_current(
            state,
            expected_last_event_id,
            lambda current: self._service.start_workflow(
                current,
                profile,
                profile_id=profile_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="start",
        )

    def complete_editing(
        self,
        state: DocumentVersionState,
        *,
        sign_request: object | None = None,
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None or actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        return self.mutate_version_if_current(
            state,
            expected_last_event_id,
            lambda current: self._service.complete_editing(
                current,
                sign_request=sign_request,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="complete_editing",
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

    def ensure_source_pdf_for_signing_if_current(
        self, state: DocumentVersionState, *, actor: UserContext, expected_last_event_id: str | None
    ) -> Path | None:
        user_id, role = actor_user_and_role(actor)
        return self._service.mutate_version_if_current(
            state.document_id,
            state.version,
            expected_last_event_id,
            lambda current: self._service.ensure_source_pdf_for_signing(
                current, actor_user_id=user_id, actor_role=role
            ),
        )

    def accept_review(
        self,
        state: DocumentVersionState,
        actor: UserContext | None = None,
        *,
        actor_user_id: str | None = None,
        sign_request: object | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        if actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        return self.mutate_version_if_current(
            state,
            expected_last_event_id,
            lambda current: self._service.accept_review(
                current,
                actor_user_id,
                sign_request=sign_request,
                actor_role=actor_role,
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="review_accept",
        )

    def reject_review(
        self,
        state: DocumentVersionState,
        reason: RejectionReason,
        *,
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        if actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        return self.mutate_version_if_current(
            state,
            expected_last_event_id,
            lambda current: self._service.reject_review(
                current, actor_user_id, reason, actor_role=actor_role
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="review_reject",
        )

    def accept_approval(
        self,
        state: DocumentVersionState,
        actor: UserContext | None = None,
        *,
        actor_user_id: str | None = None,
        sign_request: object | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        if actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        return self.mutate_version_if_current(
            state,
            expected_last_event_id,
            lambda current: self._service.accept_approval(
                current,
                actor_user_id,
                sign_request=sign_request,
                actor_role=actor_role,
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="approval_accept",
        )

    def reject_approval(
        self,
        state: DocumentVersionState,
        reason: RejectionReason,
        *,
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        if actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        return self.mutate_version_if_current(
            state,
            expected_last_event_id,
            lambda current: self._service.reject_approval(
                current, actor_user_id, reason, actor_role=actor_role
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="approval_reject",
        )

    def abort_workflow(
        self,
        state: DocumentVersionState,
        *,
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
        expected_last_event_id: str | None | object = _NO_PRECONDITION,
    ) -> DocumentVersionState:
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None or actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        return self.mutate_version_if_current(
            state,
            expected_last_event_id,
            lambda current: self._service.abort_workflow(
                current, actor_user_id=actor_user_id, actor_role=actor_role
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="abort",
        )

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

    def extend_annual_validity_signed(
        self,
        state: DocumentVersionState,
        *,
        actor: UserContext,
        sign_intent: dict[str, object],
        signature_api: object,
        scratch_root: Path,
        expected_last_event_id: str | None,
        duration_days: int,
        reason: str,
        review_outcome: ValidityExtensionOutcome,
    ) -> tuple[DocumentVersionState, bool]:
        user_id, role = actor_user_and_role(actor)
        if role != SystemRole.QMB:
            raise PermissionDeniedError("annual validity extension requires an effective QMB")

        def _extend(current: DocumentVersionState):
            if current.extension_count >= 3:
                return self._service.extend_annual_validity(
                    current,
                    actor_user_id=user_id,
                    signature_present=False,
                    duration_days=duration_days,
                    reason=reason,
                    review_outcome=review_outcome,
                )
            sign_request = self.build_workflow_sign_request_from_intent(
                state=current,
                transition="EXTEND_VALIDITY",
                sign_intent=sign_intent,
                actor=actor,
                signature_api=signature_api,
                scratch_root=scratch_root,
            )
            artifact = None
            try:
                artifact = self._service.sign_and_store_signed_artifact(
                    current, sign_request, transition="EXTEND_VALIDITY"
                )
                return self._service.extend_annual_validity(
                    current,
                    actor_user_id=user_id,
                    signature_present=True,
                    duration_days=duration_days,
                    reason=reason,
                    review_outcome=review_outcome,
                )
            except Exception:
                if artifact is not None:
                    try:
                        self._service.delete_artifact(artifact)
                    except Exception:
                        pass
                raise

        return self._service.mutate_version_if_current(
            state.document_id,
            state.version,
            expected_last_event_id,
            _extend,
            actor_user_id=user_id,
            actor_role=role,
            action="extend_validity",
        )

    def create_new_version_after_archive(
        self,
        state: DocumentVersionState,
        next_version: int,
        *,
        expected_last_event_id: str | None,
        actor: UserContext | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        """Create a successor version under CAS + shared ``new_version`` policy.

        ``expected_last_event_id`` is required (no ``_NO_PRECONDITION`` default).
        Policy is evaluated on the locked persisted ``current`` after the ETag
        compare; the use-case runs only as the mutation operation.
        """
        if actor is not None:
            actor_user_id, actor_role = actor_user_and_role(actor)
        if actor_user_id is None or actor_role is None:
            raise PermissionDeniedError("confirmed UserContext is required")
        return self.mutate_version_if_current(
            state,
            expected_last_event_id,
            lambda current: self._service.create_new_version_after_archive(
                current,
                next_version,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="new_version",
        )

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

    def update_document_header_if_current(
        self, document_id: str, *, expected_updated_at: str, actor: UserContext, **changes
    ) -> DocumentHeader:
        user_id, role = actor_user_and_role(actor)
        return self._service.update_document_header_if_current(
            document_id,
            expected_updated_at=expected_updated_at,
            actor_user_id=user_id,
            actor_role=role,
            **changes,
        )


class DocumentsReadApi:
    """Read-Confirmation API for training integration (§6.1)."""

    def __init__(self, service: DocumentsService) -> None:
        self._service = service

    def open_released_document_for_training(
        self, user_id: str, document_id: str, version: int
    ) -> DocumentReadSession:
        return self._service.open_released_document_for_training(user_id, document_id, version)

    def open_released_document_for_actor(
        self, actor: UserContext, document_id: str, version: int
    ) -> DocumentReadSession:
        user_id, _role = actor_user_and_role(actor)
        return self.open_released_document_for_training(user_id, document_id, version)

    def confirm_released_document_read(
        self, user_id: str, document_id: str, version: int, *, source: str
    ) -> DocumentReadReceipt:
        return self._service.confirm_released_document_read(user_id, document_id, version, source=source)

    def confirm_released_document_read_for_actor(
        self, actor: UserContext, document_id: str, version: int, *, source: str
    ) -> DocumentReadReceipt:
        user_id, _role = actor_user_and_role(actor)
        return self.confirm_released_document_read(user_id, document_id, version, source=source)

    def get_read_receipt(
        self, user_id: str, document_id: str, version: int
    ) -> DocumentReadReceipt | None:
        return self._service.get_read_receipt(user_id, document_id, version)

    def get_read_receipt_for_actor(
        self, actor: UserContext, document_id: str, version: int
    ) -> DocumentReadReceipt | None:
        user_id, _role = actor_user_and_role(actor)
        return self.get_read_receipt(user_id, document_id, version)

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

    def start_tracked_pdf_read_for_actor(
        self,
        actor: UserContext,
        document_id: str,
        version: int,
        *,
        artifact_id: str | None,
        total_pages: int,
        source: str,
        min_seconds_per_page: int = 10,
    ) -> TrackedPdfReadSession:
        user_id, _role = actor_user_and_role(actor)
        return self.start_tracked_pdf_read(
            user_id,
            document_id,
            version,
            artifact_id=artifact_id,
            total_pages=total_pages,
            source=source,
            min_seconds_per_page=min_seconds_per_page,
        )

    def _require_session_actor(self, actor: UserContext, session_id: str) -> None:
        user_id, _role = actor_user_and_role(actor)
        session = self._service.get_tracked_pdf_read_session(session_id)
        if session is None:
            raise ValidationError("tracked PDF read session not found")
        if session.user_id != user_id:
            raise PermissionDeniedError("tracked PDF read session belongs to another user")

    def record_page_dwell(self, session_id: str, *, page_number: int, dwell_seconds: int) -> PdfReadProgress:
        return self._service.record_page_dwell(session_id, page_number=page_number, dwell_seconds=dwell_seconds)

    def record_page_dwell_for_actor(
        self, actor: UserContext, session_id: str, *, page_number: int, dwell_seconds: int
    ) -> PdfReadProgress:
        self._require_session_actor(actor, session_id)
        return self.record_page_dwell(session_id, page_number=page_number, dwell_seconds=dwell_seconds)

    def get_pdf_read_progress(self, session_id: str) -> PdfReadProgress:
        return self._service.get_pdf_read_progress(session_id)

    def get_pdf_read_progress_for_actor(self, actor: UserContext, session_id: str) -> PdfReadProgress:
        self._require_session_actor(actor, session_id)
        return self.get_pdf_read_progress(session_id)

    def finalize_tracked_pdf_read(self, session_id: str, *, source: str) -> DocumentReadReceipt | None:
        return self._service.finalize_tracked_pdf_read(session_id, source=source)

    def finalize_tracked_pdf_read_for_actor(
        self, actor: UserContext, session_id: str, *, source: str
    ) -> DocumentReadReceipt | None:
        self._require_session_actor(actor, session_id)
        return self.finalize_tracked_pdf_read(session_id, source=source)


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

    def sync_docx_comments_if_current(
        self, state: DocumentVersionState, *, expected_last_event_id: str | None,
        actor_user_id: str, actor_role: SystemRole,
    ) -> list[WorkflowCommentListItem]:
        return self._service.mutate_version_if_current(
            state.document_id,
            state.version,
            expected_last_event_id,
            lambda current: self._service.sync_docx_comments(
                current, actor_user_id=actor_user_id, actor_role=actor_role
            ),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="comments",
        )

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

    def create_pdf_workflow_comment_if_current(self, state: DocumentVersionState, *, expected_last_event_id: str | None, **kwargs):
        actor_user_id = kwargs.get("actor_user_id")
        actor_role = kwargs.get("actor_role")
        return self._service.mutate_version_if_current(
            state.document_id,
            state.version,
            expected_last_event_id,
            lambda current: self._service.create_pdf_workflow_comment(current, **kwargs),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="comments",
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

    def set_workflow_comment_status_if_current(self, comment_id: str, *, expected_updated_at: str, **kwargs):
        return self._service.set_workflow_comment_status_if_current(
            comment_id, expected_updated_at=expected_updated_at, **kwargs
        )

