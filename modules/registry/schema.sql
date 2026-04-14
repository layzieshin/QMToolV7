CREATE TABLE IF NOT EXISTS document_registry (
    document_id TEXT PRIMARY KEY,
    active_version INTEGER,
    release_note TEXT,
    release_evidence_mode TEXT NOT NULL,
    register_state TEXT NOT NULL,
    is_findable INTEGER NOT NULL,
    valid_from TEXT,
    valid_until TEXT,
    last_update_event_id TEXT NOT NULL,
    last_update_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_document_registry_state
    ON document_registry (register_state, is_findable);
