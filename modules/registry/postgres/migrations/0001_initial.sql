-- AP-029 PG01-A: Registry PostgreSQL initial schema (version 1).
-- Applied only by modules.registry.postgres_schema after provision_registry_schema.sql.
-- Do not include BEGIN/COMMIT; the applicator wraps each migration in a transaction.
-- Schema `registry` must already exist and be owned by qmtool_migrator.

CREATE TABLE registry._qm_schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    checksum text NOT NULL,
    schema_fingerprint text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE registry.document_registry (
    document_id text PRIMARY KEY,
    active_version integer NULL,
    release_note text NULL,
    release_evidence_mode text NOT NULL,
    register_state text NOT NULL,
    is_findable boolean NOT NULL,
    valid_from timestamptz NULL,
    valid_until timestamptz NULL,
    last_update_event_id text NOT NULL,
    last_update_at timestamptz NOT NULL
);

CREATE INDEX idx_document_registry_state
    ON registry.document_registry (register_state, is_findable);

GRANT SELECT, INSERT, UPDATE, DELETE ON registry.document_registry TO qmtool_runtime;
