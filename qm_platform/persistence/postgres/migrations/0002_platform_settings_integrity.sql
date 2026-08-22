-- AP-029 PG00-A: Platform settings integrity table and runtime history read grant.
-- Mirrors SQLite V2 platform_settings_integrity semantics.

CREATE TABLE platform.platform_settings_integrity (
    integrity_key text PRIMARY KEY,
    integrity_value text NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL
);

GRANT SELECT, INSERT, UPDATE, DELETE ON platform.platform_settings_integrity TO qmtool_runtime;
REVOKE ALL ON TABLE platform.platform_settings_integrity FROM PUBLIC;

GRANT SELECT ON platform._qm_schema_migrations TO qmtool_runtime;
