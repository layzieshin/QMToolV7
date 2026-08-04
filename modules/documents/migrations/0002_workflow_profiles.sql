CREATE TABLE IF NOT EXISTS workflow_profile_definitions (
    profile_code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    control_class TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    active_version INTEGER,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_profile_versions (
    profile_version_id TEXT PRIMARY KEY,
    profile_code TEXT NOT NULL,
    version_no INTEGER NOT NULL CHECK (version_no > 0),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('SEED', 'MIGRATED', 'ADMIN')),
    change_reason TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    release_evidence_mode TEXT NOT NULL,
    four_eyes_required INTEGER NOT NULL CHECK (four_eyes_required IN (0, 1)),
    requires_editors INTEGER NOT NULL CHECK (requires_editors IN (0, 1)),
    requires_reviewers INTEGER NOT NULL CHECK (requires_reviewers IN (0, 1)),
    requires_approvers INTEGER NOT NULL CHECK (requires_approvers IN (0, 1)),
    allows_content_changes INTEGER NOT NULL CHECK (allows_content_changes IN (0, 1)),
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    FOREIGN KEY (profile_code) REFERENCES workflow_profile_definitions(profile_code),
    UNIQUE (profile_code, version_no),
    UNIQUE (profile_code, definition_hash)
);

CREATE TABLE IF NOT EXISTS workflow_profile_transitions (
    profile_transition_id TEXT PRIMARY KEY,
    profile_version_id TEXT NOT NULL,
    transition_no INTEGER NOT NULL CHECK (transition_no > 0),
    from_status TEXT NOT NULL CHECK (from_status IN ('DRAFT', 'IN_REVIEW', 'IN_APPROVAL', 'APPROVED')),
    to_status TEXT NOT NULL CHECK (to_status IN ('DRAFT', 'IN_REVIEW', 'IN_APPROVAL', 'APPROVED')),
    required_role TEXT NOT NULL CHECK (required_role IN ('EDITOR', 'REVIEWER', 'APPROVER', 'QMB', 'NONE')),
    decision_policy TEXT NOT NULL CHECK (decision_policy IN ('ONE_OF_POOL', 'ALL_ASSIGNED', 'NONE')),
    signature_required INTEGER NOT NULL CHECK (signature_required IN (0, 1)),
    four_eyes_required INTEGER NOT NULL CHECK (four_eyes_required IN (0, 1)),
    revoke_if_changed INTEGER NOT NULL DEFAULT 0 CHECK (revoke_if_changed IN (0, 1)),
    deadline_seconds INTEGER CHECK (deadline_seconds IS NULL OR deadline_seconds > 0),
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    FOREIGN KEY (profile_version_id) REFERENCES workflow_profile_versions(profile_version_id),
    UNIQUE (profile_version_id, transition_no),
    UNIQUE (profile_version_id, from_status, to_status)
);

CREATE TABLE IF NOT EXISTS document_type_definitions (
    document_type TEXT PRIMARY KEY,
    control_class TEXT NOT NULL,
    default_profile_code TEXT NOT NULL,
    allows_profile_override INTEGER NOT NULL DEFAULT 0 CHECK (allows_profile_override IN (0, 1)),
    binding_source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (default_profile_code)
        REFERENCES workflow_profile_definitions(profile_code)
);

CREATE TABLE IF NOT EXISTS workflow_profile_imports (
    import_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL,
    semantic_sha256 TEXT NOT NULL,
    import_classification TEXT NOT NULL CHECK (import_classification IN ('SEED', 'MIGRATED', 'MIXED')),
    imported_at TEXT NOT NULL,
    report_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_profile_definitions_active
    ON workflow_profile_definitions (is_active, control_class);

CREATE INDEX IF NOT EXISTS idx_workflow_profile_versions_lookup
    ON workflow_profile_versions (profile_code, version_no DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_profile_imports_semantic
    ON workflow_profile_imports (source_path, source_kind, semantic_sha256);

CREATE TRIGGER IF NOT EXISTS trg_workflow_profile_versions_no_update
BEFORE UPDATE ON workflow_profile_versions
BEGIN
    SELECT RAISE(ABORT, 'workflow_profile_versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_workflow_profile_versions_no_delete
BEFORE DELETE ON workflow_profile_versions
BEGIN
    SELECT RAISE(ABORT, 'workflow_profile_versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_workflow_profile_transitions_no_update
BEFORE UPDATE ON workflow_profile_transitions
BEGIN
    SELECT RAISE(ABORT, 'workflow_profile_transitions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_workflow_profile_transitions_no_delete
BEFORE DELETE ON workflow_profile_transitions
BEGIN
    SELECT RAISE(ABORT, 'workflow_profile_transitions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_workflow_profile_definitions_guard
BEFORE UPDATE ON workflow_profile_definitions
FOR EACH ROW
WHEN
    NEW.profile_code != OLD.profile_code
    OR NEW.label != OLD.label
    OR NEW.control_class != OLD.control_class
    OR COALESCE(NEW.created_at, '') != COALESCE(OLD.created_at, '')
    OR COALESCE(NEW.created_by, '') != COALESCE(OLD.created_by, '')
BEGIN
    SELECT RAISE(ABORT, 'workflow_profile_definitions only allow activation updates');
END;
