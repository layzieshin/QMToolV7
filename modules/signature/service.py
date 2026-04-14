from __future__ import annotations

import hashlib
import importlib
import shutil
from io import BytesIO
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Callable

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import LabelLayoutInput, SignRequest, SignResult, SignatureAsset, SignaturePlacementInput, UserSignatureTemplate
from .crypto_port import CryptoSignRequest, CryptoSignerPort
from .errors import (
    CryptoSigningNotConfiguredError,
    InvalidPlacementError,
    PasswordInvalidError,
    PasswordRequiredError,
    PdfReadError,
    SignatureAssetError,
    SignatureImageRequiredError,
)
from .output_path_policy import OutputPathPolicy
from .secure_store import EncryptedSignatureBlobStore
from .sqlite_repository import SQLiteSignatureRepository
from .template_use_cases import SignatureTemplateUseCases


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SignatureServiceV2:
    settings_service: object
    logger: object
    audit_logger: object
    password_verifier: Callable[[str, str], bool]
    event_bus: object | None = None
    crypto_signer: CryptoSignerPort | None = None
    repository: SQLiteSignatureRepository | None = None
    secure_store: EncryptedSignatureBlobStore | None = None

    def __post_init__(self) -> None:
        self._template_use_cases = SignatureTemplateUseCases(self)

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
                return SignResult(
                    output_pdf=output_pdf,
                    signed=False,
                    sha256="",
                    dry_run=True,
                    mode=request.sign_mode,
                )

            if request.sign_mode == "crypto" and self.crypto_signer is None:
                raise CryptoSigningNotConfiguredError("crypto signer not configured")

            reader = self._safe_pdf_reader(request.input_pdf)
            if request.placement.page_index >= len(reader.pages):
                raise InvalidPlacementError(
                    f"page_index out of range: {request.placement.page_index} >= {len(reader.pages)}"
                )
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
            return SignResult(
                output_pdf=output_pdf,
                signed=True,
                sha256=file_hash,
                dry_run=False,
                mode=request.sign_mode,
            )
        except Exception as exc:
            self._publish_event("domain.signature.sign.failed.v1", request, {"error": str(exc), "mode": request.sign_mode})
            raise

    def import_signature_asset(self, owner_user_id: str, source_path: Path) -> SignatureAsset:
        return self._template_use_cases.import_signature_asset(owner_user_id, source_path)

    def create_user_signature_template(
        self,
        *,
        owner_user_id: str,
        name: str,
        placement: SignaturePlacementInput,
        layout: LabelLayoutInput,
        signature_asset_id: str | None,
        scope: str = "user",
    ) -> UserSignatureTemplate:
        return self._template_use_cases.create_user_signature_template(
            owner_user_id=owner_user_id,
            name=name,
            placement=placement,
            layout=layout,
            signature_asset_id=signature_asset_id,
            scope=scope,
        )

    def list_user_signature_templates(self, owner_user_id: str) -> list[UserSignatureTemplate]:
        return self._template_use_cases.list_user_signature_templates(owner_user_id)

    def list_global_signature_templates(self) -> list[UserSignatureTemplate]:
        return self._template_use_cases.list_global_signature_templates()

    def delete_signature_template(self, template_id: str) -> None:
        self._template_use_cases.delete_signature_template(template_id)

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
        return self._template_use_cases.update_signature_template(
            template_id=template_id,
            owner_user_id=owner_user_id,
            name=name,
            placement=placement,
            layout=layout,
            signature_asset_id=signature_asset_id,
        )

    def copy_global_template_to_user(self, template_id: str, owner_user_id: str, name: str | None = None) -> UserSignatureTemplate:
        return self._template_use_cases.copy_global_template_to_user(template_id, owner_user_id, name=name)

    def set_active_signature_asset(self, owner_user_id: str, asset_id: str, password: str | None = None) -> None:
        if self.repository is None:
            raise SignatureAssetError("signature template storage is not configured")
        asset = self.repository.get_asset(asset_id)
        if asset is None:
            raise SignatureAssetError(f"unknown signature asset: {asset_id}")
        if asset.owner_user_id != owner_user_id:
            raise SignatureAssetError("active signature ownership mismatch")
        current_asset_id = self.repository.get_active_signature_asset_id(owner_user_id)
        if current_asset_id is not None and current_asset_id != asset_id:
            self._require_valid_password(owner_user_id, password)
        self.repository.set_active_signature_asset(owner_user_id, asset_id)

    def get_active_signature_asset_id(self, owner_user_id: str) -> str | None:
        if self.repository is None:
            return None
        return self.repository.get_active_signature_asset_id(owner_user_id)

    def clear_active_signature(self, owner_user_id: str, password: str | None = None) -> None:
        if self.repository is None:
            raise SignatureAssetError("signature template storage is not configured")
        current_asset_id = self.repository.get_active_signature_asset_id(owner_user_id)
        if current_asset_id is None:
            return
        self._require_valid_password(owner_user_id, password)
        self.repository.clear_active_signature_asset(owner_user_id)

    def export_active_signature(self, owner_user_id: str, target_path: Path) -> Path:
        if self.repository is None or self.secure_store is None:
            raise SignatureAssetError("signature template storage is not configured")
        asset_id = self.repository.get_active_signature_asset_id(owner_user_id)
        if not asset_id:
            raise SignatureAssetError("no active signature for user")
        asset = self.repository.get_asset(asset_id)
        if asset is None:
            raise SignatureAssetError("active signature asset missing")
        blob = self.secure_store.get_bytes(asset.storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(blob)
        return target_path

    def import_signature_asset_bytes(self, owner_user_id: str, png_bytes: bytes, *, filename_hint: str = "canvas.png") -> SignatureAsset:
        if self.repository is None or self.secure_store is None:
            raise SignatureAssetError("signature template storage is not configured")
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp) / filename_hint
            temp.write_bytes(png_bytes)
            return self.import_signature_asset(owner_user_id, temp)

    def import_signature_asset_and_set_active(
        self,
        owner_user_id: str,
        source_path: Path,
        *,
        password: str | None = None,
    ) -> SignatureAsset:
        asset = self.import_signature_asset(owner_user_id, source_path)
        self.set_active_signature_asset(owner_user_id, asset.asset_id, password=password)
        return asset

    def import_signature_asset_bytes_and_set_active(
        self,
        owner_user_id: str,
        png_bytes: bytes,
        *,
        filename_hint: str = "canvas.png",
        password: str | None = None,
    ) -> SignatureAsset:
        asset = self.import_signature_asset_bytes(owner_user_id, png_bytes, filename_hint=filename_hint)
        self.set_active_signature_asset(owner_user_id, asset.asset_id, password=password)
        return asset

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
        return self._template_use_cases.sign_with_template(
            template_id=template_id,
            input_pdf=input_pdf,
            signer_user=signer_user,
            password=password,
            output_pdf=output_pdf,
            dry_run=dry_run,
            overwrite_output=overwrite_output,
            reason=reason,
            placement_override=placement_override,
            layout_override=layout_override,
        )

    def resolve_runtime_layout(self, layout: LabelLayoutInput, *, signer_user: str | None = None) -> LabelLayoutInput:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        resolved_name = layout.name_text
        resolved_date = layout.date_text
        if layout.show_name and not resolved_name:
            resolved_name = signer_user or ""
        if layout.show_date and not resolved_date:
            resolved_date = timestamp
        return LabelLayoutInput(
            show_signature=layout.show_signature,
            show_name=layout.show_name,
            show_date=layout.show_date,
            name_text=resolved_name,
            date_text=resolved_date,
            name_position=layout.name_position,
            date_position=layout.date_position,
            name_font_size=layout.name_font_size,
            date_font_size=layout.date_font_size,
            color_hex=layout.color_hex,
            name_above=layout.name_above,
            name_below=layout.name_below,
            date_above=layout.date_above,
            date_below=layout.date_below,
            x_offset=layout.x_offset,
            name_rel_x=layout.name_rel_x,
            name_rel_y=layout.name_rel_y,
            date_rel_x=layout.date_rel_x,
            date_rel_y=layout.date_rel_y,
        )

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

    def _to_png_bytes(self, source_path: Path) -> bytes:
        suffix = source_path.suffix.lower()
        raw = source_path.read_bytes()
        if suffix == ".png":
            return raw
        try:
            pil_image_mod = importlib.import_module("PIL.Image")
            buf = BytesIO()
            with pil_image_mod.open(source_path) as image:
                first = image.convert("RGBA")
                first.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as exc:
            raise SignatureAssetError("failed to normalize GIF signature to PNG") from exc

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

    def _require_valid_password(self, owner_user_id: str, password: str | None) -> None:
        if not password:
            raise PasswordRequiredError("password required for replacing or deleting active signature")
        if not self.password_verifier(owner_user_id, password):
            raise PasswordInvalidError("password verification failed")

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

        resolved_layout = self.resolve_runtime_layout(request.layout, signer_user=request.signer_user)

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
                name_above=resolved_layout.name_rel_y if resolved_layout.name_rel_y is not None and resolved_layout.name_rel_y < 0 else resolved_layout.name_above,
                name_below=resolved_layout.name_rel_y if resolved_layout.name_rel_y is not None and resolved_layout.name_rel_y >= 0 else resolved_layout.name_below,
                date_above=resolved_layout.date_rel_y if resolved_layout.date_rel_y is not None and resolved_layout.date_rel_y < 0 else resolved_layout.date_above,
                date_below=resolved_layout.date_rel_y if resolved_layout.date_rel_y is not None and resolved_layout.date_rel_y >= 0 else resolved_layout.date_below,
                x_offset=resolved_layout.name_rel_x if resolved_layout.name_rel_x is not None else resolved_layout.x_offset,
            ),
            color_rgb=self._hex_to_rgb(resolved_layout.color_hex),
            name_font_size=resolved_layout.name_font_size,
            date_font_size=resolved_layout.date_font_size,
        )
        PdfSigner.sign_pdf(
            input_path=str(request.input_pdf),
            output_path=str(output_pdf),
            png_signature=signature_png,
            placement=placement,
            labels=labels,
        )

    def _sign_crypto(self, request: SignRequest, output_pdf: Path) -> None:
        if self.crypto_signer is None:
            raise CryptoSigningNotConfiguredError("crypto signer not configured")
        self.crypto_signer.sign(
            CryptoSignRequest(
                input_pdf=request.input_pdf,
                output_pdf=output_pdf,
                reason=request.reason,
            )
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
                name=name,
                module_id="signature",
                payload=payload,
                actor_user_id=request.signer_user,
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
            Image = getattr(pil_image_mod, "Image", None)
            # PIL.Image module exposes new() at module-level
            img = pil_image_mod.new("RGBA", (1, 1), (0, 0, 0, 0))
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            # Fallback tiny valid PNG
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc``\x00\x00\x00\x02\x00\x01"
                b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
            )

