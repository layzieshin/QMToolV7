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
from .signature_execute_ops import SignatureExecuteOps
from .signature_policy_ops import SignaturePolicyOps
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
        self._policy_ops = SignaturePolicyOps(
            repository=self.repository,
            secure_store=self.secure_store,
            password_verifier=self.password_verifier,
        )
        self._execute_ops = SignatureExecuteOps(
            settings_service=self.settings_service,
            logger=self.logger,
            audit_logger=self.audit_logger,
            password_verifier=self.password_verifier,
            event_bus=self.event_bus,
            crypto_signer=self.crypto_signer,
            resolve_runtime_layout_fn=self.resolve_runtime_layout,
        )

    # -- Execute delegation --------------------------------------------------

    def sign_with_fixed_position(self, request: SignRequest) -> SignResult:
        return self._execute_ops.sign_with_fixed_position(request)

    # -- Template delegation -------------------------------------------------

    def import_signature_asset(self, owner_user_id: str, source_path: Path) -> SignatureAsset:
        return self._template_use_cases.import_signature_asset(owner_user_id, source_path)

    def create_user_signature_template(
        self, *, owner_user_id: str, name: str, placement: SignaturePlacementInput,
        layout: LabelLayoutInput, signature_asset_id: str | None, scope: str = "user",
    ) -> UserSignatureTemplate:
        return self._template_use_cases.create_user_signature_template(
            owner_user_id=owner_user_id, name=name, placement=placement,
            layout=layout, signature_asset_id=signature_asset_id, scope=scope,
        )

    def list_user_signature_templates(self, owner_user_id: str) -> list[UserSignatureTemplate]:
        return self._template_use_cases.list_user_signature_templates(owner_user_id)

    def list_global_signature_templates(self) -> list[UserSignatureTemplate]:
        return self._template_use_cases.list_global_signature_templates()

    def delete_signature_template(self, template_id: str) -> None:
        self._template_use_cases.delete_signature_template(template_id)

    def update_signature_template(
        self, *, template_id: str, owner_user_id: str, name: str | None = None,
        placement: SignaturePlacementInput | None = None, layout: LabelLayoutInput | None = None,
        signature_asset_id: str | None = None,
    ) -> UserSignatureTemplate:
        return self._template_use_cases.update_signature_template(
            template_id=template_id, owner_user_id=owner_user_id, name=name,
            placement=placement, layout=layout, signature_asset_id=signature_asset_id,
        )

    def copy_global_template_to_user(self, template_id: str, owner_user_id: str, name: str | None = None) -> UserSignatureTemplate:
        return self._template_use_cases.copy_global_template_to_user(template_id, owner_user_id, name=name)

    # -- Policy delegation ---------------------------------------------------

    def set_active_signature_asset(self, owner_user_id: str, asset_id: str, password: str | None = None) -> None:
        self._policy_ops.set_active_signature_asset(owner_user_id, asset_id, password=password)

    def get_active_signature_asset_id(self, owner_user_id: str) -> str | None:
        return self._policy_ops.get_active_signature_asset_id(owner_user_id)

    def clear_active_signature(self, owner_user_id: str, password: str | None = None) -> None:
        self._policy_ops.clear_active_signature(owner_user_id, password=password)

    def export_active_signature(self, owner_user_id: str, target_path: Path) -> Path:
        return self._policy_ops.export_active_signature(owner_user_id, target_path)

    def import_signature_asset_bytes(self, owner_user_id: str, png_bytes: bytes, *, filename_hint: str = "canvas.png") -> SignatureAsset:
        return self._policy_ops.import_signature_asset_bytes(
            owner_user_id, png_bytes, filename_hint=filename_hint, import_fn=self.import_signature_asset,
        )

    def import_signature_asset_and_set_active(self, owner_user_id: str, source_path: Path, *, password: str | None = None) -> SignatureAsset:
        return self._policy_ops.import_signature_asset_and_set_active(
            owner_user_id, source_path, password=password, import_fn=self.import_signature_asset,
        )

    def import_signature_asset_bytes_and_set_active(
        self, owner_user_id: str, png_bytes: bytes, *, filename_hint: str = "canvas.png", password: str | None = None,
    ) -> SignatureAsset:
        return self._policy_ops.import_signature_asset_bytes_and_set_active(
            owner_user_id, png_bytes, filename_hint=filename_hint, password=password, import_fn=self.import_signature_asset,
        )

    def sign_with_template(
        self, *, template_id: str, input_pdf: Path, signer_user: str, password: str | None = None,
        output_pdf: Path | None = None, dry_run: bool = False, overwrite_output: bool = False,
        reason: str = "template_api", placement_override: SignaturePlacementInput | None = None,
        layout_override: LabelLayoutInput | None = None,
    ) -> SignResult:
        return self._template_use_cases.sign_with_template(
            template_id=template_id, input_pdf=input_pdf, signer_user=signer_user,
            password=password, output_pdf=output_pdf, dry_run=dry_run, overwrite_output=overwrite_output,
            reason=reason, placement_override=placement_override, layout_override=layout_override,
        )

    def resolve_runtime_layout(self, layout: LabelLayoutInput, *, signer_user: str | None = None) -> LabelLayoutInput:
        return self._policy_ops.resolve_runtime_layout(layout, signer_user=signer_user)

    # -- Legacy methods kept for template_use_cases backward compat ----------

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
        return SignatureExecuteOps._hex_to_rgb(hex_value)

    @staticmethod
    def _transparent_png() -> bytes:
        return SignatureExecuteOps._transparent_png()
