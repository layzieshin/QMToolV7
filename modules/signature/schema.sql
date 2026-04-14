CREATE TABLE IF NOT EXISTS signature_assets (
    asset_id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    media_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_signature_templates (
    template_id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    placement_page_index INTEGER NOT NULL,
    placement_x REAL NOT NULL,
    placement_y REAL NOT NULL,
    placement_target_width REAL NOT NULL,
    show_signature INTEGER NOT NULL,
    show_name INTEGER NOT NULL,
    show_date INTEGER NOT NULL,
    name_text TEXT,
    date_text TEXT,
    name_position TEXT NOT NULL,
    date_position TEXT NOT NULL,
    name_font_size INTEGER NOT NULL,
    date_font_size INTEGER NOT NULL,
    color_hex TEXT NOT NULL,
    name_above REAL NOT NULL,
    name_below REAL NOT NULL,
    date_above REAL NOT NULL,
    date_below REAL NOT NULL,
    x_offset REAL NOT NULL,
    name_rel_x REAL,
    name_rel_y REAL,
    date_rel_x REAL,
    date_rel_y REAL,
    signature_asset_id TEXT,
    scope TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signature_assets_owner ON signature_assets(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_signature_templates_owner ON user_signature_templates(owner_user_id);

CREATE TABLE IF NOT EXISTS user_active_signatures (
    owner_user_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
