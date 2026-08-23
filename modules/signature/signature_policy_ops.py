"""Signature asset/policy operations (SRP split B4).

Manages active signature assets, import, export, and password policy
for replacing/deleting active signatures.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .contracts import LabelLayoutInput, SignatureAsset
from .errors import PasswordInvalidError, PasswordRequiredError, SignatureAssetError
from .secure_store import EncryptedSignatureBlobStore
from .repository import SignatureRepository


def _safe_png_basename(filename_hint: str) -> str:
    raw = str(filename_hint or "").replace("\\", "/").strip()
    if not raw:
        return "canvas.png"
    first = raw.split("/", 1)[0]
    if raw.startswith("/") or raw.startswith("~") or ":" in first:
        return "canvas.png"
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return "canvas.png"
    name = parts[-1]
    stem = Path(name).stem
    safe = "".join(ch for ch in stem if ch.isalnum() or ch in "-_") or "canvas"
    return f"{safe}.png"


@dataclass
class SignaturePolicyOps:
    repository: SignatureRepository | None
    secure_store: EncryptedSignatureBlobStore | None
    password_verifier: Callable[[str, str], bool]

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

    def import_signature_asset_bytes(self, owner_user_id: str, png_bytes: bytes, *, filename_hint: str = "canvas.png", import_fn: Callable | None = None) -> SignatureAsset:
        if self.repository is None or self.secure_store is None:
            raise SignatureAssetError("signature template storage is not configured")
        basename = _safe_png_basename(filename_hint)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp).resolve()
            temp = (tmp_root / basename).resolve()
            if not temp.is_relative_to(tmp_root) or temp.suffix.lower() != ".png":
                raise SignatureAssetError("unsafe signature temp path")
            temp.write_bytes(png_bytes)
            if import_fn is not None:
                return import_fn(owner_user_id, temp)
            raise SignatureAssetError("import_fn is required")

    def import_signature_asset_and_set_active(self, owner_user_id: str, source_path: Path, *, password: str | None = None, import_fn: Callable | None = None) -> SignatureAsset:
        if import_fn is None:
            raise SignatureAssetError("import_fn is required")
        asset = import_fn(owner_user_id, source_path)
        self.set_active_signature_asset(owner_user_id, asset.asset_id, password=password)
        return asset

    def import_signature_asset_bytes_and_set_active(self, owner_user_id: str, png_bytes: bytes, *, filename_hint: str = "canvas.png", password: str | None = None, import_fn: Callable | None = None) -> SignatureAsset:
        asset = self.import_signature_asset_bytes(owner_user_id, png_bytes, filename_hint=filename_hint, import_fn=import_fn)
        self.set_active_signature_asset(owner_user_id, asset.asset_id, password=password)
        return asset

    def resolve_runtime_layout(self, layout: LabelLayoutInput, *, signer_user: str | None = None) -> LabelLayoutInput:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        resolved_name = (signer_user or "") if layout.show_name else layout.name_text
        resolved_date = timestamp if layout.show_date else layout.date_text
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

    def _require_valid_password(self, owner_user_id: str, password: str | None) -> None:
        if not password:
            raise PasswordRequiredError("password required for replacing or deleting active signature")
        if not self.password_verifier(owner_user_id, password):
            raise PasswordInvalidError("password verification failed")

