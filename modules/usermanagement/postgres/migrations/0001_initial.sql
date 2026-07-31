-- AP-028 M3: Usermanagement PostgreSQL initial schema (version 1).
-- Applied only by modules.usermanagement.postgres_schema after provision_roles.sql.
-- UUID primary keys are supplied by the application (no DB defaults).
-- Do not include BEGIN/COMMIT; the applicator wraps each migration in a transaction.
-- Schema `usermanagement` must already exist and be owned by qmtool_migrator.

CREATE TABLE usermanagement._qm_schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    checksum text NOT NULL,
    schema_fingerprint text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE usermanagement.users (
    user_id uuid PRIMARY KEY,
    username text NOT NULL,
    password_hash text NOT NULL,
    role text NOT NULL,
    first_name text NULL,
    last_name text NULL,
    display_name text NULL,
    email text NULL,
    department text NULL,
    scope text NULL,
    organization_unit text NULL,
    is_active boolean NOT NULL DEFAULT true,
    deactivated_at timestamptz NULL,
    is_qmb boolean NOT NULL DEFAULT false,
    must_change_password boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    -- Active users must not carry a deactivation timestamp.
    -- Inactive rows may keep deactivated_at NULL (= historical unknown); M8 must not invent one.
    CONSTRAINT users_active_requires_null_deactivated_at
        CHECK (is_active = false OR deactivated_at IS NULL)
);

CREATE UNIQUE INDEX users_username_lower_uidx
    ON usermanagement.users (lower(username));

CREATE TABLE usermanagement.sessions (
    session_id uuid PRIMARY KEY,
    token_hash text NOT NULL UNIQUE,
    user_id uuid NOT NULL
        REFERENCES usermanagement.users (user_id)
        ON DELETE RESTRICT,
    created_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz NULL,
    client_type text NOT NULL,
    authentication_level text NOT NULL DEFAULT 'password',
    CONSTRAINT sessions_expires_after_created
        CHECK (expires_at > created_at),
    CONSTRAINT sessions_last_seen_after_created
        CHECK (last_seen_at >= created_at),
    CONSTRAINT sessions_revoked_after_created
        CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);

CREATE INDEX sessions_user_id_idx
    ON usermanagement.sessions (user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON usermanagement.users TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON usermanagement.sessions TO qmtool_runtime;
