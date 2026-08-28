-- AP-029 PG01-A: Documents PostgreSQL initial schema (version 1).
-- Applied only by modules.documents.postgres_schema after provision_documents_schema.sql.
-- Do not include BEGIN/COMMIT; the applicator wraps each migration in a transaction.
-- Schema `documents` must already exist and be owned by qmtool_migrator.

CREATE TABLE documents._qm_schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    checksum text NOT NULL,
    schema_fingerprint text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE documents.document_headers (
    document_id text PRIMARY KEY,
    doc_type text NOT NULL,
    control_class text NOT NULL,
    workflow_profile_id text NOT NULL,
    register_binding boolean NOT NULL,
    department text NULL,
    site text NULL,
    regulatory_scope text NULL,
    distribution_roles_json text NOT NULL DEFAULT '[]',
    distribution_sites_json text NOT NULL DEFAULT '[]',
    distribution_departments_json text NOT NULL DEFAULT '[]',
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE documents.document_versions (
    document_id text NOT NULL,
    version integer NOT NULL,
    title text NOT NULL,
    description text NULL,
    doc_type text NOT NULL,
    control_class text NOT NULL,
    workflow_profile_id text NOT NULL,
    owner_user_id text NULL,
    status text NOT NULL,
    workflow_active boolean NOT NULL,
    workflow_profile_json text NULL,
    editors_json text NOT NULL,
    reviewers_json text NOT NULL,
    approvers_json text NOT NULL,
    reviewed_by_json text NOT NULL,
    approved_by_json text NOT NULL,
    edit_signature_done boolean NOT NULL,
    valid_from timestamptz NULL,
    valid_until timestamptz NULL,
    next_review_at timestamptz NULL,
    review_completed_at timestamptz NULL,
    review_completed_by text NULL,
    approval_completed_at timestamptz NULL,
    approval_completed_by text NULL,
    released_at timestamptz NULL,
    archived_at timestamptz NULL,
    archived_by text NULL,
    superseded_by_version integer NULL,
    extension_count integer NOT NULL,
    last_extended_at timestamptz NULL,
    last_extended_by text NULL,
    last_extension_reason text NULL,
    last_extension_review_outcome text NULL,
    custom_fields_json text NOT NULL,
    last_event_id text NULL,
    last_event_at timestamptz NULL,
    last_actor_user_id text NULL,
    created_at timestamptz NULL,
    created_by text NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (document_id, version)
);

CREATE INDEX idx_document_versions_status
    ON documents.document_versions (status);

CREATE UNIQUE INDEX idx_document_versions_one_approved_per_doc
    ON documents.document_versions (document_id)
    WHERE status = 'APPROVED';

CREATE TABLE documents.document_artifacts (
    artifact_id text PRIMARY KEY,
    document_id text NOT NULL,
    version integer NOT NULL,
    artifact_type text NOT NULL,
    source_type text NOT NULL,
    storage_key text NOT NULL,
    original_filename text NOT NULL,
    mime_type text NOT NULL,
    sha256 text NOT NULL,
    size_bytes integer NOT NULL,
    is_current boolean NOT NULL,
    metadata_json text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX idx_document_artifacts_doc_ver
    ON documents.document_artifacts (document_id, version);

CREATE INDEX idx_document_artifacts_type_current
    ON documents.document_artifacts (document_id, version, artifact_type, is_current);

CREATE TABLE documents.document_read_receipts (
    receipt_id text PRIMARY KEY,
    user_id text NOT NULL,
    document_id text NOT NULL,
    version integer NOT NULL,
    confirmed_at timestamptz NOT NULL,
    source text NOT NULL
);

CREATE UNIQUE INDEX idx_document_read_receipts_unique
    ON documents.document_read_receipts (user_id, document_id, version);

CREATE TABLE documents.document_workflow_comments (
    comment_id text PRIMARY KEY,
    ref_no text NOT NULL,
    document_id text NOT NULL,
    version integer NOT NULL,
    context text NOT NULL,
    source_kind text NOT NULL,
    source_comment_key text NOT NULL,
    artifact_id text NULL,
    page_number integer NULL,
    anchor_json text NULL,
    author_display text NULL,
    source_created_at timestamptz NULL,
    preview_text text NOT NULL,
    full_text text NOT NULL,
    status text NOT NULL,
    status_note text NULL,
    status_changed_by text NULL,
    status_changed_at timestamptz NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE UNIQUE INDEX idx_document_workflow_comments_natural
    ON documents.document_workflow_comments (document_id, version, context, source_comment_key);

CREATE INDEX idx_document_workflow_comments_lookup
    ON documents.document_workflow_comments (document_id, version, context, status);

CREATE TABLE documents.document_pdf_read_sessions (
    session_id text PRIMARY KEY,
    user_id text NOT NULL,
    document_id text NOT NULL,
    version integer NOT NULL,
    artifact_id text NULL,
    total_pages integer NOT NULL,
    min_seconds_per_page integer NOT NULL,
    source text NOT NULL,
    opened_at timestamptz NOT NULL,
    completed_at timestamptz NULL,
    completion_result text NULL
);

CREATE TABLE documents.document_pdf_read_page_progress (
    session_id text NOT NULL,
    page_number integer NOT NULL,
    accumulated_seconds integer NOT NULL,
    reached_threshold boolean NOT NULL,
    first_seen_at timestamptz NULL,
    last_seen_at timestamptz NULL,
    PRIMARY KEY (session_id, page_number)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON documents.document_headers TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.document_versions TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.document_artifacts TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.document_read_receipts TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.document_workflow_comments TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.document_pdf_read_sessions TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.document_pdf_read_page_progress TO qmtool_runtime;
