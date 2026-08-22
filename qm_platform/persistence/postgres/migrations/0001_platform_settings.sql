-- AP-029 PG00-A: Platform PostgreSQL initial schema (version 1).
-- Applied only by qm_platform.persistence.postgres_schema after provision_platform_schema.sql.
-- Schema `platform` must already exist and be owned by qmtool_migrator.
-- Do not include BEGIN/COMMIT; the applicator wraps each migration in a transaction.

CREATE TABLE platform._qm_schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    checksum text NOT NULL,
    schema_fingerprint text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE platform.platform_settings (
    scope_kind text NOT NULL,
    scope_id text NOT NULL,
    module_id text NOT NULL,
    setting_key text NOT NULL,
    value_type text NOT NULL,
    value_json text NOT NULL,
    schema_version integer NOT NULL,
    revision integer NOT NULL,
    updated_at text NOT NULL,
    updated_by_user_id text NOT NULL,
    PRIMARY KEY (scope_kind, scope_id, module_id, setting_key),
    CONSTRAINT platform_settings_scope_kind_module
        CHECK (scope_kind = 'MODULE'),
    CONSTRAINT platform_settings_scope_id_matches_module
        CHECK (scope_id = module_id),
    CONSTRAINT platform_settings_revision_positive
        CHECK (revision >= 1)
);

CREATE TABLE platform.platform_setting_revisions (
    revision_id text PRIMARY KEY,
    scope_kind text NOT NULL,
    scope_id text NOT NULL,
    module_id text NOT NULL,
    setting_key text NOT NULL,
    revision_no integer NOT NULL,
    old_value_json text,
    new_value_json text NOT NULL,
    changed_at text NOT NULL,
    changed_by_user_id text NOT NULL,
    reason text,
    UNIQUE (scope_kind, scope_id, module_id, setting_key, revision_no),
    CONSTRAINT platform_setting_revisions_scope_kind_module
        CHECK (scope_kind = 'MODULE'),
    CONSTRAINT platform_setting_revisions_scope_id_matches_module
        CHECK (scope_id = module_id),
    CONSTRAINT platform_setting_revisions_revision_positive
        CHECK (revision_no >= 1)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON platform.platform_settings TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON platform.platform_setting_revisions TO qmtool_runtime;
REVOKE ALL ON TABLE platform.platform_settings FROM PUBLIC;
REVOKE ALL ON TABLE platform.platform_setting_revisions FROM PUBLIC;
