-- incident_management module schema (V1)

CREATE TABLE IF NOT EXISTS incident_id_counters (
    report_date TEXT PRIMARY KEY,
    next_seq INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    reporter_user_id TEXT NOT NULL,
    reported_at TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    labels_json TEXT NOT NULL DEFAULT '[]',
    area TEXT,
    process_name TEXT,
    device TEXT,
    classification TEXT,
    is_critical INTEGER,
    criticality_reason TEXT,
    is_repeated INTEGER,
    capa_required INTEGER,
    capa_reason TEXT,
    root_cause_required INTEGER,
    group_id TEXT,
    leadership_required INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    closed_at TEXT,
    archived_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_reported_at ON incidents(reported_at);
CREATE INDEX IF NOT EXISTS idx_incidents_category ON incidents(category);

CREATE TABLE IF NOT EXISTS incident_timeline (
    entry_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    actor_user_id TEXT,
    summary TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS incident_inquiries (
    inquiry_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT,
    asked_by_user_id TEXT NOT NULL,
    answered_by_user_id TEXT,
    asked_at TEXT NOT NULL,
    answered_at TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS incident_actions (
    action_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    description TEXT NOT NULL,
    owner_user_id TEXT,
    due_at TEXT,
    completed_at TEXT,
    completed_by_user_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS incident_capas (
    capa_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    status TEXT NOT NULL,
    trigger_reason TEXT,
    goal TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS root_cause_analyses (
    rca_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    immediate_event TEXT,
    trigger TEXT,
    root_causes TEXT,
    similar_prior TEXT,
    systemic_weakness TEXT,
    future_risk TEXT,
    method TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS effectiveness_reviews (
    review_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    planned_at TEXT NOT NULL,
    criteria TEXT NOT NULL,
    completed_at TEXT,
    completed_by_user_id TEXT,
    result TEXT,
    effective INTEGER,
    notes TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS incident_artifacts (
    artifact_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT,
    sha256 TEXT,
    size_bytes INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS incident_groups (
    group_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_by_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leadership_acknowledgements (
    ack_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    forwarded_by_user_id TEXT NOT NULL,
    forwarded_at TEXT NOT NULL,
    leadership_user_id TEXT NOT NULL,
    comment TEXT,
    acknowledged_at TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS management_review_batches (
    batch_id TEXT PRIMARY KEY,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    report_storage_key TEXT
);

CREATE TABLE IF NOT EXISTS management_review_items (
    item_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    status TEXT NOT NULL,
    acknowledged_at TEXT,
    acknowledged_by_user_id TEXT,
    FOREIGN KEY (batch_id) REFERENCES management_review_batches(batch_id),
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS module_role_assignments (
    assignment_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    role_name TEXT NOT NULL,
    assigned_by_user_id TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    UNIQUE(user_id, role_name)
);
