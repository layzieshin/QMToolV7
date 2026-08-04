-- J02: platform settings store (module_global only; no USER scope in this package).
CREATE TABLE IF NOT EXISTS platform_settings (
    scope_kind TEXT NOT NULL CHECK (scope_kind = 'MODULE'),
    scope_id TEXT NOT NULL,
    module_id TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    value_type TEXT NOT NULL,
    value_json TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    updated_at TEXT NOT NULL,
    updated_by_user_id TEXT NOT NULL,
    PRIMARY KEY (scope_kind, scope_id, module_id, setting_key),
    CHECK (scope_id = module_id)
);

CREATE TABLE IF NOT EXISTS platform_setting_revisions (
    revision_id TEXT PRIMARY KEY,
    scope_kind TEXT NOT NULL CHECK (scope_kind = 'MODULE'),
    scope_id TEXT NOT NULL,
    module_id TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    revision_no INTEGER NOT NULL CHECK (revision_no >= 1),
    old_value_json TEXT,
    new_value_json TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    changed_by_user_id TEXT NOT NULL,
    reason TEXT,
    UNIQUE (scope_kind, scope_id, module_id, setting_key, revision_no),
    CHECK (scope_id = module_id)
);
