-- AP-029 PG01-A: Documents workflow profile PostgreSQL schema (version 2).
-- Applied only by modules.documents.postgres_schema after 0001_initial.sql.
-- Do not include BEGIN/COMMIT; the applicator wraps each migration in a transaction.

CREATE TABLE documents.workflow_profile_definitions (
    profile_code text PRIMARY KEY,
    label text NOT NULL,
    control_class text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    active_version integer NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL
);

CREATE TABLE documents.workflow_profile_versions (
    profile_version_id text PRIMARY KEY,
    profile_code text NOT NULL
        REFERENCES documents.workflow_profile_definitions (profile_code),
    version_no integer NOT NULL,
    source_kind text NOT NULL,
    change_reason text NOT NULL,
    definition_hash text NOT NULL,
    effective_from timestamptz NOT NULL,
    release_evidence_mode text NOT NULL,
    four_eyes_required boolean NOT NULL,
    requires_editors boolean NOT NULL,
    requires_reviewers boolean NOT NULL,
    requires_approvers boolean NOT NULL,
    allows_content_changes boolean NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    CONSTRAINT workflow_profile_versions_version_no_positive CHECK (version_no > 0),
    CONSTRAINT workflow_profile_versions_source_kind_known
        CHECK (source_kind IN ('SEED', 'MIGRATED', 'ADMIN')),
    UNIQUE (profile_code, version_no),
    UNIQUE (profile_code, definition_hash)
);

CREATE TABLE documents.workflow_profile_transitions (
    profile_transition_id text PRIMARY KEY,
    profile_version_id text NOT NULL
        REFERENCES documents.workflow_profile_versions (profile_version_id),
    transition_no integer NOT NULL,
    from_status text NOT NULL,
    to_status text NOT NULL,
    required_role text NOT NULL,
    decision_policy text NOT NULL,
    signature_required boolean NOT NULL,
    four_eyes_required boolean NOT NULL,
    revoke_if_changed boolean NOT NULL DEFAULT false,
    deadline_seconds integer NULL,
    is_enabled boolean NOT NULL DEFAULT true,
    CONSTRAINT workflow_profile_transitions_transition_no_positive CHECK (transition_no > 0),
    CONSTRAINT workflow_profile_transitions_from_status_known
        CHECK (from_status IN ('DRAFT', 'IN_REVIEW', 'IN_APPROVAL', 'APPROVED')),
    CONSTRAINT workflow_profile_transitions_to_status_known
        CHECK (to_status IN ('DRAFT', 'IN_REVIEW', 'IN_APPROVAL', 'APPROVED')),
    CONSTRAINT workflow_profile_transitions_required_role_known
        CHECK (required_role IN ('EDITOR', 'REVIEWER', 'APPROVER', 'QMB', 'NONE')),
    CONSTRAINT workflow_profile_transitions_decision_policy_known
        CHECK (decision_policy IN ('ONE_OF_POOL', 'ALL_ASSIGNED', 'NONE')),
    CONSTRAINT workflow_profile_transitions_revoke_if_changed_bool
        CHECK (revoke_if_changed IN (true, false)),
    CONSTRAINT workflow_profile_transitions_deadline_positive
        CHECK (deadline_seconds IS NULL OR deadline_seconds > 0),
    UNIQUE (profile_version_id, transition_no),
    UNIQUE (profile_version_id, from_status, to_status)
);

CREATE TABLE documents.document_type_definitions (
    document_type text PRIMARY KEY,
    control_class text NOT NULL,
    default_profile_code text NOT NULL
        REFERENCES documents.workflow_profile_definitions (profile_code),
    allows_profile_override boolean NOT NULL DEFAULT false,
    binding_source text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE documents.workflow_profile_imports (
    import_id text PRIMARY KEY,
    source_path text NOT NULL,
    source_kind text NOT NULL,
    raw_sha256 text NOT NULL,
    semantic_sha256 text NOT NULL,
    import_classification text NOT NULL,
    imported_at timestamptz NOT NULL,
    report_json text NOT NULL,
    CONSTRAINT workflow_profile_imports_classification_known
        CHECK (import_classification IN ('SEED', 'MIGRATED', 'MIXED'))
);

CREATE INDEX idx_workflow_profile_definitions_active
    ON documents.workflow_profile_definitions (is_active, control_class);

CREATE INDEX idx_workflow_profile_versions_lookup
    ON documents.workflow_profile_versions (profile_code, version_no DESC);

CREATE UNIQUE INDEX idx_workflow_profile_imports_semantic
    ON documents.workflow_profile_imports (source_path, source_kind, semantic_sha256);

CREATE OR REPLACE FUNCTION documents.deny_workflow_profile_versions_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'workflow_profile_versions are immutable';
END;
$$;

CREATE TRIGGER trg_workflow_profile_versions_no_update
BEFORE UPDATE ON documents.workflow_profile_versions
FOR EACH ROW
EXECUTE FUNCTION documents.deny_workflow_profile_versions_mutation();

CREATE TRIGGER trg_workflow_profile_versions_no_delete
BEFORE DELETE ON documents.workflow_profile_versions
FOR EACH ROW
EXECUTE FUNCTION documents.deny_workflow_profile_versions_mutation();

CREATE OR REPLACE FUNCTION documents.deny_workflow_profile_transitions_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'workflow_profile_transitions are immutable';
END;
$$;

CREATE TRIGGER trg_workflow_profile_transitions_no_update
BEFORE UPDATE ON documents.workflow_profile_transitions
FOR EACH ROW
EXECUTE FUNCTION documents.deny_workflow_profile_transitions_mutation();

CREATE TRIGGER trg_workflow_profile_transitions_no_delete
BEFORE DELETE ON documents.workflow_profile_transitions
FOR EACH ROW
EXECUTE FUNCTION documents.deny_workflow_profile_transitions_mutation();

CREATE OR REPLACE FUNCTION documents.guard_workflow_profile_definitions_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.profile_code IS DISTINCT FROM OLD.profile_code
       OR NEW.label IS DISTINCT FROM OLD.label
       OR NEW.control_class IS DISTINCT FROM OLD.control_class
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN
        RAISE EXCEPTION 'workflow_profile_definitions only allow activation updates';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_workflow_profile_definitions_guard
BEFORE UPDATE ON documents.workflow_profile_definitions
FOR EACH ROW
EXECUTE FUNCTION documents.guard_workflow_profile_definitions_update();

GRANT SELECT, INSERT, UPDATE, DELETE ON documents.workflow_profile_definitions TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.workflow_profile_versions TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.workflow_profile_transitions TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.document_type_definitions TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents.workflow_profile_imports TO qmtool_runtime;
