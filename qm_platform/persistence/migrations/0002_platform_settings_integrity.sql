-- J02: DB-anchored residual integrity and cutover completion marker.
CREATE TABLE IF NOT EXISTS platform_settings_integrity (
    integrity_key TEXT PRIMARY KEY,
    integrity_value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL
);
