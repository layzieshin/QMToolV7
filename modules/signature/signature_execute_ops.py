"""Signature execution operations (SRP split B4).

Contains the core signing logic: visual signing, crypto signing, PDF validation,
password policy enforcement, and audit emission.
"""
from __future__ import annotations

import hashlib
import importlib
import shutil
from io import BytesIO
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import LabelLayoutInput, SignRequest, SignResult
from .crypto_port import CryptoSignRequest, CryptoSignerPort
from .errors import (
    CryptoSigningNotConfiguredError,
    InvalidPlacementError,
    PasswordInvalidError,
    PasswordRequiredError,
    PdfReadError,
    SignatureImageRequiredError,
)
from .output_path_policy import OutputPathPolicy


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SignatureExecuteOps:
    settings_service: object
    logger: object
    audit_logger: object
    password_verifier: Callable[[str, str], bool]
    event_bus: object | None = None
    crypto_signer: CryptoSignerPort | None = None
    resolve_runtime_layout_fn: Callable[..., LabelLayoutInput] | None = None

    def sign_with_fixed_position(self, request: SignRequest) -> SignResult:
        self._publish_event("domain.signature.sign.requested.v1", request, {"mode": request.sign_mode, "dry_run": request.dry_run})
        try:
            self._enforce_password_policy(request)
            output_pdf = self._resolve_output_path(request)
            if not request.input_pdf.exists():
                raise PdfReadError(f"input PDF not found: {request.input_pdf}")

            if request.dry_run:
                self._emit_audit("signature.dry_run", request, output_pdf)
                self._publish_event("domain.signature.sign.dry_run.v1", request, {"output_pdf": str(output_pdf)})
                return SignResult(output_pdf=output_pdf, signed=False, sha256="", dry_run=True, mode=request.sign_mode)

            if request.sign_mode == "crypto" and self.crypto_signer is None:
                raise CryptoSigningNotConfiguredError("crypto signer not configured")

            reader = self._safe_pdf_reader(request.input_pdf)
            if request.placement.page_index >= len(reader.pages):
                raise InvalidPlacementError(f"page_index out of range: {request.placement.page_index} >= {len(reader.pages)}")
            page = reader.pages[request.placement.page_index]
            page_w = float(page.mediabox.width)
            page_h = float(page.mediabox.height)
            self._validate_placement(request, page_w, page_h)

            if request.sign_mode == "visual":
                self._sign_visual(request, output_pdf)
            elif request.sign_mode == "crypto":
                self._sign_crypto(request, output_pdf)
            elif request.sign_mode == "both":
                self._sign_visual(request, output_pdf)
                self._sign_crypto(
                    SignRequest(
                        input_pdf=output_pdf,
                        placement=request.placement,
                        layout=request.layout,
                        signature_png=request.signature_png,
                        output_pdf=output_pdf,
                        overwrite_output=True,
                        dry_run=False,
                        sign_mode="crypto",
                        signer_user=request.signer_user,
                        password=request.password,
                        reason=request.reason,
                    ),
                    output_pdf,
                )
            else:
                raise ValueError(f"unsupported sign_mode: {request.sign_mode}")

            file_hash = hashlib.sha256(output_pdf.read_bytes()).hexdigest()
            self._emit_audit("signature.signed", request, output_pdf, file_hash)
            self._publish_event(
                "domain.signature.sign.succeeded.v1",
                request,
                {"output_pdf": str(output_pdf), "sha256": file_hash, "mode": request.sign_mode},
            )
            return SignResult(output_pdf=output_pdf, signed=True, sha256=file_hash, dry_run=False, mode=request.sign_mode)
        except Exception as exc:
            self._publish_event("domain.signature.sign.failed.v1", request, {"error": str(exc), "mode": request.sign_mode})
            raise

    # -- internals -----------------------------------------------------------

    def _enforce_password_policy(self, request: SignRequest) -> None:
        settings = self.settings_service.get_module_settings("signature")
        requires_password = bool(settings.get("require_password", True))
        if not requires_password:
            return
        if not request.signer_user:
            raise PasswordRequiredError("signer_user is required by password policy")
        if not request.password:
            raise PasswordRequiredError("password required by policy")
        if not self.password_verifier(request.signer_user, request.password):
            raise PasswordInvalidError("password verification failed")

    def _validate_placement(self, request: SignRequest, page_w: float, page_h: float) -> None:
        p = request.placement
        if p.page_index < 0:
            raise InvalidPlacementError("page_index must be >= 0")
        if p.target_width <= 0:
            raise InvalidPlacementError("target_width must be > 0")
        if p.x < 0 or p.y < 0:
            raise InvalidPlacementError("x and y must be >= 0")
        if p.x > page_w or p.y > page_h:
            raise InvalidPlacementError("x/y exceeds page bounds")
        if p.x + p.target_width > page_w:
            raise InvalidPlacementError("x + target_width exceeds page width")
        estimated_height = max(6.0, p.target_width * 0.3)
        if p.y + estimated_height > page_h:
            raise InvalidPlacementError("y + estimated signature height exceeds page height")

    def _resolve_output_path(self, request: SignRequest) -> Path:
        return OutputPathPolicy.resolve(request)

    def _safe_pdf_reader(self, input_pdf: Path):
        if not input_pdf.exists():
            raise PdfReadError(f"input PDF not found: {input_pdf}")
        try:
            reader_mod = importlib.import_module("pypdf")
            PdfReader = getattr(reader_mod, "PdfReader")
        except Exception as exc:
            raise PdfReadError("pypdf is required for non-dry-run signing") from exc
        try:
            return PdfReader(str(input_pdf))
        except Exception as exc:
            raise PdfReadError(f"failed reading pdf: {input_pdf}") from exc

    def _sign_visual(self, request: SignRequest, output_pdf: Path) -> None:
        try:
            from .pdf_signer import PdfSigner, RenderLabels
            from .visual_models import LabelOffsets, LabelPosition, SignaturePlacement
        except Exception as exc:
            raise PdfReadError("visual signing dependencies are not installed") from exc

        if not request.layout.show_signature and not request.layout.show_name and not request.layout.show_date:
            shutil.copyfile(request.input_pdf, output_pdf)
            return

        signature_png = b""
        if request.layout.show_signature:
            if request.signature_png is None or not request.signature_png.exists():
                raise SignatureImageRequiredError("signature image is required when show_signature=true")
            signature_png = request.signature_png.read_bytes()
        else:
            signature_png = self._transparent_png()

        resolved_layout = self._resolve_layout(request)

        placement = SignaturePlacement(
            page_index=request.placement.page_index,
            x=request.placement.x,
            y=request.placement.y,
            target_width=request.placement.target_width,
        )
        labels = RenderLabels(
            name_text=resolved_layout.name_text if resolved_layout.show_name else None,
            date_text=resolved_layout.date_text if resolved_layout.show_date else None,
            name_pos=LabelPosition(resolved_layout.name_position),
            date_pos=LabelPosition(resolved_layout.date_position),
            date_format="%Y-%m-%d",
            offsets=LabelOffsets(
                name_above=resolved_layout.name_above,
                name_below=resolved_layout.name_below,
                date_above=resolved_layout.date_above,
                date_below=resolved_layout.date_below,
                x_offset=resolved_layout.x_offset,
            ),
            color_rgb=self._hex_to_rgb(resolved_layout.color_hex),
            name_font_size=resolved_layout.name_font_size,
            date_font_size=resolved_layout.date_font_size,
            name_rel_x=resolved_layout.name_rel_x,
            name_rel_y=resolved_layout.name_rel_y,
            date_rel_x=resolved_layout.date_rel_x,
            date_rel_y=resolved_layout.date_rel_y,
        )
        PdfSigner.sign_pdf(
            input_path=str(request.input_pdf),
            output_path=str(output_pdf),
            png_signature=signature_png,
            placement=placement,
            labels=labels,
        )

    def _resolve_layout(self, request: SignRequest) -> LabelLayoutInput:
        if self.resolve_runtime_layout_fn is not None:
            return self.resolve_runtime_layout_fn(request.layout, signer_user=request.signer_user)
        return request.layout

    def _sign_crypto(self, request: SignRequest, output_pdf: Path) -> None:
        if self.crypto_signer is None:
            raise CryptoSigningNotConfiguredError("crypto signer not configured")
        self.crypto_signer.sign(
            CryptoSignRequest(input_pdf=request.input_pdf, output_pdf=output_pdf, reason=request.reason)
        )

    def _emit_audit(self, action: str, request: SignRequest, output_pdf: Path, sha256: str = "") -> None:
        self.audit_logger.emit(
            action=action,
            actor=request.signer_user or "system",
            target=str(output_pdf),
            result="ok",
            reason=request.reason,
        )
        self.logger.info(
            "signature",
            action,
            {
                "input_pdf": str(request.input_pdf),
                "output_pdf": str(output_pdf),
                "page_index": request.placement.page_index,
                "x": request.placement.x,
                "y": request.placement.y,
                "width": request.placement.target_width,
                "mode": request.sign_mode,
                "dry_run": request.dry_run,
                "sha256": sha256,
                "ts": _utcnow().isoformat(),
            },
        )

    def _publish_event(self, name: str, request: SignRequest, payload: dict) -> None:
        if self.event_bus is None:
            return
        publish = getattr(self.event_bus, "publish", None)
        if not callable(publish):
            return
        publish(
            EventEnvelope.create(
                name=name, module_id="signature", payload=payload, actor_user_id=request.signer_user,
            )
        )

    @staticmethod
    def _hex_to_rgb(hex_value: str) -> tuple[int, int, int]:
        s = (hex_value or "#000000").strip().lstrip("#")
        if len(s) == 3:
            s = "".join(ch * 2 for ch in s)
        if len(s) != 6:
            return (0, 0, 0)
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError:
            return (0, 0, 0)

    @staticmethod
    def _transparent_png() -> bytes:
        try:
            pil_image_mod = importlib.import_module("PIL.Image")
            img = pil_image_mod.new("RGBA", (1, 1), (0, 0, 0, 0))
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc``\x00\x00\x00\x02\x00\x01"
                b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
            )

