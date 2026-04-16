from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from datetime import datetime

from .errors import SignatureError  # noqa: F401 - public re-export for adapters


SignMode = Literal["visual", "crypto", "both"]
TextPosition = Literal["above", "below", "off"]
TemplateScope = Literal["user", "global"]


@dataclass(frozen=True)
class SignaturePlacementInput:
    page_index: int
    x: float
    y: float
    target_width: float


@dataclass(frozen=True)
class LabelLayoutInput:
    show_signature: bool = True
    show_name: bool = True
    show_date: bool = True
    name_text: str | None = None
    date_text: str | None = None
    name_position: TextPosition = "above"
    date_position: TextPosition = "below"
    name_font_size: int = 12
    date_font_size: int = 12
    color_hex: str = "#000000"
    name_above: float = 6.0
    name_below: float = 12.0
    date_above: float = 18.0
    date_below: float = 24.0
    x_offset: float = 0.0
    # Optional fine-grained relative offsets (preferred when set).
    name_rel_x: float | None = None
    name_rel_y: float | None = None
    date_rel_x: float | None = None
    date_rel_y: float | None = None


@dataclass(frozen=True)
class SignRequest:
    input_pdf: Path
    placement: SignaturePlacementInput
    layout: LabelLayoutInput
    signature_png: Path | None = None
    output_pdf: Path | None = None
    overwrite_output: bool = False
    dry_run: bool = False
    sign_mode: SignMode = "visual"
    signer_user: str | None = None
    password: str | None = None
    reason: str = "api"


@dataclass(frozen=True)
class SignResult:
    output_pdf: Path
    signed: bool
    sha256: str
    dry_run: bool
    mode: SignMode


@dataclass(frozen=True)
class SignatureAsset:
    asset_id: str
    owner_user_id: str
    storage_key: str
    media_type: str
    original_filename: str
    sha256: str
    size_bytes: int
    created_at: datetime


@dataclass(frozen=True)
class UserSignatureTemplate:
    template_id: str
    owner_user_id: str
    name: str
    placement: SignaturePlacementInput
    layout: LabelLayoutInput
    signature_asset_id: str | None
    created_at: datetime
    scope: TemplateScope = "user"

