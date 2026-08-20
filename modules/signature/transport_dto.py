"""JSON DTO helpers for signature HTTP boundaries (J04-M0-P3B)."""
from __future__ import annotations

from typing import Any

from .contracts import LabelLayoutInput, SignatureAsset, SignaturePlacementInput, UserSignatureTemplate


def placement_to_payload(placement: SignaturePlacementInput) -> dict[str, Any]:
    return {
        "page_index": placement.page_index,
        "x": placement.x,
        "y": placement.y,
        "target_width": placement.target_width,
    }


def placement_from_payload(data: dict[str, Any]) -> SignaturePlacementInput:
    return SignaturePlacementInput(
        page_index=int(data["page_index"]),
        x=float(data["x"]),
        y=float(data["y"]),
        target_width=float(data["target_width"]),
    )


def layout_to_payload(layout: LabelLayoutInput) -> dict[str, Any]:
    return {
        "show_signature": layout.show_signature,
        "show_name": layout.show_name,
        "show_date": layout.show_date,
        "name_text": layout.name_text,
        "date_text": layout.date_text,
        "name_position": layout.name_position,
        "date_position": layout.date_position,
        "name_font_size": layout.name_font_size,
        "date_font_size": layout.date_font_size,
        "color_hex": layout.color_hex,
        "name_above": layout.name_above,
        "name_below": layout.name_below,
        "date_above": layout.date_above,
        "date_below": layout.date_below,
        "x_offset": layout.x_offset,
        "name_rel_x": layout.name_rel_x,
        "name_rel_y": layout.name_rel_y,
        "date_rel_x": layout.date_rel_x,
        "date_rel_y": layout.date_rel_y,
    }


def layout_from_payload(data: dict[str, Any]) -> LabelLayoutInput:
    return LabelLayoutInput(
        show_signature=bool(data.get("show_signature", True)),
        show_name=bool(data.get("show_name", True)),
        show_date=bool(data.get("show_date", True)),
        name_text=data.get("name_text"),
        date_text=data.get("date_text"),
        name_position=data.get("name_position", "above"),
        date_position=data.get("date_position", "below"),
        name_font_size=int(data.get("name_font_size", 12)),
        date_font_size=int(data.get("date_font_size", 12)),
        color_hex=str(data.get("color_hex", "#000000")),
        name_above=float(data.get("name_above", 6.0)),
        name_below=float(data.get("name_below", 12.0)),
        date_above=float(data.get("date_above", 18.0)),
        date_below=float(data.get("date_below", 24.0)),
        x_offset=float(data.get("x_offset", 0.0)),
        name_rel_x=data.get("name_rel_x"),
        name_rel_y=data.get("name_rel_y"),
        date_rel_x=data.get("date_rel_x"),
        date_rel_y=data.get("date_rel_y"),
    )


def asset_to_payload(asset: SignatureAsset) -> dict[str, Any]:
    return {
        "asset_id": asset.asset_id,
        "owner_user_id": asset.owner_user_id,
        "media_type": asset.media_type,
        "original_filename": asset.original_filename,
        "sha256": asset.sha256,
        "size_bytes": asset.size_bytes,
        "created_at": asset.created_at.isoformat(),
    }


def template_to_payload(template: UserSignatureTemplate) -> dict[str, Any]:
    return {
        "template_id": template.template_id,
        "owner_user_id": template.owner_user_id,
        "name": template.name,
        "placement": placement_to_payload(template.placement),
        "layout": layout_to_payload(template.layout),
        "signature_asset_id": template.signature_asset_id,
        "created_at": template.created_at.isoformat(),
        "scope": template.scope,
    }
