from __future__ import annotations

import hashlib
import shutil
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .contracts import LabelLayoutInput, SignRequest, SignResult, SignatureAsset, SignaturePlacementInput, UserSignatureTemplate
from .errors import SignatureAssetError, SignatureTemplateError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SignatureTemplateUseCases:
    def __init__(self, service: object) -> None:
        self._service = service

    def import_signature_asset(self, owner_user_id: str, source_path: Path) -> SignatureAsset:
        if self._service.repository is None or self._service.secure_store is None:
            raise SignatureAssetError("signature template storage is not configured")
        if not source_path.exists():
            raise SignatureAssetError(f"signature source not found: {source_path}")
        suffix = source_path.suffix.lower()
        if suffix not in (".png", ".gif"):
            raise SignatureAssetError("only PNG or GIF signature images are supported")
        png_bytes = self._service._to_png_bytes(source_path)
        digest = hashlib.sha256(png_bytes).hexdigest()
        storage_key = self._service.secure_store.put_bytes(owner_user_id, ".png", png_bytes)
        asset = SignatureAsset(
            asset_id=uuid4().hex,
            owner_user_id=owner_user_id,
            storage_key=storage_key,
            media_type="image/png",
            original_filename=source_path.name,
            sha256=digest,
            size_bytes=len(png_bytes),
            created_at=_utcnow(),
        )
        self._service.repository.add_asset(asset)
        self._service.audit_logger.emit(
            action="signature.asset.imported",
            actor=owner_user_id,
            target=asset.asset_id,
            result="ok",
            reason="signature_asset_import",
        )
        self._service._publish_event(
            "domain.signature.asset.imported.v1",
            SignRequest(
                input_pdf=Path("N/A"),
                placement=SignaturePlacementInput(page_index=0, x=0.0, y=0.0, target_width=1.0),
                layout=LabelLayoutInput(show_signature=False, show_name=False, show_date=False),
                signer_user=owner_user_id,
                dry_run=True,
            ),
            {"asset_id": asset.asset_id, "owner_user_id": owner_user_id, "media_type": asset.media_type},
        )
        return asset

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
        if self._service.repository is None:
            raise SignatureTemplateError("signature template storage is not configured")
        normalized = name.strip()
        if not normalized:
            raise SignatureTemplateError("template name is required")
        if signature_asset_id is not None:
            if self._service.secure_store is None:
                raise SignatureTemplateError("secure store is not configured")
            asset = self._service.repository.get_asset(signature_asset_id)
            if asset is None:
                raise SignatureTemplateError(f"unknown signature asset: {signature_asset_id}")
            if scope == "user" and asset.owner_user_id != owner_user_id:
                raise SignatureTemplateError("signature asset ownership mismatch")
        template = UserSignatureTemplate(
            template_id=uuid4().hex,
            owner_user_id=owner_user_id,
            name=normalized,
            placement=placement,
            layout=layout,
            signature_asset_id=signature_asset_id,
            created_at=_utcnow(),
            scope="global" if scope == "global" else "user",
        )
        self._service.repository.upsert_template(template)
        self._service.audit_logger.emit(
            action="signature.template.created",
            actor=owner_user_id,
            target=template.template_id,
            result="ok",
            reason="signature_template_create",
        )
        return template

    def list_user_signature_templates(self, owner_user_id: str) -> list[UserSignatureTemplate]:
        if self._service.repository is None:
            return []
        return self._service.repository.list_templates(owner_user_id)

    def list_global_signature_templates(self) -> list[UserSignatureTemplate]:
        if self._service.repository is None:
            return []
        return self._service.repository.list_global_templates()

    def delete_signature_template(self, template_id: str) -> None:
        if self._service.repository is None:
            raise SignatureTemplateError("signature template storage is not configured")
        self._service.repository.delete_template(template_id)

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
        if self._service.repository is None:
            raise SignatureTemplateError("signature template storage is not configured")
        current = self._service.repository.get_template(template_id)
        if current is None:
            raise SignatureTemplateError(f"unknown signature template: {template_id}")
        if current.owner_user_id != owner_user_id:
            raise SignatureTemplateError("template ownership mismatch")
        if signature_asset_id is not None:
            asset = self._service.repository.get_asset(signature_asset_id)
            if asset is None:
                raise SignatureTemplateError(f"unknown signature asset: {signature_asset_id}")
            if current.scope == "user" and asset.owner_user_id != owner_user_id:
                raise SignatureTemplateError("signature asset ownership mismatch")

        updated = replace(
            current,
            name=(name.strip() if name is not None else current.name),
            placement=placement if placement is not None else current.placement,
            layout=layout if layout is not None else current.layout,
            signature_asset_id=signature_asset_id if signature_asset_id is not None else current.signature_asset_id,
        )
        if not updated.name:
            raise SignatureTemplateError("template name is required")
        self._service.repository.upsert_template(updated)
        self._service.audit_logger.emit(
            action="signature.template.updated",
            actor=owner_user_id,
            target=updated.template_id,
            result="ok",
            reason="signature_template_update",
        )
        return updated

    def copy_global_template_to_user(self, template_id: str, owner_user_id: str, name: str | None = None) -> UserSignatureTemplate:
        if self._service.repository is None:
            raise SignatureTemplateError("signature template storage is not configured")
        source = self._service.repository.get_template(template_id)
        if source is None:
            raise SignatureTemplateError(f"unknown signature template: {template_id}")
        if source.scope != "global":
            raise SignatureTemplateError("template is not global")
        return self.create_user_signature_template(
            owner_user_id=owner_user_id,
            name=name or f"{source.name}-copy",
            placement=source.placement,
            layout=source.layout,
            signature_asset_id=source.signature_asset_id,
            scope="user",
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
        if self._service.repository is None:
            raise SignatureTemplateError("signature template storage is not configured")
        template = self._service.repository.get_template(template_id)
        if template is None:
            raise SignatureTemplateError(f"unknown signature template: {template_id}")
        signature_path: Path | None = None
        tmp_path: Path | None = None
        if template.layout.show_signature:
            asset_id = template.signature_asset_id or self._service.get_active_signature_asset_id(signer_user)
            if not asset_id:
                raise SignatureTemplateError("template requires signature asset but none is linked")
            if self._service.secure_store is None:
                raise SignatureTemplateError("secure store is not configured")
            asset = self._service.repository.get_asset(asset_id)
            if asset is None:
                raise SignatureTemplateError(f"unknown signature asset: {asset_id}")
            blob = self._service.secure_store.get_bytes(asset.storage_key)
            tmp_dir = Path(tempfile.mkdtemp(prefix="qmtool-signature-asset-"))
            tmp_path = tmp_dir
            signature_path = tmp_dir / "signature.png"
            signature_path.write_bytes(blob)
        try:
            return self._service.sign_with_fixed_position(
                SignRequest(
                    input_pdf=input_pdf,
                    output_pdf=output_pdf,
                    signature_png=signature_path,
                    placement=template.placement,
                    layout=template.layout,
                    overwrite_output=overwrite_output,
                    dry_run=dry_run,
                    sign_mode="visual",
                    signer_user=signer_user,
                    password=password,
                    reason=reason,
                )
            )
        finally:
            if tmp_path is not None:
                shutil.rmtree(tmp_path, ignore_errors=True)
