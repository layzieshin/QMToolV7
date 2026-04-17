CREATE TABLE IF NOT EXISTS document_headers (
    document_id TEXT PRIMARY KEY,
    doc_type TEXT NOT NULL,
    control_class TEXT NOT NULL,
    workflow_profile_id TEXT NOT NULL,
    register_binding INTEGER NOT NULL,
    department TEXT,
    site TEXT,
    regulatory_scope TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_versions (
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    doc_type TEXT NOT NULL,
    control_class TEXT NOT NULL,
    workflow_profile_id TEXT NOT NULL,
    owner_user_id TEXT,
    status TEXT NOT NULL,
    workflow_active INTEGER NOT NULL,
    workflow_profile_json TEXT,
    editors_json TEXT NOT NULL,
    reviewers_json TEXT NOT NULL,
    approvers_json TEXT NOT NULL,
    reviewed_by_json TEXT NOT NULL,
    approved_by_json TEXT NOT NULL,
    edit_signature_done INTEGER NOT NULL,
    valid_from TEXT,
    valid_until TEXT,
    next_review_at TEXT,
    review_completed_at TEXT,
    review_completed_by TEXT,
    approval_completed_at TEXT,
    approval_completed_by TEXT,
    released_at TEXT,
    archived_at TEXT,
    archived_by TEXT,
    superseded_by_version INTEGER,
    extension_count INTEGER NOT NULL,
    custom_fields_json TEXT NOT NULL,
    last_event_id TEXT,
    last_event_at TEXT,
    last_actor_user_id TEXT,
    created_at TEXT,
    created_by TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (document_id, version)
);

CREATE INDEX IF NOT EXISTS idx_document_versions_status
    ON document_versions (status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_versions_one_approved_per_doc
    ON document_versions (document_id)
    WHERE status = 'APPROVED';

CREATE TABLE IF NOT EXISTS document_artifacts (
    artifact_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    artifact_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    is_current INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_document_artifacts_doc_ver
    ON document_artifacts (document_id, version);

CREATE INDEX IF NOT EXISTS idx_document_artifacts_type_current
    ON document_artifacts (document_id, version, artifact_type, is_current);

CREATE TABLE IF NOT EXISTS document_read_receipts (
    receipt_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    confirmed_at TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_read_receipts_unique
    ON document_read_receipts (user_id, document_id, version);

CREATE TABLE IF NOT EXISTS document_workflow_comments (
    comment_id TEXT PRIMARY KEY,
    ref_no TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    context TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_comment_key TEXT NOT NULL,
    artifact_id TEXT,
    page_number INTEGER,
    anchor_json TEXT,
    author_display TEXT,
    source_created_at TEXT,
    preview_text TEXT NOT NULL,
    full_text TEXT NOT NULL,
    status TEXT NOT NULL,
    status_note TEXT,
    status_changed_by TEXT,
    status_changed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_workflow_comments_natural
ON document_workflow_comments (document_id, version, context, source_comment_key);

CREATE INDEX IF NOT EXISTS idx_document_workflow_comments_lookup
ON document_workflow_comments (document_id, version, context, status);

CREATE TABLE IF NOT EXISTS document_pdf_read_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    artifact_id TEXT,
    total_pages INTEGER NOT NULL,
    min_seconds_per_page INTEGER NOT NULL,
    source TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    completed_at TEXT,
    completion_result TEXT
);

CREATE TABLE IF NOT EXISTS document_pdf_read_page_progress (
    session_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    accumulated_seconds INTEGER NOT NULL,
    reached_threshold INTEGER NOT NULL,
    first_seen_at TEXT,
    last_seen_at TEXT,
    PRIMARY KEY (session_id, page_number)
);

