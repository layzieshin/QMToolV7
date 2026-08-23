"""HTTP transport for signature module (J04-M0-P3B). No local signature DB."""
from __future__ import annotations

import os
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from interfaces.clients.http_transport import (
    BackendHttpTransport,
    BackendTransportError,
    resolve_backend_base_url_from_env,
)
from modules.signature.api import (
    LabelLayoutInput,
    SignRequest,
    SignResult,
    SignatureAsset,
    SignaturePlacementInput,
    UserSignatureTemplate,
)
from modules.signature.api import SignatureError, layout_from_payload, layout_to_payload, placement_from_payload


class SignatureBackendTransportError(SignatureError):
    """Raised when the signature backend HTTP transport fails."""


_token_provider: Callable[[], str | None] | None = None
_reject_env_token: bool = False


def bind_pyqt_session_token_provider(provider: Callable[[], str | None]) -> None:
    global _token_provider, _reject_env_token
    _token_provider = provider
    _reject_env_token = True


def clear_pyqt_session_token_provider() -> None:
    global _token_provider, _reject_env_token
    _token_provider = None
    _reject_env_token = False


def resolve_session_token() -> str:
    if _token_provider is not None:
        token = (_token_provider() or "").strip()
        if token:
            return token
        if _reject_env_token:
            raise SignatureBackendTransportError(
                "backend session is required for signature operations (QMTOOL_SESSION_TOKEN ignored in PyQt)"
            )
    token = os.environ.get("QMTOOL_SESSION_TOKEN", "").strip()
    if not token:
        raise SignatureBackendTransportError(
            "QMTOOL_SESSION_TOKEN is required for signature operations (no local SQLite fallback)"
        )
    return token


class SignatureHttpClient:
    def __init__(self, *, base_url: str, token: str) -> None:
        self._transport = BackendHttpTransport(base_url=base_url.rstrip("/"), token_provider=lambda: token)

    @classmethod
    def from_env(cls) -> SignatureHttpClient:
        return cls(base_url=resolve_backend_base_url_from_env(), token=resolve_session_token())

    @classmethod
    def for_runtime(cls) -> SignatureHttpClient:
        return cls.from_env()

    def _request(self, method: str, path: str, *, body: dict[str, Any] | None = None, raw_body: bytes | None = None, content_type: str = "application/json", headers: dict[str, str] | None = None) -> Any:
        try:
            return self._transport.request(
                method,
                path,
                body=body,
                raw_body=raw_body,
                content_type=content_type,
                auth=True,
                headers=headers,
            )
        except BackendTransportError as exc:
            raise SignatureBackendTransportError(
                f"signature backend HTTP {exc.status_code or '?'}: {exc.body or str(exc)}"
            ) from exc

    def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        raw_body: bytes | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
    ) -> bytes:
        if body is not None:
            import json

            raw_body = json.dumps(body, ensure_ascii=True).encode("utf-8")
        try:
            payload, _headers = self._transport.request_bytes(
                method,
                path,
                raw_body=raw_body,
                content_type=content_type,
                auth=True,
                headers=headers,
            )
            return payload
        except BackendTransportError as exc:
            raise SignatureBackendTransportError(
                f"signature backend HTTP {exc.status_code or '?'}: {exc.body or str(exc)}"
            ) from exc

    @staticmethod
    def _template_from_payload(row: dict[str, Any]) -> UserSignatureTemplate:
        return UserSignatureTemplate(
            template_id=str(row["template_id"]),
            owner_user_id=str(row["owner_user_id"]),
            name=str(row["name"]),
            placement=placement_from_payload(dict(row["placement"])),
            layout=layout_from_payload(dict(row["layout"])),
            signature_asset_id=str(row["signature_asset_id"]) if row.get("signature_asset_id") else None,
            created_at=datetime.fromisoformat(str(row["created_at"])),
            scope=row.get("scope", "user"),
        )

    @staticmethod
    def _asset_from_payload(row: dict[str, Any]) -> SignatureAsset:
        return SignatureAsset(
            asset_id=str(row["asset_id"]),
            owner_user_id=str(row["owner_user_id"]),
            storage_key="",
            media_type=str(row.get("media_type") or "image/png"),
            original_filename=str(row.get("original_filename") or "signature.png"),
            sha256=str(row.get("sha256") or ""),
            size_bytes=int(row.get("size_bytes") or 0),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )


class HttpSignatureApi:
    """SignatureApi-compatible adapter over HTTP."""

    def _client(self) -> SignatureHttpClient:
        return SignatureHttpClient.for_runtime()

    def sign_with_fixed_position(self, request: SignRequest) -> SignResult:
        client = self._client()
        handle_payload = client._request(
            "POST",
            "/api/v1/signature/standalone/upload",
            raw_body=request.input_pdf.read_bytes(),
            content_type="application/pdf",
        )
        if not isinstance(handle_payload, dict):
            raise SignatureBackendTransportError("invalid signature upload response")
        handle = str(handle_payload.get("upload_handle") or "")
        if not handle:
            raise SignatureBackendTransportError("signature upload handle missing from backend response")
        signed_bytes = client._request_bytes(
            "POST",
            "/api/v1/signature/standalone/sign",
            body={
                "upload_handle": handle,
                "placement": {
                    "page_index": request.placement.page_index,
                    "x": request.placement.x,
                    "y": request.placement.y,
                    "target_width": request.placement.target_width,
                },
                "layout": layout_to_payload(request.layout),
                "password": request.password,
                "reason": request.reason,
                "sign_mode": request.sign_mode,
                "dry_run": request.dry_run,
            },
        )
        output_pdf = request.output_pdf or Path(tempfile.gettempdir()) / f"qmtool-signed-{os.getpid()}.pdf"
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        output_pdf.write_bytes(signed_bytes)
        return SignResult(
            output_pdf=output_pdf,
            signed=not request.dry_run,
            sha256="",
            dry_run=request.dry_run,
            mode=request.sign_mode,
        )

    def resolve_runtime_layout(self, layout: LabelLayoutInput, *, signer_user: str | None = None) -> LabelLayoutInput:
        payload = self._client()._request(
            "POST",
            "/api/v1/signature/resolve-runtime-layout",
            body={"layout": layout_to_payload(layout), "signer_user": signer_user},
        )
        if not isinstance(payload, dict):
            raise SignatureBackendTransportError("invalid resolve-runtime-layout response")
        return layout_from_payload(payload)

    def import_signature_asset(self, owner_user_id: str, source_path: Path) -> SignatureAsset:
        del owner_user_id
        return self.import_signature_asset_bytes(source_path.read_bytes(), filename_hint=source_path.name)

    def create_user_signature_template(
        self,
        owner_user_id: str,
        name: str,
        placement: SignaturePlacementInput,
        layout: LabelLayoutInput,
        signature_asset_id: str | None,
        scope: str = "user",
    ) -> UserSignatureTemplate:
        del owner_user_id
        payload = self._client()._request(
            "POST",
            "/api/v1/signature/templates/user",
            body={
                "name": name,
                "placement": {
                    "page_index": placement.page_index,
                    "x": placement.x,
                    "y": placement.y,
                    "target_width": placement.target_width,
                },
                "layout": layout_to_payload(layout),
                "signature_asset_id": signature_asset_id,
                "scope": scope,
            },
        )
        return self._template_from_payload(payload)

    def list_user_signature_templates(self, owner_user_id: str) -> list[UserSignatureTemplate]:
        del owner_user_id
        rows = self._client()._request("GET", "/api/v1/signature/templates/user")
        if not isinstance(rows, list):
            raise SignatureBackendTransportError("invalid template list response")
        return [self._template_from_payload(row) for row in rows if isinstance(row, dict)]

    def list_global_signature_templates(self) -> list[UserSignatureTemplate]:
        rows = self._client()._request("GET", "/api/v1/signature/templates/global")
        if not isinstance(rows, list):
            raise SignatureBackendTransportError("invalid global template list response")
        return [self._template_from_payload(row) for row in rows if isinstance(row, dict)]

    def delete_signature_template(self, template_id: str) -> None:
        self._client()._request("DELETE", f"/api/v1/signature/templates/{template_id}")

    def update_signature_template(
        self,
        *,
        template_id: str,
        owner_user_id: str,
        name: str | None = None,
        placement: SignaturePlacementInput | None = None,
        layout: LabelLayoutInput | None = None,
        signature_asset_id: str | None = None,
    ) -> UserSignatureTemplate:
        del owner_user_id
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if placement is not None:
            body["placement"] = {
                "page_index": placement.page_index,
                "x": placement.x,
                "y": placement.y,
                "target_width": placement.target_width,
            }
        if layout is not None:
            body["layout"] = layout_to_payload(layout)
        if signature_asset_id is not None:
            body["signature_asset_id"] = signature_asset_id
        payload = self._client()._request("PUT", f"/api/v1/signature/templates/{template_id}", body=body)
        return self._template_from_payload(payload)

    def copy_global_template_to_user(self, template_id: str, owner_user_id: str, name: str | None = None) -> UserSignatureTemplate:
        del owner_user_id
        payload = self._client()._request(
            "POST",
            f"/api/v1/signature/templates/global/{template_id}/copy",
            body={"name": name},
        )
        return self._template_from_payload(payload)

    def set_active_signature_asset(self, owner_user_id: str, asset_id: str, password: str | None = None) -> None:
        del owner_user_id
        self._client()._request(
            "POST",
            "/api/v1/signature/assets/active",
            body={"asset_id": asset_id, "password": password},
        )

    def get_active_signature_asset_id(self, owner_user_id: str) -> str | None:
        del owner_user_id
        payload = self._client()._request("GET", "/api/v1/signature/assets/active/id")
        if not isinstance(payload, dict):
            return None
        asset_id = payload.get("asset_id")
        return str(asset_id) if asset_id else None

    def clear_active_signature(self, owner_user_id: str, password: str | None = None) -> None:
        del owner_user_id
        self._client()._request("DELETE", "/api/v1/signature/assets/active", body={"password": password})

    def export_active_signature(self, owner_user_id: str, target_path: Path) -> Path:
        del owner_user_id
        content = self._client()._request_bytes("GET", "/api/v1/signature/assets/active/content")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        return target_path

    def import_signature_asset_bytes(self, owner_user_id: str, png_bytes: bytes, *, filename_hint: str = "canvas.png") -> SignatureAsset:
        del owner_user_id
        payload = self._client()._request(
            "POST",
            "/api/v1/signature/assets/import",
            raw_body=png_bytes,
            content_type="image/png",
            headers={"X-Filename-Hint": filename_hint},
        )
        return self._asset_from_payload(payload)

    def import_signature_asset_and_set_active(
        self,
        owner_user_id: str,
        source_path: Path,
        *,
        password: str | None = None,
    ) -> SignatureAsset:
        return self.import_signature_asset_bytes_and_set_active(
            owner_user_id,
            source_path.read_bytes(),
            filename_hint=source_path.name,
            password=password,
        )

    def import_signature_asset_bytes_and_set_active(
        self,
        owner_user_id: str,
        png_bytes: bytes,
        *,
        filename_hint: str = "canvas.png",
        password: str | None = None,
    ) -> SignatureAsset:
        del owner_user_id
        headers = {"X-Filename-Hint": filename_hint}
        if password:
            headers["X-Signature-Password"] = password
        payload = self._client()._request(
            "POST",
            "/api/v1/signature/assets/import-and-activate",
            raw_body=png_bytes,
            content_type="image/png",
            headers=headers,
        )
        return self._asset_from_payload(payload)

    def sign_with_template(
        self,
        *,
        template_id: str,
        input_pdf: Path,
        signer_user: str,
        password: str | None = None,
        output_pdf: Path | None = None,
        dry_run: bool = False,
        overwrite_output: bool = False,
        reason: str = "template_api",
        placement_override: SignaturePlacementInput | None = None,
        layout_override: LabelLayoutInput | None = None,
    ) -> SignResult:
        selected = next((row for row in self.list_user_signature_templates("") if row.template_id == template_id), None)
        if selected is None:
            selected = next(
                (row for row in self.list_global_signature_templates() if row.template_id == template_id),
                None,
            )
        if selected is None:
            raise SignatureBackendTransportError(f"template '{template_id}' not found")
        placement = placement_override or selected.placement
        layout = layout_override or selected.layout
        request = SignRequest(
            input_pdf=input_pdf,
            output_pdf=output_pdf,
            placement=placement,
            layout=layout,
            overwrite_output=overwrite_output,
            dry_run=dry_run,
            sign_mode="visual",
            signer_user=signer_user,
            password=password,
            reason=reason,
        )
        return self.sign_with_fixed_position(request)

    def verify_password(self, password: str) -> bool:
        payload = self._client()._request("POST", "/api/v1/signature/verify-password", body={"password": password})
        return isinstance(payload, dict) and bool(payload.get("ok"))
