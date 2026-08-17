"""Documents HTTP transport (J04-M0). Calls ``modules.documents.api`` only."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from io import BytesIO
from urllib.parse import quote

from modules.documents.api import (
    ArtifactType,
    ControlClass,
    DocumentConflictError,
    HeaderConflictError,
    CommentConflictError,
    DocumentStatus,
    DocumentType,
    DocumentWorkflowError,
    DocumentsFeatureUnavailableError,
    PermissionDeniedError,
    RejectionReason,
    ValidationError,
    docx_conversion_available,
    ValidityExtensionOutcome,
    WorkflowCommentContext,
    WorkflowCommentDetail,
    WorkflowCommentListItem,
    WorkflowCommentRecord,
    WorkflowCommentStatus,
    actor_user_and_role,
    available_actions_for_actor,
    artifact_to_public_payload,
    compute_global_capabilities,
    document_version_state_to_payload,
)
from modules.usermanagement.api import UserContext

from src.backend.auth_dependencies import get_container, require_user_context_normal

router = APIRouter(prefix="/documents", tags=["documents"])
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


class VersionStateResponse(BaseModel):
    state: dict[str, Any]
    available_actions: list[str]
    etag: str


class AssignRolesBody(BaseModel):
    editors: list[str] = Field(default_factory=list)
    reviewers: list[str] = Field(default_factory=list)
    approvers: list[str] = Field(default_factory=list)


class RejectBody(BaseModel):
    template_id: str | None = None
    template_text: str | None = None
    free_text: str | None = None


class ProfileDefinitionBody(BaseModel):
    payload: dict[str, object]
    change_reason: str


class ProfileCodeBody(BaseModel):
    change_reason: str


class BindDocTypeBody(BaseModel):
    doc_type: str
    profile_code: str
    change_reason: str


class CreateVersionBody(BaseModel):
    document_id: str
    version: int
    owner_user_id: str | None = None
    title: str = ""
    description: str | None = None
    doc_type: str = DocumentType.OTHER.value
    control_class: str = ControlClass.CONTROLLED.value
    workflow_profile_id: str | None = None


class StartWorkflowBody(BaseModel):
    profile_id: str | None = None


class MetadataBody(BaseModel):
    title: str | None = None
    description: str | None = None
    valid_until: str | None = None
    next_review_at: str | None = None
    custom_fields: dict[str, object] | None = None


class ChangeRequestBody(BaseModel):
    change_id: str
    reason: str
    impact_refs: list[str] = Field(default_factory=list)


class ReadDocumentBody(BaseModel):
    document_id: str
    version: int
    source: str = "training"


class StartTrackedReadBody(ReadDocumentBody):
    artifact_id: str | None = None
    total_pages: int
    min_seconds_per_page: int = 10


class PageDwellBody(BaseModel):
    page_number: int
    dwell_seconds: int


class FinalizeReadBody(BaseModel):
    source: str = "training_pdf"


class SignIntentBody(BaseModel):
    placement: dict[str, object]
    layout: dict[str, object]
    password: str | None = None
    reason: str | None = None


class WorkflowSignBody(BaseModel):
    sign_intent: SignIntentBody | None = None


class HeaderUpdateBody(BaseModel):
    workflow_profile_id: str | None = None
    department: str | None = None
    site: str | None = None
    regulatory_scope: str | None = None
    distribution_roles: list[str] | None = None
    distribution_sites: list[str] | None = None
    distribution_departments: list[str] | None = None


class CreatePdfCommentBody(BaseModel):
    context: str
    page_number: int
    comment_text: str
    anchor_json: str | None = None


class CommentStatusBody(BaseModel):
    new_status: str
    note: str | None = None


class ExtendAnnualBody(BaseModel):
    duration_days: int
    reason: str
    review_outcome: str = ValidityExtensionOutcome.UNCHANGED.value
    sign_intent: SignIntentBody


class NewVersionAfterArchiveBody(BaseModel):
    next_version: int


class ExtendAnnualResponse(BaseModel):
    state: dict[str, Any]
    available_actions: list[str]
    etag: str
    is_maxed: bool


class EnsureSourcePdfResponse(BaseModel):
    state: dict[str, Any]
    available_actions: list[str]
    etag: str
    artifact_id: str | None = None


def _optional_sign_request(request: Request, state, transition: str, body: WorkflowSignBody | None, actor: UserContext):
    if body is None or body.sign_intent is None:
        profile = getattr(state, "workflow_profile", None)
        if profile and transition in set(profile.signature_required_transitions):
            raise ValidationError(f"signature request required for transition '{transition}'")
        return None
    app_home = Path(get_container(request).get_port("app_home"))
    scratch = app_home / "scratch" / "workflow-sign"
    return _workflow_api(request).build_workflow_sign_request_from_intent(
        state=state,
        transition=transition,
        sign_intent={
            "placement": body.sign_intent.placement,
            "layout": body.sign_intent.layout,
            "password": body.sign_intent.password,
            "reason": body.sign_intent.reason,
        },
        actor=actor,
        signature_api=get_container(request).get_port("signature_api"),
        scratch_root=scratch,
    )


def _map_documents_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HeaderConflictError):
        current = exc.current_header
        etag = current.updated_at.isoformat()
        return HTTPException(
            status_code=409,
            detail={"error": "header_conflict", "message": str(exc), "current_etag": etag},
            headers={"ETag": etag},
        )
    if isinstance(exc, CommentConflictError):
        current = exc.current_comment
        etag = current.updated_at.isoformat()
        return HTTPException(
            status_code=409,
            detail={"error": "comment_conflict", "message": str(exc), "current_etag": etag},
            headers={"ETag": etag},
        )
    if isinstance(exc, DocumentConflictError):
        current = exc.current_state
        etag = _etag_for_state(current)
        return HTTPException(
            status_code=409,
            detail={
                "error": "document_conflict",
                "message": str(exc),
                "current_etag": etag,
                "current_state": document_version_state_to_payload(current),
            },
            headers={"ETag": etag},
        )
    if isinstance(exc, DocumentsFeatureUnavailableError):
        return HTTPException(
            status_code=501,
            detail={"error": "documents_feature_unavailable", "message": str(exc)},
        )
    if isinstance(exc, PermissionDeniedError):
        return HTTPException(status_code=403, detail={"error": "forbidden", "message": str(exc)})
    if isinstance(exc, (DocumentWorkflowError, ValidationError)):
        return HTTPException(status_code=400, detail={"error": "documents_workflow", "message": str(exc)})
    return HTTPException(status_code=500, detail={"error": "internal", "message": "documents request failed"})


def _workflow_api(request: Request):
    return get_container(request).get_port("documents_workflow_api")


def _delegated_create_allowed(request: Request, actor: UserContext) -> bool:
    container = get_container(request)
    if not container.has_port("settings_service"):
        return False
    settings = container.get_port("settings_service").get_module_settings("documents")
    mapping = settings.get("can_create_new_documents", {})
    return isinstance(mapping, dict) and bool(mapping.get(str(actor.user_id), False))


def _pool_api(request: Request):
    return get_container(request).get_port("documents_pool_api")


def _artifacts_api(request: Request):
    return get_container(request).get_port("documents_artifacts_api")


def _read_api(request: Request):
    return get_container(request).get_port("documents_read_api")


def _comments_api(request: Request):
    return get_container(request).get_port("documents_comments_api")


def _parse_optional_iso8601(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _header_payload(header) -> dict[str, Any]:
    return {
        "document_id": header.document_id,
        "doc_type": header.doc_type.value,
        "control_class": header.control_class.value,
        "workflow_profile_id": header.workflow_profile_id,
        "register_binding": header.register_binding,
        "department": header.department,
        "site": header.site,
        "regulatory_scope": header.regulatory_scope,
        "distribution_roles": list(header.distribution_roles),
        "distribution_sites": list(header.distribution_sites),
        "distribution_departments": list(header.distribution_departments),
        "created_at": header.created_at.isoformat(),
        "updated_at": header.updated_at.isoformat(),
    }


def _comment_list_item_payload(row: WorkflowCommentListItem) -> dict[str, object]:
    return {
        "comment_id": row.comment_id,
        "ref_no": row.ref_no,
        "document_id": row.document_id,
        "version": row.version,
        "context": row.context.value,
        "page_number": row.page_number,
        "anchor_json": row.anchor_json,
        "author_display": row.author_display,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "preview_text": row.preview_text,
        "status": row.status.value,
        "updated_at": row.updated_at.isoformat(),
        "etag": row.updated_at.isoformat(),
    }


def _comment_detail_payload(row: WorkflowCommentDetail) -> dict[str, object]:
    return {
        "comment_id": row.comment_id,
        "ref_no": row.ref_no,
        "document_id": row.document_id,
        "version": row.version,
        "context": row.context.value,
        "page_number": row.page_number,
        "author_display": row.author_display,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "full_text": row.full_text,
        "status": row.status.value,
        "source_kind": row.source_kind.value,
        "status_note": row.status_note,
        "status_changed_by": row.status_changed_by,
        "status_changed_at": row.status_changed_at.isoformat() if row.status_changed_at else None,
    }


def _comment_record_payload(row: WorkflowCommentRecord) -> dict[str, object]:
    return {
        "comment_id": row.comment_id,
        "ref_no": row.ref_no,
        "document_id": row.document_id,
        "version": row.version,
        "context": row.context.value,
        "status": row.status.value,
        "page_number": row.page_number,
        "preview_text": row.preview_text,
        "updated_at": row.updated_at.isoformat(),
        "etag": row.updated_at.isoformat(),
    }


def _mutate_version_state(
    request: Request,
    state,
    expected: str | None,
    operation,
    *,
    actor: UserContext | None = None,
    action: str | None = None,
):
    api = _workflow_api(request)
    return api.mutate_version_if_current(
        state,
        expected,
        operation,
        actor=actor,
        action=action,
    )


async def _read_upload(request: Request, *, magic: bytes, label: str) -> bytes:
    raw_length = request.headers.get("Content-Length")
    if raw_length:
        try:
            if int(raw_length) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail={"error": "upload_too_large", "message": "upload exceeds 100 MiB"},
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": "invalid_content_length"}) from exc
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"error": "upload_too_large", "message": "upload exceeds 100 MiB"},
            )
        chunks.append(chunk)
    payload = b"".join(chunks)
    if not payload:
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_upload", "message": f"{label} upload body is empty"},
        )
    if not payload.startswith(magic):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_magic_bytes", "message": f"upload is not a valid {label} file"},
        )
    return payload


def _content_disposition(filename: str) -> str:
    safe = "".join(ch for ch in filename if ch.isalnum() or ch in "._- ").strip() or "artifact"
    return f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(filename)}"


def _etag_for_state(state) -> str:
    return str(getattr(state, "last_event_id", None) or "none")


def _state_payload(state, actor: UserContext) -> tuple[dict[str, Any], list[str]]:
    actions = sorted(available_actions_for_actor(state, actor))
    payload = document_version_state_to_payload(state)
    payload["available_actions"] = actions
    return payload, actions


def _state_response(state, actor: UserContext, response: Response | None = None) -> VersionStateResponse:
    payload, actions = _state_payload(state, actor)
    etag = _etag_for_state(state)
    if response is not None:
        response.headers["ETag"] = etag
    return VersionStateResponse(state=payload, available_actions=actions, etag=etag)


def _required_if_match(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        raise HTTPException(
            status_code=428,
            detail={"error": "if_match_required", "message": "If-Match is required"},
        )
    value = raw.strip()
    return None if value == "none" else value


def _load_state(request: Request, document_id: str, version: int):
    state = _pool_api(request).get_document_version(document_id, version)
    if state is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "document version not found"})
    return state


@router.get("/pool/by-status/{status}", response_model=list[dict[str, Any]])
def list_by_status(
    status: str,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> list[dict[str, Any]]:
    try:
        parsed = DocumentStatus(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_status"}) from exc
    rows = _pool_api(request).list_by_status_for_actor(parsed, actor)
    return [_state_payload(row, actor)[0] for row in rows]


@router.get("/versions/{document_id}/{version}", response_model=VersionStateResponse)
def get_version(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> VersionStateResponse:
    state = _pool_api(request).get_document_version_for_actor(document_id, version, actor)
    if state is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "document version not found"})
    return _state_response(state, actor, response)


@router.get("/versions/{document_id}/{version}/artifacts")
def list_artifacts(
    document_id: str,
    version: int,
    request: Request,
    _actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> list[dict[str, object]]:
    state = _pool_api(request).get_document_version_for_actor(document_id, version, _actor)
    if state is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "document version not found"})
    return [
        artifact_to_public_payload(artifact)
        for artifact in _artifacts_api(request).list_artifacts_for_actor(document_id, version, _actor)
    ]


@router.get("/artifacts/{artifact_id}")
def get_artifact(
    artifact_id: str,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, object]:
    artifact = _artifacts_api(request).get_artifact_by_id_for_actor(artifact_id, actor)
    if artifact is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "artifact not found"})
    return artifact_to_public_payload(artifact)


@router.get("/artifacts/{artifact_id}/content")
def get_artifact_content(
    artifact_id: str,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    api = _artifacts_api(request)
    artifact = api.get_artifact_by_id_for_actor(artifact_id, actor)
    if artifact is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "artifact not found"})
    try:
        content = api.read_artifact_bytes_for_actor(artifact_id, actor)
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    headers = {
        "Content-Disposition": _content_disposition(artifact.original_filename),
        "Content-Length": str(len(content)),
        "ETag": artifact.sha256,
        "X-Content-SHA256": artifact.sha256,
    }
    return StreamingResponse(BytesIO(content), media_type=artifact.mime_type, headers=headers)


@router.get("/headers/{document_id}")
def get_header(
    document_id: str,
    request: Request,
    response: Response,
    _actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    header = _pool_api(request).get_header(document_id)
    if header is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "document header not found"})
    response.headers["ETag"] = header.updated_at.isoformat()
    return _header_payload(header)


@router.get("/home/tasks")
def list_home_tasks(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    scope: str | None = None,
    user_id: str | None = None,
):
    del user_id
    return _pool_api(request).list_tasks_for_actor(actor, scope=scope)


@router.get("/home/review-actions")
def list_home_review_actions(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    user_id: str | None = None,
):
    del user_id
    return _pool_api(request).list_review_actions_for_actor(actor)


@router.get("/home/recent")
def list_home_recent(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    user_id: str | None = None,
):
    del user_id
    return _pool_api(request).list_recent_documents_for_actor(actor)


@router.get("/released")
def list_released_documents(
    request: Request,
    _actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    return _pool_api(request).list_current_released_documents()


@router.post("/reads/open-released")
def open_released_document(
    body: ReadDocumentBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, object]:
    try:
        session = _read_api(request).open_released_document_for_actor(
            actor, body.document_id, body.version
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "document_id": session.document_id,
        "version": session.version,
        "opened_at": session.opened_at.isoformat(),
    }


@router.post("/reads/confirm")
def confirm_released_document(
    body: ReadDocumentBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, object]:
    try:
        receipt = _read_api(request).confirm_released_document_read_for_actor(
            actor, body.document_id, body.version, source=body.source
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _receipt_payload(receipt)


@router.get("/reads/receipt/{document_id}/{version}")
def get_read_receipt(
    document_id: str,
    version: int,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    try:
        receipt = _read_api(request).get_read_receipt_for_actor(actor, document_id, version)
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    if receipt is None:
        return Response(status_code=204)
    return _receipt_payload(receipt)


@router.post("/reads/tracked/start")
def start_tracked_read(
    body: StartTrackedReadBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, object]:
    try:
        session = _read_api(request).start_tracked_pdf_read_for_actor(
            actor,
            body.document_id,
            body.version,
            artifact_id=body.artifact_id,
            total_pages=body.total_pages,
            source=body.source,
            min_seconds_per_page=body.min_seconds_per_page,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "document_id": session.document_id,
        "version": session.version,
        "artifact_id": session.artifact_id,
        "total_pages": session.total_pages,
        "min_seconds_per_page": session.min_seconds_per_page,
        "source": session.source,
        "opened_at": session.opened_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
    }


@router.post("/reads/tracked/{session_id}/dwell")
def record_tracked_dwell(
    session_id: str,
    body: PageDwellBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, object]:
    try:
        progress = _read_api(request).record_page_dwell_for_actor(
            actor,
            session_id,
            page_number=body.page_number,
            dwell_seconds=body.dwell_seconds,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _progress_payload(progress)


@router.get("/reads/tracked/{session_id}/progress")
def get_tracked_progress(
    session_id: str,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, object]:
    try:
        progress = _read_api(request).get_pdf_read_progress_for_actor(actor, session_id)
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _progress_payload(progress)


@router.post("/reads/tracked/{session_id}/finalize")
def finalize_tracked_read(
    session_id: str,
    body: FinalizeReadBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    try:
        receipt = _read_api(request).finalize_tracked_pdf_read_for_actor(
            actor, session_id, source=body.source
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    if receipt is None:
        return Response(status_code=204)
    return _receipt_payload(receipt)


def _receipt_payload(receipt) -> dict[str, object]:
    return {
        "receipt_id": receipt.receipt_id,
        "user_id": receipt.user_id,
        "document_id": receipt.document_id,
        "version": receipt.version,
        "confirmed_at": receipt.confirmed_at.isoformat(),
        "source": receipt.source,
    }


def _progress_payload(progress) -> dict[str, object]:
    return {
        "session_id": progress.session_id,
        "total_pages": progress.total_pages,
        "completed_pages": list(progress.completed_pages),
        "missing_pages": list(progress.missing_pages),
        "page_seconds": {str(key): value for key, value in progress.page_seconds.items()},
        "is_complete": progress.is_complete,
    }


@router.get("/capabilities")
def get_documents_capabilities(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, bool]:
    delegated = False
    container = get_container(request)
    if container.has_port("settings_service"):
        settings = container.get_port("settings_service").get_module_settings("documents")
        mapping = settings.get("can_create_new_documents", {})
        if isinstance(mapping, dict):
            delegated = bool(mapping.get(str(actor.user_id), False))
    return compute_global_capabilities(actor, delegated_create_allowed=delegated)


@router.post("/versions/create", response_model=VersionStateResponse)
def create_version(
    body: CreateVersionBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> VersionStateResponse:
    api = _workflow_api(request)
    try:
        state = api.create_document_version(
            body.document_id,
            body.version,
            owner_user_id=body.owner_user_id,
            title=body.title,
            description=body.description,
            doc_type=DocumentType(body.doc_type),
            control_class=ControlClass(body.control_class),
            workflow_profile_id=body.workflow_profile_id,
            delegated_create_allowed=_delegated_create_allowed(request, actor),
            actor=actor,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(state, actor, response)


@router.post("/versions/{document_id}/{version}/workflow/assign-roles", response_model=VersionStateResponse)
def assign_roles(
    document_id: str,
    version: int,
    body: AssignRolesBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        updated = api.assign_workflow_roles(
            state,
            editors=set(body.editors),
            reviewers=set(body.reviewers),
            approvers=set(body.approvers),
            actor=actor,
            expected_last_event_id=expected,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/workflow/start", response_model=VersionStateResponse)
def start_workflow(
    document_id: str,
    version: int,
    body: StartWorkflowBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        updated = api.start_workflow(
            state,
            profile_id=body.profile_id,
            actor=actor,
            expected_last_event_id=expected,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/workflow/editing-complete", response_model=VersionStateResponse)
def editing_complete(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    body: WorkflowSignBody | None = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        sign_request = _optional_sign_request(request, state, "IN_PROGRESS->IN_REVIEW", body, actor)
        updated = api.complete_editing(state, sign_request=sign_request, actor=actor, expected_last_event_id=expected)
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/workflow/review/accept", response_model=VersionStateResponse)
def review_accept(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    body: WorkflowSignBody | None = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        sign_request = _optional_sign_request(request, state, "IN_REVIEW->IN_APPROVAL", body, actor)
        updated = api.accept_review(state, actor=actor, sign_request=sign_request, expected_last_event_id=expected)
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/workflow/review/reject", response_model=VersionStateResponse)
def review_reject(
    document_id: str,
    version: int,
    body: RejectBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        updated = api.reject_review(
            state,
            RejectionReason(
                template_id=body.template_id,
                template_text=body.template_text,
                free_text=body.free_text,
            ),
            actor=actor,
            expected_last_event_id=expected,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/workflow/approval/accept", response_model=VersionStateResponse)
def approval_accept(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    body: WorkflowSignBody | None = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        sign_request = _optional_sign_request(request, state, "IN_APPROVAL->APPROVED", body, actor)
        updated = api.accept_approval(state, actor=actor, sign_request=sign_request, expected_last_event_id=expected)
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/workflow/approval/reject", response_model=VersionStateResponse)
def approval_reject(
    document_id: str,
    version: int,
    body: RejectBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        updated = api.reject_approval(
            state,
            RejectionReason(
                template_id=body.template_id,
                template_text=body.template_text,
                free_text=body.free_text,
            ),
            actor=actor,
            expected_last_event_id=expected,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/workflow/abort", response_model=VersionStateResponse)
def abort_workflow(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        updated = api.abort_workflow(state, actor=actor, expected_last_event_id=expected)
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/import-pdf", response_model=VersionStateResponse)
async def import_pdf(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    content_type = request.headers.get("Content-Type", "").strip().lower()
    if content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_content_type", "message": "Content-Type must be application/pdf"},
        )
    raw_body = await _read_upload(request, magic=b"%PDF", label="PDF")
    tmp = (
        Path(get_container(request).get_port("app_home"))
        / "scratch"
        / "imports"
        / f"{document_id}-{version}-{uuid4().hex}.pdf"
    )
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw_body)
    try:
        updated = api.import_existing_pdf(
            document_id,
            version,
            tmp,
            actor=actor,
            expected_last_event_id=expected,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return _state_response(updated, actor, response)


@router.post(
    "/versions/{document_id}/{version}/workflow/ensure-source-pdf",
    response_model=EnsureSourcePdfResponse,
)
def ensure_source_pdf_for_signing_route(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> EnsureSourcePdfResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        path = api.ensure_source_pdf_for_signing_if_current(state, actor=actor, expected_last_event_id=expected)
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    if path is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "documents_workflow",
                "message": (
                    "SOURCE_PDF could not be prepared "
                    "(missing DOCX/PDF source or conversion unavailable)"
                ),
            },
        )
    updated = _pool_api(request).get_document_version_for_actor(document_id, version, actor)
    if updated is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "document version not found"})
    artifact_id: str | None = None
    for artifact in _artifacts_api(request).list_artifacts_for_actor(document_id, version, actor):
        if artifact.artifact_type == ArtifactType.SOURCE_PDF and artifact.is_current:
            artifact_id = artifact.artifact_id
            break
    state_dict, actions = _state_payload(updated, actor)
    etag = _etag_for_state(updated)
    response.headers["ETag"] = etag
    return EnsureSourcePdfResponse(
        state=state_dict,
        available_actions=actions,
        etag=etag,
        artifact_id=artifact_id,
    )


@router.post("/versions/{document_id}/{version}/import-docx", response_model=VersionStateResponse)
async def import_docx(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    if not docx_conversion_available():
        raise _map_documents_error(
            DocumentsFeatureUnavailableError("DOCX conversion is not available on this backend host")
        )
    _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    content_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_content_type", "message": "Content-Type must be DOCX"},
        )
    raw_body = await _read_upload(request, magic=b"PK\x03\x04", label="DOCX")
    tmp = (
        Path(get_container(request).get_port("app_home"))
        / "scratch"
        / "imports"
        / f"{document_id}-{version}-{uuid4().hex}.docx"
    )
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw_body)
    try:
        updated = _workflow_api(request).import_existing_docx(
            document_id,
            version,
            tmp,
            actor=actor,
            expected_last_event_id=expected,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return _state_response(updated, actor, response)


@router.put("/headers/{document_id}")
def update_header(
    document_id: str,
    body: HeaderUpdateBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
):
    expected = _required_if_match(if_match)
    if expected is None:
        raise HTTPException(
            status_code=428,
            detail={"error": "if_match_required", "message": "If-Match is required"},
        )
    api = _workflow_api(request)
    try:
        header = api.update_document_header_if_current(
            document_id,
            expected_updated_at=expected,
            actor=actor,
            workflow_profile_id=body.workflow_profile_id,
            department=body.department,
            site=body.site,
            regulatory_scope=body.regulatory_scope,
            distribution_roles=body.distribution_roles,
            distribution_sites=body.distribution_sites,
            distribution_departments=body.distribution_departments,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    response.headers["ETag"] = header.updated_at.isoformat()
    return _header_payload(header)


@router.patch("/versions/{document_id}/{version}/metadata", response_model=VersionStateResponse)
def patch_version_metadata(
    document_id: str,
    version: int,
    body: MetadataBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    user_id, role = actor_user_and_role(actor)
    api = _workflow_api(request)
    try:
        updated = _mutate_version_state(
            request,
            state,
            expected,
            lambda current: api.update_version_metadata(
                current,
                title=body.title,
                description=body.description,
                valid_until=_parse_optional_iso8601(body.valid_until),
                next_review_at=_parse_optional_iso8601(body.next_review_at),
                custom_fields=body.custom_fields,
                actor_user_id=user_id,
                actor_role=role,
            ),
            actor=actor,
            action="update_metadata",
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.get("/versions/{document_id}/{version}/comments")
def list_workflow_comments(
    document_id: str,
    version: int,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    context: str = WorkflowCommentContext.PDF_REVIEW.value,
) -> list[dict[str, object]]:
    state = _load_state(request, document_id, version)
    user_id, role = actor_user_and_role(actor)
    try:
        parsed_context = WorkflowCommentContext(context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_context"}) from exc
    api = _comments_api(request)
    try:
        rows = api.list_workflow_comments(
            state,
            context=parsed_context,
            actor_user_id=user_id,
            actor_role=role,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return [_comment_list_item_payload(row) for row in rows]


@router.get("/comments/{comment_id}")
def get_workflow_comment_detail(
    comment_id: str,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, object]:
    user_id, role = actor_user_and_role(actor)
    api = _comments_api(request)
    try:
        detail = api.get_workflow_comment_detail(comment_id, actor_user_id=user_id, actor_role=role)
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _comment_detail_payload(detail)


@router.post("/versions/{document_id}/{version}/comments/sync-docx")
def sync_docx_comments(
    document_id: str,
    version: int,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> list[dict[str, object]]:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    user_id, role = actor_user_and_role(actor)
    api = _comments_api(request)
    try:
        rows = api.sync_docx_comments_if_current(
            state, expected_last_event_id=expected, actor_user_id=user_id, actor_role=role
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return [_comment_list_item_payload(row) for row in rows]


@router.post("/versions/{document_id}/{version}/comments")
def create_pdf_workflow_comment(
    document_id: str,
    version: int,
    body: CreatePdfCommentBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, object]:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    user_id, role = actor_user_and_role(actor)
    try:
        parsed_context = WorkflowCommentContext(body.context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_context"}) from exc
    api = _comments_api(request)
    try:
        record = api.create_pdf_workflow_comment_if_current(
            state,
            expected_last_event_id=expected,
            context=parsed_context,
            actor_user_id=user_id,
            actor_role=role,
            page_number=body.page_number,
            comment_text=body.comment_text,
            anchor_json=body.anchor_json,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _comment_record_payload(record)


@router.post("/comments/{comment_id}/status")
def set_workflow_comment_status(
    comment_id: str,
    body: CommentStatusBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, object]:
    expected = _required_if_match(if_match)
    if expected is None:
        raise HTTPException(
            status_code=428,
            detail={"error": "if_match_required", "message": "If-Match is required"},
        )
    user_id, role = actor_user_and_role(actor)
    try:
        parsed_status = WorkflowCommentStatus(body.new_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_status"}) from exc
    api = _comments_api(request)
    try:
        record = api.set_workflow_comment_status_if_current(
            comment_id,
            expected_updated_at=expected,
            new_status=parsed_status,
            actor_user_id=user_id,
            actor_role=role,
            note=body.note,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    response.headers["ETag"] = record.updated_at.isoformat()
    return _comment_record_payload(record)


@router.post("/versions/{document_id}/{version}/lifecycle/archive", response_model=VersionStateResponse)
def archive_approved_version(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    user_id, role = actor_user_and_role(actor)
    api = _workflow_api(request)
    try:
        updated = _mutate_version_state(
            request,
            state,
            expected,
            lambda current: api.archive_approved(current, role, actor_user_id=user_id),
            actor=actor,
            action="archive",
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/lifecycle/extend-annual", response_model=ExtendAnnualResponse)
def extend_annual_validity_route(
    document_id: str,
    version: int,
    body: ExtendAnnualBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ExtendAnnualResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    try:
        review_outcome = ValidityExtensionOutcome(body.review_outcome)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_review_outcome"}) from exc
    api = _workflow_api(request)
    try:
        updated, is_maxed = api.extend_annual_validity_signed(
            state,
            actor=actor,
            sign_intent={
                "placement": body.sign_intent.placement,
                "layout": body.sign_intent.layout,
                "password": body.sign_intent.password,
                "reason": body.sign_intent.reason,
            },
            signature_api=get_container(request).get_port("signature_api"),
            scratch_root=Path(get_container(request).get_port("app_home")) / "scratch" / "workflow-sign",
            expected_last_event_id=expected,
            duration_days=body.duration_days,
            reason=body.reason,
            review_outcome=review_outcome,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    payload, actions = _state_payload(updated, actor)
    etag = _etag_for_state(updated)
    response.headers["ETag"] = etag
    return ExtendAnnualResponse(state=payload, available_actions=actions, etag=etag, is_maxed=is_maxed)


@router.post("/versions/{document_id}/{version}/lifecycle/new-version-after-archive", response_model=VersionStateResponse)
def new_version_after_archive(
    document_id: str,
    version: int,
    body: NewVersionAfterArchiveBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    api = _workflow_api(request)
    try:
        # CAS + new_version policy live on the public module API (no outer wrap).
        updated = api.create_new_version_after_archive(
            state,
            body.next_version,
            expected_last_event_id=expected,
            actor=actor,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.get("/versions/{document_id}/{version}/change-requests")
def list_change_requests(
    document_id: str,
    version: int,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> list[dict[str, object]]:
    state = _load_state(request, document_id, version)
    api = _workflow_api(request)
    try:
        return api.list_change_requests(state)
    except Exception as exc:
        raise _map_documents_error(exc) from exc


@router.post("/versions/{document_id}/{version}/change-requests", response_model=VersionStateResponse)
def add_change_request(
    document_id: str,
    version: int,
    body: ChangeRequestBody,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    state = _load_state(request, document_id, version)
    expected = _required_if_match(if_match)
    user_id, role = actor_user_and_role(actor)
    api = _workflow_api(request)
    try:
        updated = _mutate_version_state(
            request,
            state,
            expected,
            lambda current: api.add_change_request(
                current,
                change_id=body.change_id,
                reason=body.reason,
                impact_refs=body.impact_refs,
                actor_user_id=user_id,
                actor_role=role,
            ),
            actor=actor,
            action="change_requests",
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    return _state_response(updated, actor, response)


@router.post("/versions/{document_id}/{version}/create-from-template", response_model=VersionStateResponse)
async def create_from_template(
    document_id: str,
    version: int,
    request: Request,
    response: Response,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> VersionStateResponse:
    if not docx_conversion_available():
        raise _map_documents_error(
            DocumentsFeatureUnavailableError("DOCX conversion is not available on this backend host")
        )
    pool_state = _pool_api(request).get_document_version(document_id, version)
    expected = _required_if_match(if_match) if pool_state is not None else None
    content_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    allowed = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_content_type", "message": "Content-Type must be DOTX/DOCX template"},
        )
    raw_body = await _read_upload(request, magic=b"PK\x03\x04", label="template")
    suffix = ".dotx" if "template" in content_type else ".docx"
    tmp = (
        Path(get_container(request).get_port("app_home"))
        / "scratch"
        / "imports"
        / f"{document_id}-{version}-{uuid4().hex}{suffix}"
    )
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw_body)
    user_id, role = actor_user_and_role(actor)
    api = _workflow_api(request)
    try:
        if pool_state is None:
            updated = api.create_from_template(
                document_id,
                version,
                tmp,
                actor_user_id=user_id,
                actor_role=role,
            )
        else:
            updated = _mutate_version_state(
                request,
                pool_state,
                expected,
                lambda _current: api.create_from_template(
                    document_id,
                    version,
                    tmp,
                    actor_user_id=user_id,
                    actor_role=role,
                ),
            )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return _state_response(updated, actor, response)


@router.get("/workflow-profiles/definitions")
def list_profile_definitions(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    include_inactive: bool = True,
):
    api = _workflow_api(request)
    try:
        return api.list_workflow_profile_definitions(actor=actor, include_inactive=include_inactive)
    except Exception as exc:
        raise _map_documents_error(exc) from exc


@router.post("/workflow-profiles/definitions")
def create_profile_definition(
    body: ProfileDefinitionBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    api = _workflow_api(request)
    try:
        return api.create_workflow_profile_definition(body.payload, actor=actor, change_reason=body.change_reason)
    except Exception as exc:
        raise _map_documents_error(exc) from exc


@router.get("/workflow-profiles/definitions/{profile_code}/versions")
def list_profile_versions(
    profile_code: str,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    api = _workflow_api(request)
    try:
        return api.list_workflow_profile_versions(profile_code, actor=actor)
    except Exception as exc:
        raise _map_documents_error(exc) from exc


@router.post("/workflow-profiles/definitions/{profile_code}/versions")
def create_profile_version(
    profile_code: str,
    body: ProfileDefinitionBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    api = _workflow_api(request)
    try:
        return api.create_workflow_profile_version(
            profile_code,
            body.payload,
            actor=actor,
            change_reason=body.change_reason,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc


@router.post("/workflow-profiles/definitions/{profile_code}/activate")
def activate_profile_definition(
    profile_code: str,
    body: ProfileCodeBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    api = _workflow_api(request)
    try:
        return api.activate_workflow_profile_definition(
            profile_code,
            actor=actor,
            change_reason=body.change_reason,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc


@router.post("/workflow-profiles/definitions/{profile_code}/deactivate")
def deactivate_profile_definition(
    profile_code: str,
    body: ProfileCodeBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    api = _workflow_api(request)
    try:
        return api.deactivate_workflow_profile_definition(
            profile_code,
            actor=actor,
            change_reason=body.change_reason,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc


@router.post("/workflow-profiles/bindings")
def bind_document_type_profile(
    body: BindDocTypeBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    api = _workflow_api(request)
    try:
        return api.bind_document_type_default_profile(
            DocumentType(body.doc_type),
            body.profile_code,
            actor=actor,
            change_reason=body.change_reason,
        )
    except Exception as exc:
        raise _map_documents_error(exc) from exc
