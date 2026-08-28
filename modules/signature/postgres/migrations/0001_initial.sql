-- AP-029 PG01-A: Signature PostgreSQL initial schema (version 1).
-- Applied only by modules.signature.postgres_schema after provision_signature_schema.sql.
-- Do not include BEGIN/COMMIT; the applicator wraps each migration in a transaction.
-- Schema `signature` must already exist and be owned by qmtool_migrator.

CREATE TABLE signature._qm_schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    checksum text NOT NULL,
    schema_fingerprint text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE signature.signature_assets (
    asset_id text PRIMARY KEY,
    owner_user_id text NOT NULL,
    storage_key text NOT NULL,
    media_type text NOT NULL,
    original_filename text NOT NULL,
    sha256 text NOT NULL,
    size_bytes integer NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE signature.user_signature_templates (
    template_id text PRIMARY KEY,
    owner_user_id text NOT NULL,
    name text NOT NULL,
    placement_page_index integer NOT NULL,
    placement_x double precision NOT NULL,
    placement_y double precision NOT NULL,
    placement_target_width double precision NOT NULL,
    show_signature boolean NOT NULL,
    show_name boolean NOT NULL,
    show_date boolean NOT NULL,
    name_text text NULL,
    date_text text NULL,
    name_position text NOT NULL,
    date_position text NOT NULL,
    name_font_size integer NOT NULL,
    date_font_size integer NOT NULL,
    color_hex text NOT NULL,
    name_above double precision NOT NULL,
    name_below double precision NOT NULL,
    date_above double precision NOT NULL,
    date_below double precision NOT NULL,
    x_offset double precision NOT NULL,
    name_rel_x double precision NULL,
    name_rel_y double precision NULL,
    date_rel_x double precision NULL,
    date_rel_y double precision NULL,
    signature_asset_id text NULL,
    scope text NOT NULL DEFAULT 'user',
    created_at timestamptz NOT NULL
);

CREATE TABLE signature.user_active_signatures (
    owner_user_id text PRIMARY KEY,
    asset_id text NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX idx_signature_assets_owner
    ON signature.signature_assets (owner_user_id);

CREATE INDEX idx_signature_templates_owner
    ON signature.user_signature_templates (owner_user_id);

CREATE INDEX idx_signature_templates_scope
    ON signature.user_signature_templates (scope);

GRANT SELECT, INSERT, UPDATE, DELETE ON signature.signature_assets TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON signature.user_signature_templates TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON signature.user_active_signatures TO qmtool_runtime;
