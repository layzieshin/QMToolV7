-- Training module schema – clean-slate (§4, §12.3)

-- Tags
CREATE TABLE IF NOT EXISTS training_document_tags (
    document_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (document_id, tag)
);

CREATE TABLE IF NOT EXISTS training_user_tags (
    user_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (user_id, tag)
);

-- Overrides
CREATE TABLE IF NOT EXISTS training_manual_assignments (
    assignment_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    granted_by TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS training_exemptions (
    exemption_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    reason TEXT NOT NULL,
    granted_by TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    valid_until TEXT,
    revoked_at TEXT
);

-- Snapshots
CREATE TABLE IF NOT EXISTS training_assignment_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    source TEXT NOT NULL,
    exempted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshot_user_doc_ver
    ON training_assignment_snapshots (user_id, document_id, version);

CREATE TABLE IF NOT EXISTS training_progress (
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    read_confirmed_at TEXT,
    quiz_passed_at TEXT,
    last_score INTEGER,
    quiz_attempts_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, document_id, version)
);

-- Quiz
CREATE TABLE IF NOT EXISTS training_quiz_imports (
    import_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    document_version INTEGER NOT NULL,
    storage_key TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    question_count INTEGER NOT NULL,
    auto_bound INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS training_quiz_bindings (
    binding_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    import_id TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    replaced_at TEXT,
    replaced_by TEXT
);

CREATE TABLE IF NOT EXISTS training_quiz_replacement_history (
    history_id TEXT PRIMARY KEY,
    old_binding_id TEXT NOT NULL,
    new_binding_id TEXT NOT NULL,
    confirmed_by TEXT NOT NULL,
    confirmed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS training_quiz_attempts (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    selected_question_ids_json TEXT NOT NULL,
    answers_json TEXT,
    score INTEGER,
    total INTEGER,
    passed INTEGER,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

-- Comments
CREATE TABLE IF NOT EXISTS training_comments (
    comment_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    document_title_snapshot TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL,
    username_snapshot TEXT NOT NULL DEFAULT '',
    comment_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_by TEXT,
    resolved_at TEXT,
    resolution_note TEXT,
    inactive_by TEXT,
    inactive_at TEXT,
    inactive_note TEXT
);

-- Audit
CREATE TABLE IF NOT EXISTS training_audit_log (
    log_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);
