from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .contracts import LabelLayoutInput, SignatureAsset, SignaturePlacementInput, UserSignatureTemplate


class SQLiteSignatureRepository:
    def __init__(self, db_path: Path, schema_path: Path) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def add_asset(self, asset: SignatureAsset) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO signature_assets
                (asset_id, owner_user_id, storage_key, media_type, original_filename, sha256, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset.asset_id,
                    asset.owner_user_id,
                    asset.storage_key,
                    asset.media_type,
                    asset.original_filename,
                    asset.sha256,
                    asset.size_bytes,
                    asset.created_at.isoformat(),
                ),
            )
            conn.commit()

    def get_asset(self, asset_id: str) -> SignatureAsset | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM signature_assets WHERE asset_id = ?", (asset_id,)).fetchone()
        if row is None:
            return None
        return SignatureAsset(
            asset_id=str(row["asset_id"]),
            owner_user_id=str(row["owner_user_id"]),
            storage_key=str(row["storage_key"]),
            media_type=str(row["media_type"]),
            original_filename=str(row["original_filename"]),
            sha256=str(row["sha256"]),
            size_bytes=int(row["size_bytes"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    def upsert_template(self, template: UserSignatureTemplate) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_signature_templates
                (
                    template_id, owner_user_id, name,
                    placement_page_index, placement_x, placement_y, placement_target_width,
                    show_signature, show_name, show_date, name_text, date_text,
                    name_position, date_position, name_font_size, date_font_size, color_hex,
                    name_above, name_below, date_above, date_below, x_offset,
                    name_rel_x, name_rel_y, date_rel_x, date_rel_y,
                    signature_asset_id, scope, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.template_id,
                    template.owner_user_id,
                    template.name,
                    template.placement.page_index,
                    template.placement.x,
                    template.placement.y,
                    template.placement.target_width,
                    1 if template.layout.show_signature else 0,
                    1 if template.layout.show_name else 0,
                    1 if template.layout.show_date else 0,
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
                    template.created_at.isoformat(),
                ),
            )
            conn.commit()

    def list_templates(self, owner_user_id: str) -> list[UserSignatureTemplate]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM user_signature_templates WHERE owner_user_id = ? ORDER BY name ASC",
                (owner_user_id,),
            ).fetchall()
        return [self._row_to_template(r) for r in rows]

    def list_global_templates(self) -> list[UserSignatureTemplate]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM user_signature_templates WHERE scope = 'global' ORDER BY name ASC"
            ).fetchall()
        return [self._row_to_template(r) for r in rows]

    def get_template(self, template_id: str) -> UserSignatureTemplate | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM user_signature_templates WHERE template_id = ?", (template_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_template(row)

    def delete_template(self, template_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM user_signature_templates WHERE template_id = ?", (template_id,))
            conn.commit()

    def set_active_signature_asset(self, owner_user_id: str, asset_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_active_signatures (owner_user_id, asset_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(owner_user_id) DO UPDATE SET
                    asset_id = excluded.asset_id,
                    updated_at = excluded.updated_at
                """,
                (owner_user_id, asset_id, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_active_signature_asset_id(self, owner_user_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT asset_id FROM user_active_signatures WHERE owner_user_id = ?",
                (owner_user_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["asset_id"])

    def clear_active_signature_asset(self, owner_user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM user_active_signatures WHERE owner_user_id = ?", (owner_user_id,))
            conn.commit()

    def _row_to_template(self, row: sqlite3.Row) -> UserSignatureTemplate:
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
                name_text=row["name_text"],
                date_text=row["date_text"],
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
                name_rel_x=float(row["name_rel_x"]) if "name_rel_x" in row.keys() and row["name_rel_x"] is not None else None,
                name_rel_y=float(row["name_rel_y"]) if "name_rel_y" in row.keys() and row["name_rel_y"] is not None else None,
                date_rel_x=float(row["date_rel_x"]) if "date_rel_x" in row.keys() and row["date_rel_x"] is not None else None,
                date_rel_y=float(row["date_rel_y"]) if "date_rel_y" in row.keys() and row["date_rel_y"] is not None else None,
            ),
            signature_asset_id=row["signature_asset_id"],
            created_at=datetime.fromisoformat(str(row["created_at"])),
            scope=str(row["scope"]) if "scope" in row.keys() and row["scope"] else "user",
        )

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            self._ensure_migration_columns(conn)
            conn.commit()

    @staticmethod
    def _ensure_migration_columns(conn: sqlite3.Connection) -> None:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(user_signature_templates)").fetchall()}
        add_specs = [
            ("name_rel_x", "REAL"),
            ("name_rel_y", "REAL"),
            ("date_rel_x", "REAL"),
            ("date_rel_y", "REAL"),
            ("scope", "TEXT NOT NULL DEFAULT 'user'"),
        ]
        for col_name, sql_type in add_specs:
            if col_name not in cols:
                conn.execute(f"ALTER TABLE user_signature_templates ADD COLUMN {col_name} {sql_type}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signature_templates_scope ON user_signature_templates(scope)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
