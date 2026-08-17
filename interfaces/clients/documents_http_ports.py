"""Register documents ports backed by HTTP (desktop/CLI - no local documents.db)."""
from __future__ import annotations

from pathlib import Path

from interfaces.clients.documents_http import DocumentsBackendTransportError, DocumentsHttpClient
from modules.documents.api import (
    ArtifactType,
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentStatus,
    DocumentTaskItem,
    DocumentVersionState,
    OpenableArtifactRef,
    RecentDocumentItem,
    ReleasedDocumentItem,
    ReviewActionItem,
    RejectionReason,
    DocumentsFeatureUnavailableError,
    WorkflowCommentContext,
    WorkflowCommentDetail,
    WorkflowCommentListItem,
    WorkflowCommentRecord,
    WorkflowCommentStatus,
)
from modules.documents.api import DocumentType, WorkflowCommentSourceKind
from datetime import datetime


def _feature_unavailable(message: str) -> DocumentsFeatureUnavailableError:
    return DocumentsFeatureUnavailableError(message)


def _comment_list_item(row: dict[str, object]) -> WorkflowCommentListItem:
    updated_raw = row.get("updated_at") or row.get("etag")
    if updated_raw is None:
        raise ValueError("workflow comment list item missing updated_at")
    return WorkflowCommentListItem(
        comment_id=str(row["comment_id"]),
        ref_no=str(row["ref_no"]),
        document_id=str(row["document_id"]),
        version=int(row["version"]),
        context=WorkflowCommentContext(str(row["context"])),
        page_number=int(row["page_number"]) if row.get("page_number") is not None else None,
        anchor_json=str(row["anchor_json"]) if row.get("anchor_json") is not None else None,
        author_display=str(row["author_display"]) if row.get("author_display") is not None else None,
        created_at=datetime.fromisoformat(str(row["created_at"])) if row.get("created_at") else None,
        preview_text=str(row.get("preview_text") or ""),
        status=WorkflowCommentStatus(str(row["status"])),
        updated_at=datetime.fromisoformat(str(updated_raw)),
    )


def _comment_detail(row: dict[str, object]) -> WorkflowCommentDetail:
    return WorkflowCommentDetail(
        comment_id=str(row["comment_id"]),
        ref_no=str(row["ref_no"]),
        document_id=str(row["document_id"]),
        version=int(row["version"]),
        context=WorkflowCommentContext(str(row["context"])),
        page_number=int(row["page_number"]) if row.get("page_number") is not None else None,
        author_display=str(row["author_display"]) if row.get("author_display") is not None else None,
        created_at=datetime.fromisoformat(str(row["created_at"])) if row.get("created_at") else None,
        full_text=str(row.get("full_text") or ""),
        status=WorkflowCommentStatus(str(row["status"])),
        status_note=str(row["status_note"]) if row.get("status_note") is not None else None,
        source_kind=WorkflowCommentSourceKind(str(row["source_kind"])),
    )


def _require_iso_datetime(row: dict[str, object], key: str) -> datetime:
    raw = row.get(key)
    if raw is None or not str(raw).strip():
        raise ValueError(f"invalid documents comment response: missing {key}")
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError as exc:
        raise ValueError(f"invalid documents comment response: invalid {key}") from exc


def _comment_record(row: dict[str, object]) -> WorkflowCommentRecord:
    return WorkflowCommentRecord(
        comment_id=str(row["comment_id"]),
        ref_no=str(row["ref_no"]),
        document_id=str(row["document_id"]),
        version=int(row["version"]),
        context=WorkflowCommentContext(str(row["context"])),
        source_kind=WorkflowCommentSourceKind(str(row.get("source_kind") or "PDF_APP")),
        source_comment_key=str(row.get("source_comment_key") or row["comment_id"]),
        artifact_id=str(row["artifact_id"]) if row.get("artifact_id") is not None else None,
        page_number=int(row["page_number"]) if row.get("page_number") is not None else None,
        anchor_json=str(row["anchor_json"]) if row.get("anchor_json") is not None else None,
        author_display=str(row["author_display"]) if row.get("author_display") is not None else None,
        source_created_at=None,
        preview_text=str(row.get("preview_text") or ""),
        full_text=str(row.get("full_text") or row.get("preview_text") or ""),
        status=WorkflowCommentStatus(str(row["status"])),
        status_note=None,
        status_changed_by=None,
        status_changed_at=None,
        created_at=(
            _require_iso_datetime(row, "created_at")
            if row.get("created_at") is not None and str(row.get("created_at")).strip()
            else _require_iso_datetime(row, "updated_at")
        ),
        updated_at=_require_iso_datetime(row, "updated_at"),
    )


class HttpDocumentsCommentsApi:
    def _client(self) -> DocumentsHttpClient:
        return DocumentsHttpClient.for_runtime()

    def list_workflow_comments(self, state, *, context, actor_user_id=None, actor_role=None, actor=None):
        del actor_user_id, actor_role, actor
        rows = self._client().list_workflow_comments(
            state,
            context=getattr(context, "value", context),
        )
        return [_comment_list_item(row) for row in rows]

    def get_workflow_comment_detail(self, comment_id: str, *, actor_user_id=None, actor_role=None, actor=None):
        del actor_user_id, actor_role, actor
        return _comment_detail(self._client().get_workflow_comment_detail(comment_id))

    def sync_docx_comments(self, state, *, actor_user_id=None, actor_role=None, actor=None):
        del actor_user_id, actor_role, actor
        rows = self._client().sync_docx_comments(state)
        return [_comment_list_item(row) for row in rows]

    def create_pdf_workflow_comment(
        self,
        state,
        *,
        context,
        actor_user_id=None,
        actor_role=None,
        actor=None,
        page_number: int,
        comment_text: str,
        anchor_json: str | None = None,
    ):
        del actor_user_id, actor_role, actor
        row = self._client().create_pdf_workflow_comment(
            state,
            context=getattr(context, "value", context),
            page_number=page_number,
            comment_text=comment_text,
            anchor_json=anchor_json,
        )
        return _comment_record(row)

    def set_workflow_comment_status(
        self,
        comment_id: str,
        *,
        new_status,
        actor_user_id=None,
        actor_role=None,
        actor=None,
        note: str | None = None,
        expected_updated_at: str | None = None,
    ):
        del actor_user_id, actor_role, actor
        token = str(expected_updated_at or "").strip()
        if not token:
            raise ValueError("expected_updated_at is required for comment status mutation")
        row = self._client().set_workflow_comment_status(
            comment_id,
            new_status=getattr(new_status, "value", new_status),
            note=note,
            if_match=token,
        )
        return _comment_record(row)


class HttpDocumentsArtifactsApi:
    def _client(self) -> DocumentsHttpClient:
        return DocumentsHttpClient.for_runtime()

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        return self._client().list_artifacts(document_id, version)

    def get_artifact_by_id(self, artifact_id: str) -> DocumentArtifact | None:
        return self._client().get_artifact(artifact_id)

    def resolve_artifact_paths(
        self,
        artifact: DocumentArtifact,
        *,
        suffixes: tuple[str, ...] = (),
        existing_only: bool = True,
    ) -> list[OpenableArtifactRef]:
        path = self._client().download_artifact(artifact.artifact_id)
        if suffixes and path.suffix.lower() not in {suffix.lower() for suffix in suffixes}:
            return []
        exists = path.exists()
        if existing_only and not exists:
            return []
        return [
            OpenableArtifactRef(
                artifact_id=artifact.artifact_id,
                document_id=artifact.document_id,
                version=artifact.version,
                artifact_type=artifact.artifact_type,
                path=path,
                is_current=artifact.is_current,
                exists=exists,
            )
        ]

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
        artifacts = self.list_artifacts(document_id, version)
        if current_first:
            artifacts = sorted(artifacts, key=lambda artifact: 0 if artifact.is_current else 1)
        refs: list[OpenableArtifactRef] = []
        for artifact_type in artifact_types:
            for artifact in artifacts:
                if artifact.artifact_type == artifact_type:
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
        transition_key = (transition or "").strip().upper()
        if purpose == "reading":
            types = (ArtifactType.RELEASED_PDF,)
        elif transition_key in {"IN_REVIEW->IN_APPROVAL", "IN_APPROVAL->APPROVED"}:
            types = (ArtifactType.SIGNED_PDF,)
        elif transition_key == "EXTEND_VALIDITY":
            types = (ArtifactType.SIGNED_PDF, ArtifactType.RELEASED_PDF)
        else:
            types = (ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF, ArtifactType.RELEASED_PDF)
        refs = self.get_openable_artifact_refs(
            document_id,
            version,
            artifact_types=types,
            suffixes=(".pdf",),
        )
        return refs[0] if refs else None

    def get_released_pdf_for_reading(self, document_id: str, version: int) -> OpenableArtifactRef | None:
        refs = self.get_openable_artifact_refs(
            document_id,
            version,
            artifact_types=(ArtifactType.RELEASED_PDF,),
            suffixes=(".pdf",),
        )
        return refs[0] if refs else None

    def get_source_docx_for_conversion(self, document_id: str, version: int) -> OpenableArtifactRef | None:
        refs = self.get_openable_artifact_refs(
            document_id,
            version,
            artifact_types=(ArtifactType.SOURCE_DOCX,),
            suffixes=(".docx",),
        )
        return refs[0] if refs else None


class HttpDocumentsPoolApi:
    def _client(self) -> DocumentsHttpClient:
        return DocumentsHttpClient.for_runtime()

    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        return self._client().list_by_status(status)

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        return self._client().list_artifacts(document_id, version)

    def get_document_version(self, document_id: str, version: int) -> DocumentVersionState | None:
        return self._client().get_document_version(document_id, version)

    def get_header(self, document_id: str) -> DocumentHeader | None:
        return self._client().get_header(document_id)

    def list_tasks_for_user(self, user_id: str, role: str, scope: str | None = None) -> list[DocumentTaskItem]:
        del user_id, role
        return self._client().list_tasks(scope=scope)

    def list_review_actions_for_user(self, user_id: str, role: str) -> list[ReviewActionItem]:
        del user_id, role
        return self._client().list_review_actions()

    def list_recent_documents_for_user(self, user_id: str, role: str) -> list[RecentDocumentItem]:
        del user_id, role
        return self._client().list_recent_documents()

    def list_current_released_documents(self) -> list[ReleasedDocumentItem]:
        return self._client().list_released_documents()

    def get_capabilities(self) -> dict[str, bool]:
        return self._client().get_capabilities()


class HttpDocumentsWorkflowApi:
    def _client(self) -> DocumentsHttpClient:
        return DocumentsHttpClient.for_runtime()

    def assign_workflow_roles(self, state, *, editors, reviewers, approvers, actor_user_id=None, actor_role=None, actor=None):
        return self._client().assign_workflow_roles(state, editors=editors, reviewers=reviewers, approvers=approvers)

    def start_workflow(self, state, profile=None, *, profile_id=None, actor_user_id=None, actor_role=None, actor=None):
        return self._client().start_workflow(state, profile_id=profile_id)

    def complete_editing(self, state, *, sign_request=None, actor_user_id=None, actor_role=None, actor=None):
        return self._client().complete_editing(state, sign_intent=sign_request)

    def accept_review(self, state, actor_user_id=None, *, sign_request=None, actor_role=None, actor=None):
        return self._client().accept_review(state, sign_intent=sign_request)

    def reject_review(self, state, reason_or_user=None, reason=None, actor_user_id=None, actor_role=None, actor=None):
        rejection = reason if isinstance(reason, RejectionReason) else reason_or_user
        if not isinstance(rejection, RejectionReason):
            rejection = RejectionReason(template_text=str(rejection))
        return self._client().reject_review(state, rejection)

    def accept_approval(self, state, actor_user_id=None, *, sign_request=None, actor_role=None, actor=None):
        return self._client().accept_approval(state, sign_intent=sign_request)

    def reject_approval(self, state, reason_or_user=None, reason=None, actor_user_id=None, actor_role=None, actor=None):
        rejection = reason if isinstance(reason, RejectionReason) else reason_or_user
        if not isinstance(rejection, RejectionReason):
            rejection = RejectionReason(template_text=str(rejection))
        return self._client().reject_approval(state, rejection)

    def abort_workflow(self, state, *, actor_user_id=None, actor_role=None, actor=None):
        return self._client().abort_workflow(state)

    def create_document_version(self, document_id: str, version: int, **kwargs):
        return self._client().create_document_version(
            document_id,
            version,
            owner_user_id=kwargs.get("owner_user_id"),
            title=kwargs.get("title", ""),
            description=kwargs.get("description"),
            doc_type=getattr(kwargs.get("doc_type"), "value", kwargs.get("doc_type", "OTHER")),
            control_class=getattr(kwargs.get("control_class"), "value", kwargs.get("control_class", "CONTROLLED")),
            workflow_profile_id=kwargs.get("workflow_profile_id"),
        )

    def import_existing_pdf(self, document_id, version, source_path, *, actor_user_id=None, actor_role=None, actor=None):
        client = self._client()
        state = client.get_document_version(document_id, version)
        if state is None:
            raise DocumentsBackendTransportError("document version not found before PDF import")
        return client.import_existing_pdf(state, Path(source_path))

    def list_workflow_profile_definitions(self, *, actor=None, include_inactive=True):
        return self._client().list_workflow_profile_definitions(include_inactive=include_inactive)

    def list_profile_ids_for_control_class(self, control_class: ControlClass) -> list[str]:
        """Derive active profile codes from the public definitions contract only.

        Requires unambiguous profile_code, active_version, control_class, and is_active
        on every returned definition row. Otherwise fail-closed.
        """
        target = getattr(control_class, "value", control_class)
        target_s = str(target).strip()
        if not target_s:
            raise _feature_unavailable(
                "list_profile_ids_for_control_class requires an unambiguous control class"
            )
        rows = self.list_workflow_profile_definitions(include_inactive=False)
        if not isinstance(rows, list):
            raise _feature_unavailable(
                "workflow profile definitions payload is not a list; cannot derive profile ids"
            )
        result: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                raise _feature_unavailable(
                    "workflow profile definition row is ambiguous; cannot derive profile ids"
                )
            profile_code = row.get("profile_code")
            control = row.get("control_class")
            is_active = row.get("is_active")
            active_version = row.get("active_version")
            if (
                profile_code is None
                or control is None
                or is_active is None
                or active_version is None
            ):
                raise _feature_unavailable(
                    "workflow profile definition missing profile_code, control_class, "
                    "is_active, or active_version; cannot derive profile ids"
                )
            code_s = str(profile_code).strip()
            control_s = str(getattr(control, "value", control)).strip()
            if not code_s or not control_s:
                raise _feature_unavailable(
                    "workflow profile definition has empty profile_code or control_class; "
                    "cannot derive profile ids"
                )
            if is_active is not True and is_active != 1:
                raise _feature_unavailable(
                    "active workflow profile definition reported is_active!=true; "
                    "cannot derive profile ids"
                )
            if control_s != target_s:
                continue
            result.append(code_s)
        return sorted(set(result))

    def ensure_source_pdf_for_signing(self, state, *, actor_user_id=None, actor_role=None, actor=None):
        del actor_user_id, actor_role, actor
        return self._client().ensure_source_pdf_for_signing(state)

    def create_workflow_profile_definition(self, payload, *, actor=None, change_reason: str):
        del actor
        return self._client().create_workflow_profile_definition(payload, change_reason=change_reason)

    def create_workflow_profile_version(self, profile_code: str, payload, *, actor=None, change_reason: str):
        del actor
        return self._client().create_workflow_profile_version(profile_code, payload, change_reason=change_reason)

    def activate_workflow_profile_definition(self, profile_code: str, *, actor=None, change_reason: str):
        del actor
        return self._client().activate_workflow_profile_definition(profile_code, change_reason=change_reason)

    def deactivate_workflow_profile_definition(self, profile_code: str, *, actor=None, change_reason: str):
        del actor
        return self._client().deactivate_workflow_profile_definition(profile_code, change_reason=change_reason)

    def bind_document_type_default_profile(self, doc_type, profile_code: str, *, actor=None, change_reason: str):
        del actor
        return self._client().bind_document_type_default_profile(
            getattr(doc_type, "value", doc_type),
            profile_code,
            change_reason=change_reason,
        )

    def list_workflow_profile_versions(self, profile_code: str, *, actor=None):
        del actor
        return self._client().list_workflow_profile_versions(profile_code)

    def import_existing_docx(self, document_id, version, source_path, *, actor_user_id=None, actor_role=None, actor=None):
        client = self._client()
        state = client.get_document_version(document_id, version)
        if state is None:
            raise DocumentsBackendTransportError("document version not found before DOCX import")
        return client.import_existing_docx(state, Path(source_path))

    def create_from_template(self, document_id, version, template_path, *, actor_user_id=None, actor_role=None):
        del actor_user_id, actor_role
        client = self._client()
        state = client.get_document_version(document_id, version)
        return client.create_from_template_for_version(document_id, version, Path(template_path), state=state)

    def archive_approved(self, state, actor_role=None, actor_user_id=None, actor=None):
        del actor_role, actor_user_id, actor
        return self._client().archive_approved(state)

    def extend_annual_validity(
        self,
        state,
        *,
        actor_user_id=None,
        signature_present=None,
        duration_days=None,
        reason=None,
        review_outcome=None,
        sign_intent=None,
    ):
        del actor_user_id, signature_present
        if sign_intent is None:
            raise _feature_unavailable("sign_intent is required for annual validity extension over HTTP")
        return self._client().extend_annual_validity(
            state,
            duration_days=int(duration_days or 0),
            reason=str(reason or ""),
            review_outcome=getattr(review_outcome, "value", review_outcome),
            sign_intent=sign_intent,
        )

    def update_document_header(self, document_id: str, **kwargs):
        unsupported = {"doc_type", "control_class"} & set(kwargs)
        if unsupported:
            raise TypeError(f"unsupported header update fields: {sorted(unsupported)}")
        allowed = {
            "workflow_profile_id",
            "department",
            "site",
            "regulatory_scope",
            "distribution_roles",
            "distribution_sites",
            "distribution_departments",
            "if_match",
            "actor_user_id",
            "actor_role",
            "actor",
        }
        unknown = set(kwargs) - allowed
        if unknown:
            raise TypeError(f"unsupported header update fields: {sorted(unknown)}")
        for discarded in ("actor_user_id", "actor_role", "actor"):
            kwargs.pop(discarded, None)
        return self._client().update_document_header(
            document_id,
            workflow_profile_id=kwargs.get("workflow_profile_id"),
            department=kwargs.get("department"),
            site=kwargs.get("site"),
            regulatory_scope=kwargs.get("regulatory_scope"),
            distribution_roles=kwargs.get("distribution_roles"),
            distribution_sites=kwargs.get("distribution_sites"),
            distribution_departments=kwargs.get("distribution_departments"),
            if_match=kwargs.get("if_match"),
        )

    def update_version_metadata(self, state, **kwargs):
        return self._client().update_version_metadata(
            state,
            title=kwargs.get("title"),
            description=kwargs.get("description"),
            valid_until=kwargs.get("valid_until"),
            next_review_at=kwargs.get("next_review_at"),
            custom_fields=kwargs.get("custom_fields"),
        )

    def add_change_request(self, state, **kwargs):
        return self._client().add_change_request(
            state,
            change_id=str(kwargs.get("change_id") or ""),
            reason=str(kwargs.get("reason") or ""),
            impact_refs=list(kwargs.get("impact_refs") or []),
        )

    def list_change_requests(self, state):
        return self._client().list_change_requests(state)

    def create_new_version_after_archive(self, state, next_version: int, **kwargs):
        del kwargs
        return self._client().create_new_version_after_archive(state, int(next_version))


class HttpDocumentsReadApi:
    def _client(self) -> DocumentsHttpClient:
        return DocumentsHttpClient.for_runtime()

    def open_released_document_for_training(self, user_id: str, document_id: str, version: int):
        del user_id
        return self._client().open_released_document(document_id, version)

    def confirm_released_document_read(
        self, user_id: str, document_id: str, version: int, *, source: str
    ):
        del user_id
        return self._client().confirm_released_document_read(document_id, version, source=source)

    def get_read_receipt(self, user_id: str, document_id: str, version: int):
        del user_id
        return self._client().get_read_receipt(document_id, version)

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
    ):
        del user_id
        return self._client().start_tracked_pdf_read(
            document_id,
            version,
            artifact_id=artifact_id,
            total_pages=total_pages,
            source=source,
            min_seconds_per_page=min_seconds_per_page,
        )

    def record_page_dwell(self, session_id: str, *, page_number: int, dwell_seconds: int):
        return self._client().record_page_dwell(
            session_id, page_number=page_number, dwell_seconds=dwell_seconds
        )

    def get_pdf_read_progress(self, session_id: str):
        return self._client().get_pdf_read_progress(session_id)

    def finalize_tracked_pdf_read(self, session_id: str, *, source: str):
        return self._client().finalize_tracked_pdf_read(session_id, source=source)


def register_documents_http_ports(container) -> None:
    container.register_port("documents_pool_api", HttpDocumentsPoolApi())
    container.register_port("documents_workflow_api", HttpDocumentsWorkflowApi())
    container.register_port("documents_read_api", HttpDocumentsReadApi())
    container.register_port("documents_comments_api", HttpDocumentsCommentsApi())
    container.register_port("documents_artifacts_api", HttpDocumentsArtifactsApi())
