"""PostgreSQL SignatureRepository implementation for AP-029 PG01-D."""
from __future__ import annotations

from datetime import datetime, timezone

from .contracts import LabelLayoutInput, SignatureAsset, SignaturePlacementInput, UserSignatureTemplate
from .postgres_connection import runtime_connection
from .repository import SignatureRepository


def _coerce_timestamp(value: object | None) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PostgresSignatureRepository(SignatureRepository):
    """Signature metadata persistence through the PG01 runtime privilege contract."""

    def __init__(self, dsn: str) -> None:
        self._dsn = str(dsn)

    def add_asset(self, asset: SignatureAsset) -> None:
        with runtime_connection(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO signature.signature_assets (
                    asset_id, owner_user_id, storage_key, media_type,
                    original_filename, sha256, size_bytes, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    asset.asset_id,
                    asset.owner_user_id,
                    asset.storage_key,
                    asset.media_type,
                    asset.original_filename,
                    asset.sha256,
                    asset.size_bytes,
                    asset.created_at,
                ),
            )
            conn.commit()

    def get_asset(self, asset_id: str) -> SignatureAsset | None:
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                """
                SELECT asset_id, owner_user_id, storage_key, media_type,
                       original_filename, sha256, size_bytes, created_at
                FROM signature.signature_assets
                WHERE asset_id = %s
                """,
                (asset_id,),
            ).fetchone()
        return _row_to_asset(row) if row else None

    def upsert_template(self, template: UserSignatureTemplate) -> None:
        with runtime_connection(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO signature.user_signature_templates (
                    template_id, owner_user_id, name,
                    placement_page_index, placement_x, placement_y, placement_target_width,
                    show_signature, show_name, show_date, name_text, date_text,
                    name_position, date_position, name_font_size, date_font_size, color_hex,
                    name_above, name_below, date_above, date_below, x_offset,
                    name_rel_x, name_rel_y, date_rel_x, date_rel_y,
                    signature_asset_id, scope, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (template_id) DO UPDATE SET
                    owner_user_id = EXCLUDED.owner_user_id,
                    name = EXCLUDED.name,
                    placement_page_index = EXCLUDED.placement_page_index,
                    placement_x = EXCLUDED.placement_x,
                    placement_y = EXCLUDED.placement_y,
                    placement_target_width = EXCLUDED.placement_target_width,
                    show_signature = EXCLUDED.show_signature,
                    show_name = EXCLUDED.show_name,
                    show_date = EXCLUDED.show_date,
                    name_text = EXCLUDED.name_text,
                    date_text = EXCLUDED.date_text,
                    name_position = EXCLUDED.name_position,
                    date_position = EXCLUDED.date_position,
                    name_font_size = EXCLUDED.name_font_size,
                    date_font_size = EXCLUDED.date_font_size,
                    color_hex = EXCLUDED.color_hex,
                    name_above = EXCLUDED.name_above,
                    name_below = EXCLUDED.name_below,
                    date_above = EXCLUDED.date_above,
                    date_below = EXCLUDED.date_below,
                    x_offset = EXCLUDED.x_offset,
                    name_rel_x = EXCLUDED.name_rel_x,
                    name_rel_y = EXCLUDED.name_rel_y,
                    date_rel_x = EXCLUDED.date_rel_x,
                    date_rel_y = EXCLUDED.date_rel_y,
                    signature_asset_id = EXCLUDED.signature_asset_id,
                    scope = EXCLUDED.scope,
                    created_at = EXCLUDED.created_at
                """,
                (
                    template.template_id,
                    template.owner_user_id,
                    template.name,
                    template.placement.page_index,
                    template.placement.x,
                    template.placement.y,
                    template.placement.target_width,
                    bool(template.layout.show_signature),
                    bool(template.layout.show_name),
                    bool(template.layout.show_date),
                    template.layout.name_text,
                    template.layout.date_text,
                    template.layout.name_position,
                    template.layout.date_position,
                    template.layout.name_font_size,
                    template.layout.date_font_size,
                    template.layout.color_hex,
                    template.layout.name_above,
                    template.layout.name_below,
                    template.layout.date_above,
                    template.layout.date_below,
                    template.layout.x_offset,
                    template.layout.name_rel_x,
                    template.layout.name_rel_y,
                    template.layout.date_rel_x,
                    template.layout.date_rel_y,
                    template.signature_asset_id,
                    template.scope,
                    template.created_at,
                ),
            )
            conn.commit()

    def list_templates(self, owner_user_id: str) -> list[UserSignatureTemplate]:
        with runtime_connection(self._dsn) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM signature.user_signature_templates
                WHERE owner_user_id = %s
                ORDER BY name ASC
                """,
                (owner_user_id,),
            ).fetchall()
        return [_row_to_template(row) for row in rows]

    def list_global_templates(self) -> list[UserSignatureTemplate]:
        with runtime_connection(self._dsn) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM signature.user_signature_templates
                WHERE scope = 'global'
                ORDER BY name ASC
                """
            ).fetchall()
        return [_row_to_template(row) for row in rows]

    def get_template(self, template_id: str) -> UserSignatureTemplate | None:
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM signature.user_signature_templates
                WHERE template_id = %s
                """,
                (template_id,),
            ).fetchone()
        return _row_to_template(row) if row else None

    def delete_template(self, template_id: str) -> None:
        with runtime_connection(self._dsn) as conn:
            conn.execute(
                "DELETE FROM signature.user_signature_templates WHERE template_id = %s",
                (template_id,),
            )
            conn.commit()

    def set_active_signature_asset(self, owner_user_id: str, asset_id: str) -> None:
        with runtime_connection(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO signature.user_active_signatures (owner_user_id, asset_id, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (owner_user_id) DO UPDATE SET
                    asset_id = EXCLUDED.asset_id,
                    updated_at = EXCLUDED.updated_at
                """,
                (owner_user_id, asset_id, _utcnow()),
            )
            conn.commit()

    def get_active_signature_asset_id(self, owner_user_id: str) -> str | None:
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                """
                SELECT asset_id
                FROM signature.user_active_signatures
                WHERE owner_user_id = %s
                """,
                (owner_user_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["asset_id"])

    def clear_active_signature_asset(self, owner_user_id: str) -> None:
        with runtime_connection(self._dsn) as conn:
            conn.execute(
                "DELETE FROM signature.user_active_signatures WHERE owner_user_id = %s",
                (owner_user_id,),
            )
            conn.commit()


def _row_to_asset(row: dict[str, object]) -> SignatureAsset:
    return SignatureAsset(
        asset_id=str(row["asset_id"]),
        owner_user_id=str(row["owner_user_id"]),
        storage_key=str(row["storage_key"]),
        media_type=str(row["media_type"]),
        original_filename=str(row["original_filename"]),
        sha256=str(row["sha256"]),
        size_bytes=int(row["size_bytes"]),
        created_at=_coerce_timestamp(row["created_at"]),
    )


def _row_to_template(row: dict[str, object]) -> UserSignatureTemplate:
    return UserSignatureTemplate(
        template_id=str(row["template_id"]),
        owner_user_id=str(row["owner_user_id"]),
        name=str(row["name"]),
        placement=SignaturePlacementInput(
            page_index=int(row["placement_page_index"]),
            x=float(row["placement_x"]),
            y=float(row["placement_y"]),
            target_width=float(row["placement_target_width"]),
        ),
        layout=LabelLayoutInput(
            show_signature=bool(row["show_signature"]),
            show_name=bool(row["show_name"]),
            show_date=bool(row["show_date"]),
            name_text=row["name_text"],  # type: ignore[arg-type]
            date_text=row["date_text"],  # type: ignore[arg-type]
            name_position=str(row["name_position"]),  # type: ignore[arg-type]
            date_position=str(row["date_position"]),  # type: ignore[arg-type]
            name_font_size=int(row["name_font_size"]),
            date_font_size=int(row["date_font_size"]),
            color_hex=str(row["color_hex"]),
            name_above=float(row["name_above"]),
            name_below=float(row["name_below"]),
            date_above=float(row["date_above"]),
            date_below=float(row["date_below"]),
            x_offset=float(row["x_offset"]),
            name_rel_x=float(row["name_rel_x"]) if row.get("name_rel_x") is not None else None,
            name_rel_y=float(row["name_rel_y"]) if row.get("name_rel_y") is not None else None,
            date_rel_x=float(row["date_rel_x"]) if row.get("date_rel_x") is not None else None,
            date_rel_y=float(row["date_rel_y"]) if row.get("date_rel_y") is not None else None,
        ),
        signature_asset_id=row["signature_asset_id"],  # type: ignore[arg-type]
        created_at=_coerce_timestamp(row["created_at"]),
        scope=str(row["scope"]) if row.get("scope") else "user",
    )
