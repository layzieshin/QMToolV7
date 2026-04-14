from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import SignRequest, SignResult, SignatureAsset, SignaturePlacementInput, UserSignatureTemplate, LabelLayoutInput
from .service import SignatureServiceV2


@dataclass
class SignatureApi:
    service: SignatureServiceV2

    def sign_with_fixed_position(self, request: SignRequest) -> SignResult:
        return self.service.sign_with_fixed_position(request)

    def import_signature_asset(self, owner_user_id: str, source_path: Path) -> SignatureAsset:
        return self.service.import_signature_asset(owner_user_id, source_path)

    def create_user_signature_template(
        self,
        owner_user_id: str,
        name: str,
        placement: SignaturePlacementInput,
        layout: LabelLayoutInput,
        signature_asset_id: str | None,
        scope: str = "user",
    ) -> UserSignatureTemplate:
        return self.service.create_user_signature_template(
            owner_user_id=owner_user_id,
            name=name,
            placement=placement,
            layout=layout,
            signature_asset_id=signature_asset_id,
            scope=scope,
        )

    def list_user_signature_templates(self, owner_user_id: str) -> list[UserSignatureTemplate]:
        return self.service.list_user_signature_templates(owner_user_id)

    def list_global_signature_templates(self) -> list[UserSignatureTemplate]:
        return self.service.list_global_signature_templates()

    def delete_signature_template(self, template_id: str) -> None:
        self.service.delete_signature_template(template_id)

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
        return self.service.update_signature_template(
            template_id=template_id,
            owner_user_id=owner_user_id,
            name=name,
            placement=placement,
            layout=layout,
            signature_asset_id=signature_asset_id,
        )

    def copy_global_template_to_user(self, template_id: str, owner_user_id: str, name: str | None = None) -> UserSignatureTemplate:
        return self.service.copy_global_template_to_user(template_id, owner_user_id, name=name)

    def set_active_signature_asset(self, owner_user_id: str, asset_id: str, password: str | None = None) -> None:
        self.service.set_active_signature_asset(owner_user_id, asset_id, password=password)

    def get_active_signature_asset_id(self, owner_user_id: str) -> str | None:
        return self.service.get_active_signature_asset_id(owner_user_id)

    def clear_active_signature(self, owner_user_id: str, password: str | None = None) -> None:
        self.service.clear_active_signature(owner_user_id, password=password)

    def export_active_signature(self, owner_user_id: str, target_path: Path) -> Path:
        return self.service.export_active_signature(owner_user_id, target_path)

    def import_signature_asset_bytes(self, owner_user_id: str, png_bytes: bytes, *, filename_hint: str = "canvas.png") -> SignatureAsset:
        return self.service.import_signature_asset_bytes(owner_user_id, png_bytes, filename_hint=filename_hint)

    def import_signature_asset_and_set_active(
        self,
        owner_user_id: str,
        source_path: Path,
        *,
        password: str | None = None,
    ) -> SignatureAsset:
        return self.service.import_signature_asset_and_set_active(owner_user_id, source_path, password=password)

    def import_signature_asset_bytes_and_set_active(
        self,
        owner_user_id: str,
        png_bytes: bytes,
        *,
        filename_hint: str = "canvas.png",
        password: str | None = None,
    ) -> SignatureAsset:
        return self.service.import_signature_asset_bytes_and_set_active(
            owner_user_id,
            png_bytes,
            filename_hint=filename_hint,
            password=password,
        )

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
    ) -> SignResult:
        return self.service.sign_with_template(
            template_id=template_id,
            input_pdf=input_pdf,
            signer_user=signer_user,
            password=password,
            output_pdf=output_pdf,
            dry_run=dry_run,
            overwrite_output=overwrite_output,
            reason=reason,
        )

