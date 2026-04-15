from __future__ import annotations

import re
import shutil
import tempfile
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from modules.signature.errors import SignatureError
from qm_platform.events.event_envelope import EventEnvelope

from .contracts import (
    ArtifactSourceType,
    ArtifactType,
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentStatus,
    DocumentTaskItem,
    DocumentType,
    DocumentVersionState,
    RecentDocumentItem,
    RejectionReason,
    ReleasedDocumentItem,
    ReviewActionItem,
    SystemRole,
    WorkflowAssignments,
    WorkflowProfile,
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
    _FORBIDDEN_CUSTOM_FIELD_KEYS = {
        "status",
        "released_at",
        "approval_completed_at",
        "approval_completed_by",
        "review_completed_at",
        "review_completed_by",
        "document_id",
        "version",
        "archive",
        "assignments",
        "workflow_profile",
        "workflow_profile_id",
        "doc_type",
        "control_class",
        "register_state",
        "active_version",
    }
    _FORBIDDEN_CUSTOM_FIELD_PREFIXES = (
        "status.",
        "assignments.",
        "workflow.",
        "registry.",
    )
    _ALLOWED_CUSTOM_FIELD_KEY_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")

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

    def _emit_audit(self, *, action: str, actor: str, target: str, result: str, reason: str = "") -> None:
        if self._audit_logger is None:
            return
        emit = getattr(self._audit_logger, "emit", None)
        if not callable(emit):
            return
        emit(action=action, actor=actor, target=target, result=result, reason=reason)

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

    def _resolve_source_pdf_artifact_path(self, state: DocumentVersionState) -> Path | None:
        if self._repository is None:
            return None
        artifacts = self._repository.list_artifacts(state.document_id, state.version)
        for artifact in sorted(artifacts, key=lambda item: 0 if item.is_current else 1):
            if artifact.artifact_type != ArtifactType.SOURCE_PDF:
                continue
            resolved = self._resolve_artifact_path(artifact)
            if resolved is not None and resolved.exists() and resolved.suffix.lower() == ".pdf":
                return resolved
        return None

    def _resolve_source_docx_artifact_path(self, state: DocumentVersionState) -> Path | None:
        if self._repository is None:
            return None
        artifacts = self._repository.list_artifacts(state.document_id, state.version)
        for artifact in sorted(artifacts, key=lambda item: 0 if item.is_current else 1):
            if artifact.artifact_type != ArtifactType.SOURCE_DOCX:
                continue
            resolved = self._resolve_artifact_path(artifact)
            if resolved is not None and resolved.exists() and resolved.suffix.lower() == ".docx":
                return resolved
        return None

    def _convert_docx_to_temp_pdf_for_workflow(self, state: DocumentVersionState, source_docx: Path) -> Path:
        output_name = f"{state.document_id}_{state.version}_source.pdf"
        with tempfile.TemporaryDirectory(prefix="qmtool-docx2pdf-") as tmp_dir:
            out_path = Path(tmp_dir) / output_name
            try:
                if self._docx_to_pdf_converter is not None:
                    self._docx_to_pdf_converter(source_docx, out_path)
                else:
                    try:
                        from docx2pdf import convert
                    except ImportError as exc:
                        raise ValidationError(
                            "docx2pdf is required to convert SOURCE_DOCX before editing completion"
                        ) from exc
                    convert(str(source_docx), str(out_path))
                if not out_path.exists() or out_path.stat().st_size == 0:
                    raise ValidationError(f"docx to pdf conversion produced no output: {source_docx}")
                persisted = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}_source.pdf"
                shutil.copy2(out_path, persisted)
                return persisted
            except Exception as exc:
                if isinstance(exc, ValidationError):
                    raise
                raise ValidationError(f"docx to pdf conversion failed: {exc}") from exc

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
            created_at=existing.created_at,
            updated_at=_utcnow(),
        )
        self._repository.upsert_header(updated)
        return updated

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
            document_id,
            version,
            owner_user_id=actor_user_id,
            doc_type=DocumentType.EXT,
            control_class=ControlClass.EXTERNAL,
            workflow_profile_id="external_control",
        )
        self._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        artifact = self._create_artifact(
            state=state,
            source_path=source_path,
            artifact_type=ArtifactType.SOURCE_PDF,
            source_type=ArtifactSourceType.IMPORT_PDF,
            metadata={"intake_mode": "import_pdf"},
        )
        event = self._publish(
            "domain.documents.artifact.imported.v1",
            state,
            {"artifact_id": artifact.artifact_id},
            actor_user_id=actor_user_id,
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
            document_id,
            version,
            owner_user_id=actor_user_id,
            doc_type=DocumentType.OTHER,
            control_class=ControlClass.CONTROLLED,
            workflow_profile_id="long_release",
        )
        self._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        artifact = self._create_artifact(
            state=state,
            source_path=source_path,
            artifact_type=ArtifactType.SOURCE_DOCX,
            source_type=ArtifactSourceType.IMPORT_DOCX,
            metadata={"intake_mode": "import_docx"},
        )
        event = self._publish(
            "domain.documents.artifact.imported.v1",
            state,
            {"artifact_id": artifact.artifact_id},
            actor_user_id=actor_user_id,
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
            document_id,
            version,
            owner_user_id=actor_user_id,
            doc_type=DocumentType.OTHER,
            control_class=ControlClass.CONTROLLED,
            workflow_profile_id="long_release",
        )
        self._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        source_type = (
            ArtifactSourceType.TEMPLATE_DOTX if template_path.suffix.lower() == ".dotx" else ArtifactSourceType.TEMPLATE_DOCT
        )
        artifact = self._create_artifact(
            state=state,
            source_path=template_path,
            artifact_type=ArtifactType.SOURCE_DOCX,
            source_type=source_type,
            metadata={"intake_mode": "create_from_template"},
        )
        event = self._publish(
            "domain.documents.template.created.v1",
            state,
            {"artifact_id": artifact.artifact_id},
            actor_user_id=actor_user_id,
        )
        self._sync_registry(state, event)
        return state

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
        return self._workflow_use_cases.assign_workflow_roles(
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
        return self._workflow_use_cases.start_workflow(
            state,
            profile,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def complete_editing(
        self,
        state: DocumentVersionState,
        *,
        sign_request: object | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._workflow_use_cases.complete_editing(
            state,
            sign_request=sign_request,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def accept_review(self, state: DocumentVersionState, actor_user_id: str, actor_role: SystemRole | None = None) -> DocumentVersionState:
        return self._workflow_use_cases.accept_review(state, actor_user_id, actor_role=actor_role)

    def reject_review(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        reason: RejectionReason,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._workflow_use_cases.reject_review(state, actor_user_id, reason, actor_role=actor_role)

    def accept_approval(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        *,
        sign_request: object | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._workflow_use_cases.accept_approval(
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
        return self._workflow_use_cases.reject_approval(state, actor_user_id, reason, actor_role=actor_role)

    def abort_workflow(
        self,
        state: DocumentVersionState,
        *,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        return self._workflow_use_cases.abort_workflow(
            state,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

    def archive_approved(
        self,
        state: DocumentVersionState,
        actor_role: SystemRole,
        actor_user_id: str | None = None,
    ) -> DocumentVersionState:
        return self._workflow_use_cases.archive_approved(state, actor_role, actor_user_id=actor_user_id)

    def extend_annual_validity(
        self,
        state: DocumentVersionState,
        *,
        signature_present: bool,
    ) -> tuple[DocumentVersionState, bool]:
        return self._workflow_use_cases.extend_annual_validity(state, signature_present=signature_present)

    def create_new_version_after_archive(self, state: DocumentVersionState, next_version: int) -> DocumentVersionState:
        return self._workflow_use_cases.create_new_version_after_archive(state, next_version)

    def ensure_source_pdf_for_signing(
        self,
        state: DocumentVersionState,
        *,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> Path | None:
        if actor_user_id is not None and actor_role is not None:
            self._ensure_editor_or_owner_or_privileged(state, actor_user_id, actor_role)
        return self._ensure_source_pdf_artifact_for_signing(state, actor_user_id=actor_user_id)

    def _ensure_release_pdf_artifact(self, state: DocumentVersionState) -> None:
        if self._repository is None or self._storage_port is None:
            return
        source_path = self._resolve_release_pdf_source_path(state)
        if source_path is None or not source_path.exists():
            return
        generated_name = self._build_released_filename(state)
        with tempfile.TemporaryDirectory(prefix="qmtool-release-") as tmp_dir:
            staged_path = Path(tmp_dir) / generated_name
            self._protect_pdf_copy(source_path, staged_path)
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

    def _resolve_release_pdf_source_path(self, state: DocumentVersionState) -> Path | None:
        assert self._repository is not None
        artifacts = self._repository.list_artifacts(state.document_id, state.version)
        priorities = [ArtifactType.RELEASED_PDF, ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF]
        for artifact_type in priorities:
            for artifact in artifacts:
                if artifact.artifact_type != artifact_type:
                    continue
                resolved = self._resolve_artifact_path(artifact)
                if resolved is not None and resolved.exists() and resolved.suffix.lower() == ".pdf":
                    return resolved
        return None

    def _resolve_artifact_path(self, artifact: DocumentArtifact) -> Path | None:
        for key in ("absolute_path", "file_path", "path"):
            value = artifact.metadata.get(key)
            if value:
                candidate = Path(value)
                if candidate.exists():
                    return candidate
        root = getattr(self._storage_port, "_root_path", None)
        if isinstance(root, Path):
            return root / artifact.storage_key
        return None

    @staticmethod
    def _build_released_filename(state: DocumentVersionState) -> str:
        title = DocumentsService._transliterate_umlauts((state.title or "").strip().replace(" ", "_"))
        safe_title = "".join(ch for ch in title if ch.isalnum() or ch in ("_", "-")).strip("_-")
        if not safe_title:
            safe_title = "Dokument"
        return f"{state.document_id}_{safe_title}.pdf"

    @staticmethod
    def _transliterate_umlauts(raw: str) -> str:
        return (
            raw.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("Ä", "Ae")
            .replace("Ö", "Oe")
            .replace("Ü", "Ue")
            .replace("ß", "ss")
        )

    @staticmethod
    def _protect_pdf_copy(source_path: Path, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from pypdf import PdfReader, PdfWriter
            from pypdf.constants import UserAccessPermissions

            reader = PdfReader(str(source_path))
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(
                user_password="",
                owner_password=uuid.uuid4().hex,
                permissions_flag=UserAccessPermissions.PRINT,
            )
            with target_path.open("wb") as fh:
                writer.write(fh)
        except Exception:
            shutil.copy2(source_path, target_path)

    def _store_state(self, state: DocumentVersionState) -> None:
        self._assert_state_invariants(state)
        self._states[(state.document_id, state.version)] = state
        if self._repository is not None:
            self._repository.upsert(state)

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
        self,
        document_id: str,
        version: int,
        owner_user_id: str | None = None,
        *,
        doc_type: DocumentType = DocumentType.OTHER,
        control_class: ControlClass | None = None,
        workflow_profile_id: str = "long_release",
    ) -> DocumentVersionState:
        state = self.get_document_version(document_id, version)
        if state is not None:
            return state
        return self.create_document_version(
            document_id,
            version,
            owner_user_id=owner_user_id,
            doc_type=doc_type,
            control_class=control_class,
            workflow_profile_id=workflow_profile_id,
            title=document_id,
        )

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
        stored = self._storage_port.store_file_copy(
            source_path=source_path,
            document_id=state.document_id,
            version=state.version,
            artifact_type=artifact_type.value,
        )
        artifact = DocumentArtifact(
            artifact_id=uuid.uuid4().hex,
            document_id=state.document_id,
            version=state.version,
            artifact_type=artifact_type,
            source_type=source_type,
            storage_key=stored.storage_key,
            original_filename=source_path.name,
            mime_type=stored.mime_type,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            is_current=True,
            metadata=metadata,
            created_at=_utcnow(),
        )
        self._repository.add_artifact(artifact)
        self._repository.mark_current_artifact(
            document_id=state.document_id,
            version=state.version,
            artifact_type=artifact_type,
            artifact_id=artifact.artifact_id,
        )
        return artifact

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

    @staticmethod
    def _validate_source_file(source_path: Path, *, allowed_suffixes: set[str]) -> None:
        if not source_path.exists():
            raise ValidationError(f"source file not found: {source_path}")
        suffix = source_path.suffix.lower()
        if suffix not in allowed_suffixes:
            raise ValidationError(f"invalid source file extension '{suffix}', allowed: {sorted(allowed_suffixes)}")

    def _next_status_from_profile(self, profile: WorkflowProfile | None, current: DocumentStatus) -> DocumentStatus:
        if profile is None:
            raise ValidationError("workflow profile is required")
        try:
            idx = profile.phases.index(current)
        except ValueError as exc:
            raise ValidationError(f"profile does not contain current status {current.value}") from exc
        if idx >= len(profile.phases) - 1:
            raise InvalidTransitionError("current status is already terminal in profile")
        return profile.phases[idx + 1]

    @staticmethod
    def _assert_profile(profile: WorkflowProfile) -> None:
        if not profile.phases:
            raise ValidationError("workflow profile requires at least one phase")
        if profile.phases[0] != DocumentStatus.IN_PROGRESS:
            raise ValidationError("workflow profile must start with IN_PROGRESS")
        if profile.phases[-1] != DocumentStatus.APPROVED:
            raise ValidationError("workflow profile must end with APPROVED")

    @staticmethod
    def _assert_rejection_reason(reason: RejectionReason) -> None:
        if not reason.is_valid():
            raise ValidationError("rejection reason requires template text and/or free text")

    @staticmethod
    def _assert_active_profile(state: DocumentVersionState) -> None:
        if not state.workflow_active:
            raise InvalidTransitionError("workflow is not active")
        if state.workflow_profile is None:
            raise ValidationError("workflow profile is missing")

    @staticmethod
    def _assert_assignments_for_profile(state: DocumentVersionState, profile: WorkflowProfile) -> None:
        if profile.requires_editors and not state.assignments.editors:
            raise ValidationError("workflow-start requires at least one editor for this profile")
        if profile.requires_reviewers and not state.assignments.reviewers:
            raise ValidationError("workflow-start requires at least one reviewer for this profile")
        if profile.requires_approvers and not state.assignments.approvers:
            raise ValidationError("workflow-start requires at least one approver for this profile")
        if state.control_class == ControlClass.EXTERNAL and (
            state.assignments.editors or state.assignments.reviewers or state.assignments.approvers
        ):
            raise ValidationError("external documents must not have internal workflow assignments")

    @staticmethod
    def _ensure_owner_or_privileged(state: DocumentVersionState, actor_user_id: str, actor_role: SystemRole) -> None:
        if actor_role in (SystemRole.ADMIN, SystemRole.QMB):
            return
        if state.owner_user_id == actor_user_id:
            return
        raise PermissionDeniedError("only owner, QMB, or ADMIN may execute this action")

    @staticmethod
    def _ensure_editor_or_owner_or_privileged(state: DocumentVersionState, actor_user_id: str, actor_role: SystemRole) -> None:
        if actor_role in (SystemRole.ADMIN, SystemRole.QMB):
            return
        if state.owner_user_id == actor_user_id:
            return
        if actor_user_id in state.assignments.editors:
            return
        raise PermissionDeniedError("only assigned editors, owner, QMB, or ADMIN may complete editing")

    def _enforce_signature_transition(
        self,
        state: DocumentVersionState,
        transition: str,
        sign_request: object | None,
    ) -> None:
        profile = state.workflow_profile
        if profile is None:
            raise ValidationError("workflow profile is missing")
        if transition not in profile.signature_required_transitions:
            return
        if self._signature_api is None:
            raise ValidationError(f"signature_api missing for required transition '{transition}'")
        if sign_request is None:
            raise ValidationError(f"signature request required for transition '{transition}'")
        sign = getattr(self._signature_api, "sign_with_fixed_position", None)
        if not callable(sign):
            raise ValidationError("signature_api does not provide sign_with_fixed_position")
        try:
            sign(sign_request)
        except SignatureError as exc:
            raise ValidationError(f"signature step failed: {exc}") from exc
        output_pdf = getattr(sign_request, "output_pdf", None)
        if (
            self._repository is not None
            and self._storage_port is not None
            and isinstance(output_pdf, Path)
            and output_pdf.exists()
            and output_pdf.suffix.lower() == ".pdf"
        ):
            self._create_artifact(
                state=state,
                source_path=output_pdf,
                artifact_type=ArtifactType.SIGNED_PDF,
                source_type=ArtifactSourceType.GENERATED,
                metadata={
                    "transition": transition,
                    "generated_from": str(getattr(sign_request, "input_pdf", "")),
                },
            )

    @staticmethod
    def _is_signature_required(state: DocumentVersionState, transition: str) -> bool:
        profile = state.workflow_profile
        if profile is None:
            return False
        return transition in profile.signature_required_transitions

    @staticmethod
    def _assert_custom_fields_safe(custom_fields: dict[str, object]) -> None:
        overlap = DocumentsService._FORBIDDEN_CUSTOM_FIELD_KEYS.intersection(custom_fields.keys())
        if overlap:
            raise ValidationError(f"custom fields must not override steering fields: {sorted(overlap)}")
        for key, value in custom_fields.items():
            if not DocumentsService._ALLOWED_CUSTOM_FIELD_KEY_RE.match(key):
                raise ValidationError(f"custom field key '{key}' is invalid")
            if any(key.startswith(prefix) for prefix in DocumentsService._FORBIDDEN_CUSTOM_FIELD_PREFIXES):
                raise ValidationError(f"custom field key '{key}' uses forbidden steering prefix")
            DocumentsService._assert_custom_field_value_safe(value, key)

    @staticmethod
    def _assert_custom_field_value_safe(value: object, key: str) -> None:
        if value is None or isinstance(value, (str, int, float, bool)):
            return
        if isinstance(value, list):
            for item in value:
                DocumentsService._assert_custom_field_value_safe(item, key)
            return
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if not isinstance(nested_key, str):
                    raise ValidationError(f"custom field '{key}' contains non-string nested key")
                DocumentsService._assert_custom_field_value_safe(nested_value, key)
            return
        raise ValidationError(f"custom field '{key}' contains unsupported value type '{type(value).__name__}'")

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
        if actor_role == SystemRole.ADMIN:
            return
        if actor_role == SystemRole.USER:
            if state.owner_user_id != actor_user_id:
                raise PermissionDeniedError("owner required for role updates")
            if state.edit_signature_done:
                raise PermissionDeniedError("owner cannot update roles after first edit signature")
            return
        if actor_role == SystemRole.QMB:
            if state.status in (DocumentStatus.IN_REVIEW, DocumentStatus.IN_APPROVAL, DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
                if new_editors != state.assignments.editors:
                    raise PermissionDeniedError("QMB cannot change editor roles after review phase started")
            if state.status in (DocumentStatus.IN_APPROVAL, DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
                if new_reviewers != state.assignments.reviewers:
                    raise PermissionDeniedError("QMB cannot change reviewer roles after approval phase started")
            if state.status in (DocumentStatus.APPROVED, DocumentStatus.ARCHIVED):
                if new_approvers != state.assignments.approvers:
                    raise PermissionDeniedError("QMB cannot change approver roles after approval completed")
            return
        raise PermissionDeniedError("unsupported role for role updates")

    def _publish(
        self,
        name: str,
        state: DocumentVersionState,
        payload: dict[str, object],
        *,
        actor_user_id: str | None = None,
    ) -> EventEnvelope | None:
        envelope = EventEnvelope.create(
            name=name,
            module_id="documents",
            actor_user_id=actor_user_id,
            payload={"document_id": state.document_id, "version": state.version, **payload},
        )
        if self._event_bus is None:
            return envelope
        publish = getattr(self._event_bus, "publish", None)
        if not callable(publish):
            return envelope
        publish(envelope)
        return envelope

    def _sync_registry(self, state: DocumentVersionState, event: EventEnvelope | None) -> None:
        if self._registry_projection_api is None:
            return
        apply = getattr(self._registry_projection_api, "apply_documents_projection", None)
        if not callable(apply):
            return
        release_mode = state.workflow_profile.release_evidence_mode if state.workflow_profile is not None else "WORKFLOW"
        apply(
            source_module_id="documents",
            document_id=state.document_id,
            version=state.version,
            status=state.status.value,
            release_evidence_mode=release_mode,
            valid_from=state.valid_from,
            valid_until=state.valid_until,
            event=event,
        )

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

    @staticmethod
    def _assert_state_invariants(state: DocumentVersionState) -> None:
        if state.extension_count < 0 or state.extension_count > 3:
            raise ValidationError("extension_count must be between 0 and 3")
        if state.status not in (DocumentStatus.APPROVED, DocumentStatus.ARCHIVED) and state.extension_count != 0:
            raise ValidationError("extension_count may only be > 0 for APPROVED or ARCHIVED status")
        if state.review_completed_at is not None and state.review_completed_by is None:
            raise ValidationError("review_completed_by must be set when review_completed_at is set")
        if state.approval_completed_at is not None and state.approval_completed_by is None:
            raise ValidationError("approval_completed_by must be set when approval_completed_at is set")
        if state.released_at is not None and state.approval_completed_at is None:
            raise ValidationError("released_at requires approval_completed_at")
        if state.archived_at is not None and state.status != DocumentStatus.ARCHIVED:
            raise ValidationError("archived_at may only be set for ARCHIVED status")
        if state.status != DocumentStatus.ARCHIVED and state.archived_by is not None:
            raise ValidationError("archived_by may only be set for ARCHIVED status")
        if state.valid_from and state.valid_until and state.valid_until < state.valid_from:
            raise ValidationError("valid_until must be greater than or equal to valid_from")
        if state.valid_from and state.next_review_at and state.next_review_at < state.valid_from:
            raise ValidationError("next_review_at must be greater than or equal to valid_from")

    def _assert_workflow_profile_update_allowed(
        self,
        document_id: str,
        control_class: ControlClass,
        workflow_profile_id: str,
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

