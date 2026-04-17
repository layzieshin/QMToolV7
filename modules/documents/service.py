from __future__ import annotations

import tempfile
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from . import artifact_ops
from . import eventing
from . import naming
from . import registry_sync as _registry_sync
from . import signature_guard
from . import validation as _val
from .contracts import (
    ArtifactSourceType,
    ArtifactType,
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentReadReceipt,
    PdfReadProgress,
    DocumentReadSession,
    DocumentStatus,
    DocumentTaskItem,
    DocumentType,
    DocumentVersionState,
    RecentDocumentItem,
    RejectionReason,
    ReleasedDocumentItem,
    ReviewActionItem,
    SystemRole,
    TrackedPdfReadSession,
    WorkflowAssignments,
    WorkflowCommentContext,
    WorkflowCommentDetail,
    WorkflowCommentListItem,
    WorkflowCommentRecord,
    WorkflowCommentStatus,
    WorkflowProfile,
    ChangeRequest,
    control_class_for,
)
from .errors import InvalidTransitionError, PermissionDeniedError, ValidationError
from .profile_store import WorkflowProfileStoreJSON
from .readmodel_use_cases import DocumentsReadmodelUseCases
from .repository import DocumentsRepository
from .storage import DocumentsStoragePort
from .workflow_use_cases import DocumentsWorkflowUseCases


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentsService:
    _FORBIDDEN_CUSTOM_FIELD_KEYS = _val._FORBIDDEN_CUSTOM_FIELD_KEYS
    _FORBIDDEN_CUSTOM_FIELD_PREFIXES = _val._FORBIDDEN_CUSTOM_FIELD_PREFIXES
    _ALLOWED_CUSTOM_FIELD_KEY_RE = _val._ALLOWED_CUSTOM_FIELD_KEY_RE

    def __init__(
        self,
        event_bus: object | None = None,
        repository: DocumentsRepository | None = None,
        profile_store: WorkflowProfileStoreJSON | None = None,
        signature_api: object | None = None,
        storage_port: DocumentsStoragePort | None = None,
        registry_projection_api: object | None = None,
        audit_logger: object | None = None,
        docx_to_pdf_converter: Callable[[Path, Path], None] | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._states: dict[tuple[str, int], DocumentVersionState] = {}
        self._repository = repository
        self._profile_store = profile_store
        self._signature_api = signature_api
        self._storage_port = storage_port
        self._registry_projection_api = registry_projection_api
        self._audit_logger = audit_logger
        self._docx_to_pdf_converter = docx_to_pdf_converter
        self._readmodels = DocumentsReadmodelUseCases(
            iter_states=self._iter_all_states,
            matches_user_context=lambda state, user_id, role: self._matches_user_context(state, user_id=user_id, role=role),
        )
        self._workflow_use_cases = DocumentsWorkflowUseCases(self)

    # --- Delegation to eventing module ---

    def _emit_audit(self, *, action: str, actor: str, target: str, result: str, reason: str = "") -> None:
        eventing.emit_audit(self._audit_logger, action=action, actor=actor, target=target, result=result, reason=reason)

    def _publish(
        self,
        name: str,
        state: DocumentVersionState,
        payload: dict[str, object],
        *,
        actor_user_id: str | None = None,
    ) -> EventEnvelope | None:
        return eventing.publish_event(self._event_bus, name, state, payload, actor_user_id=actor_user_id)

    # --- Delegation to registry_sync module ---

    def _sync_registry(self, state: DocumentVersionState, event: EventEnvelope | None) -> None:
        _registry_sync.sync_registry(self._registry_projection_api, state, event)

    # --- Delegation to artifact_ops module ---

    def _resolve_artifact_path(self, artifact: DocumentArtifact) -> Path | None:
        return artifact_ops.resolve_artifact_path(artifact, self._storage_port)

    def _resolve_source_pdf_artifact_path(self, state: DocumentVersionState) -> Path | None:
        return artifact_ops.resolve_source_pdf_path(state, self._repository, self._storage_port)

    def _resolve_source_docx_artifact_path(self, state: DocumentVersionState) -> Path | None:
        return artifact_ops.resolve_source_docx_path(state, self._repository, self._storage_port)

    def _convert_docx_to_temp_pdf_for_workflow(self, state: DocumentVersionState, source_docx: Path) -> Path:
        return artifact_ops.convert_docx_to_temp_pdf(state, source_docx, self._docx_to_pdf_converter)

    def _create_artifact(
        self,
        *,
        state: DocumentVersionState,
        source_path: Path,
        artifact_type: ArtifactType,
        source_type: ArtifactSourceType,
        metadata: dict[str, str],
    ) -> DocumentArtifact:
        if self._repository is None:
            raise ValidationError("repository is required for artifact registry")
        if self._storage_port is None:
            raise ValidationError("storage_port is required for artifact storage")
        return artifact_ops.create_artifact(
            state=state,
            source_path=source_path,
            artifact_type=artifact_type,
            source_type=source_type,
            metadata=metadata,
            repository=self._repository,
            storage_port=self._storage_port,
        )

    def _ensure_source_pdf_artifact_for_signing(
        self,
        state: DocumentVersionState,
        *,
        actor_user_id: str | None = None,
    ) -> Path | None:
        source_pdf = self._resolve_source_pdf_artifact_path(state)
        if source_pdf is not None:
            return source_pdf
        source_docx = self._resolve_source_docx_artifact_path(state)
        if source_docx is None:
            return None

        staged_pdf = self._convert_docx_to_temp_pdf_for_workflow(state, source_docx)
        artifact = self._create_artifact(
            state=state,
            source_path=staged_pdf,
            artifact_type=ArtifactType.SOURCE_PDF,
            source_type=ArtifactSourceType.GENERATED,
            metadata={
                "generated_from": str(source_docx),
                "intake_mode": "docx_to_pdf_for_editing_complete",
            },
        )
        actor = actor_user_id or state.owner_user_id or "system"
        event = self._publish(
            "domain.documents.artifact.imported.v1",
            state,
            {
                "artifact_id": artifact.artifact_id,
                "artifact_type": ArtifactType.SOURCE_PDF.value,
                "source_type": ArtifactSourceType.GENERATED.value,
            },
            actor_user_id=actor_user_id,
        )
        self._sync_registry(state, event)
        self._emit_audit(
            action="documents.artifact.source_pdf.generated",
            actor=str(actor),
            target=f"{state.document_id}:{state.version}",
            result="ok",
            reason="docx_to_pdf_before_editing_complete",
        )
        return self._resolve_artifact_path(artifact) or staged_pdf

    def _ensure_release_pdf_artifact(self, state: DocumentVersionState) -> None:
        if self._repository is None or self._storage_port is None:
            return
        source_path = artifact_ops.resolve_release_pdf_source_path(state, self._repository, self._storage_port)
        if source_path is None or not source_path.exists():
            raise ValidationError(
                f"RELEASED_PDF generation failed for {state.document_id} v{state.version}: no source PDF artifact available"
            )
        generated_name = naming.build_released_filename(state)
        with tempfile.TemporaryDirectory(prefix="qmtool-release-") as tmp_dir:
            staged_path = Path(tmp_dir) / generated_name
            artifact_ops.protect_pdf_copy(source_path, staged_path)
            self._create_artifact(
                state=state,
                source_path=staged_path,
                artifact_type=ArtifactType.RELEASED_PDF,
                source_type=ArtifactSourceType.GENERATED,
                metadata={
                    "generated_filename": generated_name,
                    "source": str(source_path),
                    "protected": "true",
                },
            )
        self._require_current_released_pdf_artifact(state)

    def _require_current_released_pdf_artifact(self, state: DocumentVersionState) -> None:
        if self._repository is None:
            return
        artifacts = self._repository.list_artifacts(state.document_id, state.version)
        has_current_released = any(
            artifact.artifact_type == ArtifactType.RELEASED_PDF and bool(getattr(artifact, "is_current", False))
            for artifact in artifacts
        )
        if not has_current_released:
            raise ValidationError(
                f"approved document requires current RELEASED_PDF artifact: {state.document_id} v{state.version}"
            )

    # --- Delegation to naming module (keep static methods for backward compat) ---

    @staticmethod
    def _build_released_filename(state: DocumentVersionState) -> str:
        return naming.build_released_filename(state)

    @staticmethod
    def _transliterate_umlauts(raw: str) -> str:
        return naming.transliterate_umlauts(raw)

    @staticmethod
    def _protect_pdf_copy(source_path: Path, target_path: Path) -> None:
        artifact_ops.protect_pdf_copy(source_path, target_path)

    # --- Delegation to validation module ---

    @staticmethod
    def _assert_custom_fields_safe(custom_fields: dict[str, object]) -> None:
        _val.assert_custom_fields_safe(custom_fields)

    @staticmethod
    def _assert_custom_field_value_safe(value: object, key: str) -> None:
        _val._assert_custom_field_value_safe(value, key)

    @staticmethod
    def _assert_state_invariants(state: DocumentVersionState) -> None:
        _val.assert_state_invariants(state)

    @staticmethod
    def _assert_profile(profile: WorkflowProfile) -> None:
        _val.assert_profile(profile)

    @staticmethod
    def _assert_rejection_reason(reason: RejectionReason) -> None:
        _val.assert_rejection_reason(reason)

    @staticmethod
    def _assert_active_profile(state: DocumentVersionState) -> None:
        _val.assert_active_profile(state)

    @staticmethod
    def _assert_assignments_for_profile(state: DocumentVersionState, profile: WorkflowProfile) -> None:
        _val.assert_assignments_for_profile(state, profile)

    @staticmethod
    def _ensure_owner_or_privileged(state: DocumentVersionState, actor_user_id: str, actor_role: SystemRole) -> None:
        _val.ensure_owner_or_privileged(state, actor_user_id, actor_role)

    @staticmethod
    def _ensure_editor_or_owner_or_privileged(state: DocumentVersionState, actor_user_id: str, actor_role: SystemRole) -> None:
        _val.ensure_editor_or_owner_or_privileged(state, actor_user_id, actor_role)

    @staticmethod
    def _ensure_assignment_update_allowed(
        state: DocumentVersionState,
        actor_user_id: str,
        actor_role: SystemRole,
        *,
        new_editors: frozenset[str],
        new_reviewers: frozenset[str],
        new_approvers: frozenset[str],
    ) -> None:
        _val.ensure_assignment_update_allowed(
            state, actor_user_id, actor_role,
            new_editors=new_editors, new_reviewers=new_reviewers, new_approvers=new_approvers,
        )

    @staticmethod
    def _validate_source_file(source_path: Path, *, allowed_suffixes: set[str]) -> None:
        _val.validate_source_file(source_path, allowed_suffixes=allowed_suffixes)

    def _next_status_from_profile(self, profile: WorkflowProfile | None, current: DocumentStatus) -> DocumentStatus:
        return _val.next_status_from_profile(profile, current)

    # --- Delegation to signature_guard module ---

    def _enforce_signature_transition(
        self,
        state: DocumentVersionState,
        transition: str,
        sign_request: object | None,
    ) -> None:
        signature_guard.enforce_signature_transition(
            state, transition, sign_request,
            signature_api=self._signature_api,
            repository=self._repository,
            storage_port=self._storage_port,
            create_artifact_fn=self._create_artifact,
            resolve_artifact_path_fn=self._resolve_artifact_path,
        )

    def _resolve_signature_input_pdf_for_transition(
        self,
        state: DocumentVersionState,
        transition: str,
    ) -> Path | None:
        return signature_guard._resolve_signature_input_pdf(
            state, transition,
            repository=self._repository,
            resolve_artifact_path_fn=self._resolve_artifact_path,
        )

    @staticmethod
    def _is_signature_required(state: DocumentVersionState, transition: str) -> bool:
        return signature_guard.is_signature_required(state, transition)

    # --- Core facade methods (unchanged public API) ---

    def create_document_version(
        self,
        document_id: str,
        version: int,
        owner_user_id: str | None = None,
        *,
        title: str = "",
        description: str | None = None,
        doc_type: DocumentType = DocumentType.OTHER,
        control_class: ControlClass | None = None,
        workflow_profile_id: str = "long_release",
        custom_fields: dict[str, object] | None = None,
    ) -> DocumentVersionState:
        if not document_id.strip():
            raise ValidationError("document_id is required")
        if version <= 0:
            raise ValidationError("version must be > 0")
        normalized_title = title.strip() or document_id
        fields = custom_fields or {}
        self._assert_custom_fields_safe(fields)
        created = DocumentVersionState(
            document_id=document_id,
            version=version,
            title=normalized_title,
            description=description,
            doc_type=doc_type,
            control_class=control_class or control_class_for(doc_type),
            workflow_profile_id=workflow_profile_id,
            owner_user_id=owner_user_id,
            custom_fields=fields,
            created_at=datetime.now(timezone.utc),
            created_by=owner_user_id,
        )
        self._store_header(
            DocumentHeader(
                document_id=document_id,
                doc_type=doc_type,
                control_class=created.control_class,
                workflow_profile_id=workflow_profile_id,
                register_binding=True,
            )
        )
        self._store_state(created)
        self._sync_registry(created, None)
        return created

    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        if self._repository is not None:
            return self._repository.list_by_status(status)
        return sorted(
            (state for state in self._states.values() if state.status == status),
            key=lambda state: (state.document_id, state.version),
        )

    def get_document_version(self, document_id: str, version: int) -> DocumentVersionState | None:
        if self._repository is not None:
            return self._repository.get(document_id, version)
        return self._states.get((document_id, version))

    def get_document_header(self, document_id: str) -> DocumentHeader | None:
        if self._repository is None:
            return None
        return self._repository.get_header(document_id)

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
        if self._repository is None:
            raise ValidationError("repository is required for header updates")
        if actor_user_id is None or actor_role is None:
            raise ValidationError("actor_user_id and actor_role are required for header updates")
        if actor_role not in (SystemRole.ADMIN, SystemRole.QMB):
            raise PermissionDeniedError("only QMB or ADMIN may update document headers")
        existing = self._repository.get_header(document_id)
        if existing is None:
            raise ValidationError(f"document header not found: {document_id}")
        if doc_type is not None and doc_type != existing.doc_type:
            raise ValidationError("doc_type cannot be changed after first creation")
        if control_class is not None and control_class != existing.control_class:
            raise ValidationError("control_class cannot be changed after first creation")
        if workflow_profile_id is not None and workflow_profile_id != existing.workflow_profile_id:
            self._assert_workflow_profile_update_allowed(document_id, existing.control_class, workflow_profile_id)
        updated = DocumentHeader(
            document_id=document_id,
            doc_type=doc_type or existing.doc_type,
            control_class=control_class or existing.control_class,
            workflow_profile_id=workflow_profile_id or existing.workflow_profile_id,
            register_binding=existing.register_binding,
            department=department if department is not None else existing.department,
            site=site if site is not None else existing.site,
            regulatory_scope=regulatory_scope if regulatory_scope is not None else existing.regulatory_scope,
            distribution_roles=(
                tuple(sorted({value.strip() for value in distribution_roles if str(value).strip()}))
                if distribution_roles is not None
                else existing.distribution_roles
            ),
            distribution_sites=(
                tuple(sorted({value.strip() for value in distribution_sites if str(value).strip()}))
                if distribution_sites is not None
                else existing.distribution_sites
            ),
            distribution_departments=(
                tuple(sorted({value.strip() for value in distribution_departments if str(value).strip()}))
                if distribution_departments is not None
                else existing.distribution_departments
            ),
            created_at=existing.created_at,
            updated_at=_utcnow(),
        )
        self._repository.upsert_header(updated)
        return updated

    def _build_distribution_snapshot(self, state: DocumentVersionState) -> dict[str, object]:
        header = self.get_document_header(state.document_id)
        if header is None:
            return {}
        return {
            "frozen_at": _utcnow().isoformat(),
            "roles": list(header.distribution_roles),
            "sites": list(header.distribution_sites),
            "departments": list(header.distribution_departments),
            "header_department": header.department,
            "header_site": header.site,
            "header_regulatory_scope": header.regulatory_scope,
        }

    def update_version_metadata(
        self,
        state: DocumentVersionState,
        *,
        title: str | None = None,
        description: str | None = None,
        valid_until: datetime | None = None,
        next_review_at: datetime | None = None,
        custom_fields: dict[str, object] | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        if actor_user_id is None or actor_role is None:
            raise ValidationError("actor_user_id and actor_role are required for metadata updates")
        self._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        if (valid_until is not None or next_review_at is not None) and state.status not in (
            DocumentStatus.APPROVED,
            DocumentStatus.ARCHIVED,
        ):
            raise ValidationError("validity dates can only be updated for APPROVED or ARCHIVED versions")
        if state.status == DocumentStatus.APPROVED and (valid_until is not None or next_review_at is not None):
            raise ValidationError(
                "valid_until/next_review_at duerfen im Status APPROVED nur ueber extend_annual_validity geaendert werden"
            )
        merged_custom = dict(state.custom_fields)
        if custom_fields is not None:
            self._assert_custom_fields_safe(custom_fields)
            merged_custom.update(custom_fields)
        updated = replace(
            state,
            title=(title.strip() if title is not None and title.strip() else state.title),
            description=description if description is not None else state.description,
            valid_until=valid_until if valid_until is not None else state.valid_until,
            next_review_at=next_review_at if next_review_at is not None else state.next_review_at,
            custom_fields=merged_custom,
        )
        event = self._publish(
            "domain.documents.metadata.updated.v1",
            updated,
            {"keys": sorted((custom_fields or {}).keys())},
            actor_user_id=actor_user_id,
        )
        self._store_state(updated)
        self._sync_registry(updated, event)
        return updated

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
        self._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        normalized_change_id, normalized_reason, normalized_refs = _val.validate_change_request_input(
            change_id,
            reason,
            list(impact_refs),
        )
        existing_items = state.custom_fields.get("change_requests", [])
        if not isinstance(existing_items, list):
            raise ValidationError("custom field 'change_requests' must be a list")
        existing_change_ids = {
            str(item.get("change_id", "")).strip()
            for item in existing_items
            if isinstance(item, dict)
        }
        if normalized_change_id in existing_change_ids:
            raise ValidationError(f"change request already exists: {normalized_change_id}")
        request = ChangeRequest(
            change_id=normalized_change_id,
            reason=normalized_reason,
            impact_refs=normalized_refs,
            created_by=actor_user_id,
        )
        request_payload = {
            "change_id": request.change_id,
            "reason": request.reason,
            "impact_refs": list(request.impact_refs),
            "created_by": request.created_by,
            "created_at": request.created_at.isoformat(),
        }
        merged_custom = dict(state.custom_fields)
        merged_custom["change_requests"] = [*existing_items, request_payload]
        updated = replace(state, custom_fields=merged_custom)
        with self._write_transaction():
            self._store_state(updated)
            event = self._publish(
                "domain.documents.change_request.added.v1",
                updated,
                {"change_id": request.change_id, "impact_refs": list(request.impact_refs)},
                actor_user_id=actor_user_id,
            )
            self._sync_registry(updated, event)
        return updated

    def list_change_requests(self, state: DocumentVersionState) -> list[dict[str, object]]:
        raw_items = state.custom_fields.get("change_requests", [])
        if not isinstance(raw_items, list):
            return []
        return [item for item in raw_items if isinstance(item, dict)]

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        if self._repository is None:
            return []
        return self._repository.list_artifacts(document_id, version)

    def list_tasks_for_user(self, user_id: str, role: str, scope: str | None = None) -> list[DocumentTaskItem]:
        return self._readmodels.list_tasks_for_user(user_id=user_id, role=role, scope=scope)

    def list_review_actions_for_user(self, user_id: str, role: str) -> list[ReviewActionItem]:
        return self._readmodels.list_review_actions_for_user(user_id=user_id, role=role)

    def list_recent_documents_for_user(self, user_id: str, role: str) -> list[RecentDocumentItem]:
        return self._readmodels.list_recent_documents_for_user(user_id=user_id, role=role)

    def list_current_released_documents(self) -> list[ReleasedDocumentItem]:
        return self._readmodels.list_current_released_documents()

    def get_profile(self, profile_id: str) -> WorkflowProfile:
        if self._profile_store is None:
            if profile_id == "long_release":
                return WorkflowProfile.long_release_path()
            raise ValidationError(f"profile store missing and profile '{profile_id}' is unknown")
        return self._profile_store.get(profile_id)

    def import_existing_pdf(
        self,
        document_id: str,
        version: int,
        source_path: Path,
        *,
        actor_user_id: str,
        actor_role: SystemRole,
    ) -> DocumentVersionState:
        self._validate_source_file(source_path, allowed_suffixes={".pdf"})
        state = self._ensure_document_version(
            document_id, version, owner_user_id=actor_user_id,
            doc_type=DocumentType.EXT, control_class=ControlClass.EXTERNAL,
            workflow_profile_id="external_control",
        )
        self._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        artifact = self._create_artifact(
            state=state, source_path=source_path,
            artifact_type=ArtifactType.SOURCE_PDF,
            source_type=ArtifactSourceType.IMPORT_PDF,
            metadata={"intake_mode": "import_pdf"},
        )
        event = self._publish(
            "domain.documents.artifact.imported.v1", state,
            {"artifact_id": artifact.artifact_id}, actor_user_id=actor_user_id,
        )
        self._sync_registry(state, event)
        return state

    def import_existing_docx(
        self,
        document_id: str,
        version: int,
        source_path: Path,
        *,
        actor_user_id: str,
        actor_role: SystemRole,
    ) -> DocumentVersionState:
        self._validate_source_file(source_path, allowed_suffixes={".docx"})
        state = self._ensure_document_version(
            document_id, version, owner_user_id=actor_user_id,
            doc_type=DocumentType.OTHER, control_class=ControlClass.CONTROLLED,
            workflow_profile_id="long_release",
        )
        self._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        artifact = self._create_artifact(
            state=state, source_path=source_path,
            artifact_type=ArtifactType.SOURCE_DOCX,
            source_type=ArtifactSourceType.IMPORT_DOCX,
            metadata={"intake_mode": "import_docx"},
        )
        event = self._publish(
            "domain.documents.artifact.imported.v1", state,
            {"artifact_id": artifact.artifact_id}, actor_user_id=actor_user_id,
        )
        self._sync_registry(state, event)
        return state

    def create_from_template(
        self,
        document_id: str,
        version: int,
        template_path: Path,
        *,
        actor_user_id: str,
        actor_role: SystemRole,
    ) -> DocumentVersionState:
        self._validate_source_file(template_path, allowed_suffixes={".dotx", ".doct"})
        state = self._ensure_document_version(
            document_id, version, owner_user_id=actor_user_id,
            doc_type=DocumentType.OTHER, control_class=ControlClass.CONTROLLED,
            workflow_profile_id="long_release",
        )
        self._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        source_type = (
            ArtifactSourceType.TEMPLATE_DOTX if template_path.suffix.lower() == ".dotx" else ArtifactSourceType.TEMPLATE_DOCT
        )
        artifact = self._create_artifact(
            state=state, source_path=template_path,
            artifact_type=ArtifactType.SOURCE_DOCX,
            source_type=source_type,
            metadata={"intake_mode": "create_from_template"},
        )
        event = self._publish(
            "domain.documents.template.created.v1", state,
            {"artifact_id": artifact.artifact_id}, actor_user_id=actor_user_id,
        )
        self._sync_registry(state, event)
        return state

    # --- Workflow delegation (unchanged) ---

    def assign_workflow_roles(self, state, *, editors, reviewers, approvers, actor_user_id=None, actor_role=None):
        return self._workflow_use_cases.assign_workflow_roles(
            state, editors=editors, reviewers=reviewers, approvers=approvers,
            actor_user_id=actor_user_id, actor_role=actor_role,
        )

    def start_workflow(self, state, profile, *, actor_user_id=None, actor_role=None):
        return self._workflow_use_cases.start_workflow(state, profile, actor_user_id=actor_user_id, actor_role=actor_role)

    def complete_editing(self, state, *, sign_request=None, actor_user_id=None, actor_role=None):
        return self._workflow_use_cases.complete_editing(state, sign_request=sign_request, actor_user_id=actor_user_id, actor_role=actor_role)

    def accept_review(self, state, actor_user_id, *, sign_request=None, actor_role=None):
        return self._workflow_use_cases.accept_review(state, actor_user_id, sign_request=sign_request, actor_role=actor_role)

    def reject_review(self, state, actor_user_id, reason, actor_role=None):
        return self._workflow_use_cases.reject_review(state, actor_user_id, reason, actor_role=actor_role)

    def accept_approval(self, state, actor_user_id, *, sign_request=None, actor_role=None):
        return self._workflow_use_cases.accept_approval(state, actor_user_id, sign_request=sign_request, actor_role=actor_role)

    def reject_approval(self, state, actor_user_id, reason, actor_role=None):
        return self._workflow_use_cases.reject_approval(state, actor_user_id, reason, actor_role=actor_role)

    def abort_workflow(self, state, *, actor_user_id=None, actor_role=None):
        return self._workflow_use_cases.abort_workflow(state, actor_user_id=actor_user_id, actor_role=actor_role)

    def archive_approved(self, state, actor_role, actor_user_id=None):
        return self._workflow_use_cases.archive_approved(state, actor_role, actor_user_id=actor_user_id)

    def extend_annual_validity(
        self,
        state,
        *,
        actor_user_id: str,
        signature_present: bool,
        duration_days: int,
        reason: str,
        review_outcome,
    ):
        return self._workflow_use_cases.extend_annual_validity(
            state,
            actor_user_id=actor_user_id,
            signature_present=signature_present,
            duration_days=duration_days,
            reason=reason,
            review_outcome=review_outcome,
        )

    def create_new_version_after_archive(self, state, next_version):
        return self._workflow_use_cases.create_new_version_after_archive(state, next_version)

    def ensure_source_pdf_for_signing(self, state, *, actor_user_id=None, actor_role=None):
        if actor_user_id is not None and actor_role is not None:
            self._ensure_editor_or_owner_or_privileged(state, actor_user_id, actor_role)
        return self._ensure_source_pdf_artifact_for_signing(state, actor_user_id=actor_user_id)

    # --- Internal helpers ---

    def _store_state(self, state: DocumentVersionState) -> None:
        self._assert_state_invariants(state)
        self._states[(state.document_id, state.version)] = state
        if self._repository is not None:
            self._repository.upsert(state)

    @contextmanager
    def _write_transaction(self):
        if self._repository is None:
            with nullcontext():
                yield
            return
        begin = getattr(self._repository, "write_transaction", None)
        if callable(begin):
            with begin():
                yield
            return
        with nullcontext():
            yield

    def _store_header(self, header: DocumentHeader) -> None:
        if self._repository is not None:
            existing = self._repository.get_header(header.document_id)
            if existing is not None:
                if existing.doc_type != header.doc_type:
                    raise ValidationError("doc_type cannot be changed after first creation")
                if existing.control_class != header.control_class:
                    raise ValidationError("control_class cannot be changed after first creation")
                return
            self._repository.upsert_header(header)

    def _ensure_document_version(
        self, document_id, version, owner_user_id=None,
        *, doc_type=DocumentType.OTHER, control_class=None, workflow_profile_id="long_release",
    ) -> DocumentVersionState:
        state = self.get_document_version(document_id, version)
        if state is not None:
            return state
        return self.create_document_version(
            document_id, version, owner_user_id=owner_user_id,
            doc_type=doc_type, control_class=control_class,
            workflow_profile_id=workflow_profile_id, title=document_id,
        )

    def _iter_all_states(self) -> list[DocumentVersionState]:
        if self._repository is None:
            return list(self._states.values())
        states: dict[tuple[str, int], DocumentVersionState] = {}
        for status in DocumentStatus:
            for state in self.list_by_status(status):
                states[(state.document_id, state.version)] = state
        return list(states.values())

    @staticmethod
    def _matches_user_context(state: DocumentVersionState, *, user_id: str, role: str) -> bool:
        role_upper = role.upper()
        if role_upper in ("ADMIN", "QMB"):
            return True
        if state.owner_user_id == user_id:
            return True
        if user_id in state.assignments.editors:
            return True
        if user_id in state.assignments.reviewers:
            return True
        if user_id in state.assignments.approvers:
            return True
        if state.last_actor_user_id == user_id:
            return True
        return False

    def _supersede_other_approved_versions(self, state: DocumentVersionState, actor_user_id: str) -> list[int]:
        if self._repository is None:
            return []
        superseded: list[int] = []
        for candidate in self._repository.list_versions(state.document_id):
            if candidate.version == state.version:
                continue
            if candidate.status != DocumentStatus.APPROVED:
                continue
            archived = replace(
                candidate,
                status=DocumentStatus.ARCHIVED,
                workflow_active=False,
                archived_at=_utcnow(),
                archived_by=actor_user_id,
                superseded_by_version=state.version,
            )
            self._store_state(archived)
            superseded.append(candidate.version)
        return superseded

    def _assert_workflow_profile_update_allowed(
        self, document_id: str, control_class: ControlClass, workflow_profile_id: str,
    ) -> None:
        profile = self.get_profile(workflow_profile_id)
        if profile.control_class != control_class:
            raise ValidationError(
                f"profile control_class '{profile.control_class.value}' does not match document control_class '{control_class.value}'"
            )
        if self._repository is None:
            return
        for version_state in self._repository.list_versions(document_id):
            if version_state.status != DocumentStatus.PLANNED:
                raise ValidationError("workflow_profile_id can only be changed while all versions are PLANNED")

    # --- Read Confirmation ---

    def open_released_document_for_training(
        self, user_id: str, document_id: str, version: int
    ) -> DocumentReadSession:
        state = self.get_document_version(document_id, version)
        if state is None:
            raise ValidationError("document version not found")
        if state.status != DocumentStatus.APPROVED:
            raise ValidationError("document version is not approved")
        if state.superseded_by_version is not None:
            raise ValidationError("document version is superseded")
        self._require_current_released_pdf_artifact(state)
        return DocumentReadSession(
            session_id=uuid4().hex,
            user_id=user_id,
            document_id=document_id,
            version=version,
            opened_at=_utcnow(),
        )

    def confirm_released_document_read(
        self, user_id: str, document_id: str, version: int, *, source: str
    ) -> DocumentReadReceipt:
        state = self.get_document_version(document_id, version)
        if state is None:
            raise ValidationError("document version not found")
        if state.status != DocumentStatus.APPROVED:
            raise ValidationError("document version is not approved")
        self._require_current_released_pdf_artifact(state)
        now = _utcnow()
        receipt = DocumentReadReceipt(
            receipt_id=uuid4().hex,
            user_id=user_id,
            document_id=document_id,
            version=version,
            confirmed_at=now,
            source=source,
        )
        if self._repository is not None:
            self._repository.create_read_receipt(receipt)
        envelope = eventing.publish_event(
            self._event_bus,
            "domain.documents.read.confirmed.v1",
            state,
            {
                "user_id": user_id,
                "document_id": document_id,
                "version": version,
                "confirmed_at": now.isoformat(),
                "source": source,
                "read_receipt_id": receipt.receipt_id,
            },
            actor_user_id=user_id,
        )
        return receipt

    def get_read_receipt(
        self, user_id: str, document_id: str, version: int
    ) -> DocumentReadReceipt | None:
        if self._repository is None:
            return None
        return self._repository.get_read_receipt(user_id, document_id, version)

    # --- Workflow comments ---

    def _comment_repo(self):
        from .comment_sqlite_repository import SQLiteWorkflowCommentRepository

        if self._repository is None or not hasattr(self._repository, "upsert_workflow_comment"):
            raise ValidationError("workflow comment repository is not available")
        return SQLiteWorkflowCommentRepository(self._repository)  # type: ignore[arg-type]

    def list_workflow_comments(
        self,
        state: DocumentVersionState,
        *,
        context: WorkflowCommentContext,
        actor_user_id: str,
        actor_role: SystemRole,
    ) -> list[WorkflowCommentListItem]:
        from .comment_service import WorkflowCommentService

        _ = actor_user_id, actor_role
        return WorkflowCommentService(repository=self._comment_repo(), event_bus=self._event_bus).list_comments(
            state, context=context
        )

    def get_workflow_comment_detail(
        self, comment_id: str, *, actor_user_id: str, actor_role: SystemRole
    ) -> WorkflowCommentDetail:
        from .comment_service import WorkflowCommentService

        _ = actor_user_id, actor_role
        return WorkflowCommentService(repository=self._comment_repo(), event_bus=self._event_bus).get_detail(comment_id)

    def sync_docx_comments(
        self, state: DocumentVersionState, *, actor_user_id: str, actor_role: SystemRole
    ) -> list[WorkflowCommentListItem]:
        from .comment_extractors.docx_comment_reader import DocxCommentReader
        from .comment_sync_service import CommentSyncService

        _ = actor_role
        source_docx = self._resolve_source_docx_artifact_path(state)
        if source_docx is None:
            return []
        return CommentSyncService(
            comment_repository=self._comment_repo(),
            docx_comment_reader=DocxCommentReader(),
            event_bus=self._event_bus,
        ).sync_docx_comments(state, docx_path=source_docx, actor_user_id=actor_user_id)

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
        from .comment_service import WorkflowCommentService

        return WorkflowCommentService(repository=self._comment_repo(), event_bus=self._event_bus).create_pdf_comment(
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
        from .comment_service import WorkflowCommentService

        _ = actor_role
        return WorkflowCommentService(repository=self._comment_repo(), event_bus=self._event_bus).set_status(
            comment_id, new_status=new_status, actor_user_id=actor_user_id, note=note
        )

    # --- Tracked read flow ---

    def _tracking_service(self):
        from .pdf_read_tracking_service import PdfReadTrackingService

        if self._repository is None:
            raise ValidationError("repository is required")
        return PdfReadTrackingService(self._repository, event_bus=self._event_bus)

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
        return self._tracking_service().start(
            user_id=user_id,
            document_id=document_id,
            version=version,
            artifact_id=artifact_id,
            total_pages=total_pages,
            source=source,
            min_seconds_per_page=min_seconds_per_page,
        )

    def record_page_dwell(self, session_id: str, *, page_number: int, dwell_seconds: int) -> PdfReadProgress:
        return self._tracking_service().record_page_dwell(
            session_id, page_number=page_number, dwell_seconds=dwell_seconds
        )

    def get_pdf_read_progress(self, session_id: str) -> PdfReadProgress:
        return self._tracking_service().get_progress(session_id)

    def finalize_tracked_pdf_read(self, session_id: str, *, source: str) -> DocumentReadReceipt | None:
        return self._tracking_service().finalize(session_id, source=source)

