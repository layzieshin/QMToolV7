"""Signature HTTP transport (J04-M0-P3B). Calls ``modules.signature.api`` only."""
from __future__ import annotations

from io import BytesIO
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from modules.signature.api import (
    PasswordInvalidError,
    PasswordRequiredError,
    SignatureError,
    SignatureTemplateError,
    asset_to_payload,
    layout_from_payload,
    layout_to_payload,
    placement_from_payload,
    placement_to_payload,
    template_to_payload,
    SignRequest,
)
from modules.usermanagement.api import UserContext
from modules.usermanagement import api as um_api

from src.backend.auth_dependencies import get_container, require_user_context_normal

router = APIRouter(prefix="/signature", tags=["signature"])
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


class VerifyPasswordBody(BaseModel):
    password: str = Field(min_length=1)


class TemplateCreateBody(BaseModel):
    name: str = Field(min_length=1)
    placement: dict[str, Any]
    layout: dict[str, Any]
    signature_asset_id: str | None = None
    scope: str = "user"


class TemplateUpdateBody(BaseModel):
    name: str | None = None
    placement: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None
    signature_asset_id: str | None = None


class SetActiveBody(BaseModel):
    asset_id: str = Field(min_length=1)
    password: str | None = None


class ClearActiveBody(BaseModel):
    password: str | None = None


class CopyGlobalBody(BaseModel):
    name: str | None = None


class StandaloneSignBody(BaseModel):
    upload_handle: str = Field(min_length=1)
    placement: dict[str, Any]
    layout: dict[str, Any]
    password: str | None = None
    reason: str = "standalone_http"
    sign_mode: str = "visual"
    dry_run: bool = False


def _signature_api(request: Request):
    return get_container(request).get_port("signature_api")


def _map_signature_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SignatureTemplateError):
        message = str(exc)
        status = 403 if any(token in message for token in ("only technical admins", "ownership mismatch")) else 400
        return HTTPException(status_code=status, detail={"error": "forbidden" if status == 403 else "signature", "message": message})
    if isinstance(exc, PasswordRequiredError):
        return HTTPException(status_code=400, detail={"error": "password_required", "message": str(exc)})
    if isinstance(exc, PasswordInvalidError):
        return HTTPException(status_code=403, detail={"error": "password_invalid", "message": str(exc)})
    if isinstance(exc, SignatureError):
        return HTTPException(status_code=400, detail={"error": "signature", "message": str(exc)})
    return HTTPException(status_code=500, detail={"error": "internal", "message": "signature request failed"})


def _upload_store(request: Request) -> dict[str, tuple[Path, str, datetime]]:
    store = getattr(request.app.state, "signature_upload_handles", None)
    if store is None:
        store = {}
        request.app.state.signature_upload_handles = store
    return store


async def _read_upload(request: Request, *, magic: bytes, label: str) -> bytes:
    raw_length = request.headers.get("Content-Length")
    if raw_length:
        try:
            if int(raw_length) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail={"error": "upload_too_large"})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": "invalid_content_length"}) from exc
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail={"error": "upload_too_large"})
        chunks.append(chunk)
    payload = b"".join(chunks)
    if not payload:
        raise HTTPException(status_code=400, detail={"error": "empty_upload", "message": f"{label} body is empty"})
    if not payload.startswith(magic):
        raise HTTPException(status_code=400, detail={"error": "invalid_magic_bytes", "message": f"invalid {label}"})
    return payload


@router.post("/verify-password")
def verify_password(
    body: VerifyPasswordBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, bool]:
    try:
        um_api.authenticate_user(get_container(request), actor.username, body.password)
    except Exception as exc:
        raise HTTPException(status_code=403, detail={"error": "password_invalid", "message": "password verification failed"})
    return {"ok": True}


@router.get("/templates/user")
def list_user_templates(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> list[dict[str, Any]]:
    api = _signature_api(request)
    return [template_to_payload(row) for row in api.list_user_signature_templates(actor.user_id)]


@router.get("/templates/global")
def list_global_templates(
    request: Request,
    _actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> list[dict[str, Any]]:
    api = _signature_api(request)
    return [template_to_payload(row) for row in api.list_global_signature_templates()]


@router.post("/templates/user")
def create_user_template(
    body: TemplateCreateBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, Any]:
    api = _signature_api(request)
    try:
        created = api.create_user_signature_template_for_actor(
            actor=actor,
            name=body.name.strip(),
            placement=placement_from_payload(body.placement),
            layout=layout_from_payload(body.layout),
            signature_asset_id=body.signature_asset_id,
            scope=body.scope if body.scope in {"user", "global"} else "user",
        )
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    return template_to_payload(created)


@router.put("/templates/{template_id}")
def update_template(
    template_id: str,
    body: TemplateUpdateBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, Any]:
    api = _signature_api(request)
    try:
        updated = api.update_signature_template_for_actor(
            actor=actor,
            template_id=template_id,
            name=body.name,
            placement=placement_from_payload(body.placement) if body.placement is not None else None,
            layout=layout_from_payload(body.layout) if body.layout is not None else None,
            signature_asset_id=body.signature_asset_id,
        )
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    return template_to_payload(updated)


@router.delete("/templates/{template_id}", status_code=204, response_class=Response)
def delete_template(
    template_id: str,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> Response:
    api = _signature_api(request)
    try:
        api.delete_signature_template_for_actor(template_id, actor)
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    return Response(status_code=204)


@router.post("/templates/global/{template_id}/copy")
def copy_global_template(
    template_id: str,
    body: CopyGlobalBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, Any]:
    api = _signature_api(request)
    try:
        copied = api.copy_global_template_for_actor(template_id, actor, name=body.name)
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    return template_to_payload(copied)


@router.post("/assets/import")
async def import_asset_bytes(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, Any]:
    content_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"image/png", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail={"error": "invalid_content_type"})
    raw = await _read_upload(request, magic=b"\x89PNG", label="PNG")
    filename = request.headers.get("X-Filename-Hint", "canvas.png")
    api = _signature_api(request)
    try:
        asset = api.import_signature_asset_bytes(actor.user_id, raw, filename_hint=filename)
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    return asset_to_payload(asset)


@router.post("/assets/import-and-activate")
async def import_and_activate_asset(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, Any]:
    content_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"image/png", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail={"error": "invalid_content_type"})
    raw = await _read_upload(request, magic=b"\x89PNG", label="PNG")
    filename = request.headers.get("X-Filename-Hint", "canvas.png")
    password = request.headers.get("X-Signature-Password")
    api = _signature_api(request)
    try:
        asset = api.import_signature_asset_bytes_and_set_active(
            actor.user_id,
            raw,
            filename_hint=filename,
            password=password.strip() if password else None,
        )
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    return asset_to_payload(asset)


@router.post("/assets/active")
def set_active_asset(
    body: SetActiveBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, bool]:
    api = _signature_api(request)
    try:
        api.set_active_signature_asset(actor.user_id, body.asset_id, password=body.password)
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    return {"ok": True}


@router.delete("/assets/active", status_code=204, response_class=Response)
def clear_active_asset(
    body: ClearActiveBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> Response:
    api = _signature_api(request)
    try:
        api.clear_active_signature(actor.user_id, password=body.password)
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    return Response(status_code=204)


@router.get("/assets/active/id")
def get_active_asset_id(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, str | None]:
    api = _signature_api(request)
    return {"asset_id": api.get_active_signature_asset_id(actor.user_id)}


@router.get("/assets/active/content")
def export_active_asset(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    app_home = Path(get_container(request).get_port("app_home"))
    scratch = app_home / "scratch" / "signature-export"
    scratch.mkdir(parents=True, exist_ok=True)
    target = scratch / f"{actor.user_id}-{uuid4().hex}.png"
    api = _signature_api(request)
    try:
        exported = api.export_active_signature(actor.user_id, target)
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    content = exported.read_bytes()
    headers = {"Content-Length": str(len(content)), "Content-Disposition": 'attachment; filename="active-signature.png"'}
    return StreamingResponse(BytesIO(content), media_type="image/png", headers=headers)


@router.post("/standalone/upload")
async def standalone_upload_pdf(
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, str]:
    content_type = request.headers.get("Content-Type", "").strip().lower()
    if content_type != "application/pdf":
        raise HTTPException(status_code=400, detail={"error": "invalid_content_type"})
    raw = await _read_upload(request, magic=b"%PDF", label="PDF")
    app_home = Path(get_container(request).get_port("app_home"))
    scratch = app_home / "scratch" / "signature-uploads"
    scratch.mkdir(parents=True, exist_ok=True)
    handle = uuid4().hex
    path = scratch / f"{handle}.pdf"
    path.write_bytes(raw)
    _upload_store(request)[handle] = (path, actor.user_id, datetime.now(timezone.utc) + timedelta(minutes=10))
    return {"upload_handle": handle}


@router.post("/standalone/sign")
def standalone_sign(
    body: StandaloneSignBody,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
):
    store = _upload_store(request)
    entry = store.get(body.upload_handle)
    if entry is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "upload handle not found"})
    input_path, owner_user_id, expires_at = entry
    if owner_user_id != actor.user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "upload handle belongs to another user"})
    if datetime.now(timezone.utc) >= expires_at:
        store.pop(body.upload_handle, None)
        try:
            input_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(status_code=410, detail={"error": "upload_handle_expired"})
    if not input_path.exists():
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "upload file missing"})

    app_home = Path(get_container(request).get_port("app_home"))
    scratch = app_home / "scratch" / "signature-sign"
    scratch.mkdir(parents=True, exist_ok=True)
    signature_png = scratch / f"active-{uuid4().hex}.png"
    output_pdf = scratch / f"signed-{uuid4().hex}.pdf"
    api = _signature_api(request)
    try:
        exported = api.export_active_signature(actor.user_id, signature_png)
        placement = placement_from_payload(body.placement)
        layout = layout_from_payload(body.layout)
        resolved_layout = api.resolve_runtime_layout(layout, signer_user=actor.username)
        sign_request = SignRequest(
            input_pdf=input_path,
            output_pdf=output_pdf,
            signature_png=exported,
            placement=placement,
            layout=resolved_layout,
            overwrite_output=True,
            dry_run=body.dry_run,
            sign_mode=body.sign_mode if body.sign_mode in {"visual", "crypto", "both"} else "visual",
            signer_user=actor.username,
            password=body.password.strip() if body.password else None,
            reason=body.reason,
        )
        result = api.sign_with_fixed_position(sign_request)
    except Exception as exc:
        raise _map_signature_error(exc) from exc
    finally:
        store.pop(body.upload_handle, None)
        try:
            input_path.unlink(missing_ok=True)
        except OSError:
            pass

    content = result.output_pdf.read_bytes()
    headers = {
        "Content-Length": str(len(content)),
        "Content-Disposition": 'attachment; filename="signed.pdf"',
        "X-Signature-SHA256": result.sha256,
    }
    return StreamingResponse(BytesIO(content), media_type="application/pdf", headers=headers)


@router.post("/resolve-runtime-layout")
def resolve_runtime_layout_route(
    body: dict[str, Any],
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> dict[str, Any]:
    layout = layout_from_payload(body.get("layout", body))
    signer = str(body.get("signer_user") or actor.username)
    api = _signature_api(request)
    resolved = api.resolve_runtime_layout(layout, signer_user=signer)
    return layout_to_payload(resolved)
