-- User management database schema V2: deactivated_at parity with PostgreSQL.
ALTER TABLE users ADD COLUMN deactivated_at TEXT;
