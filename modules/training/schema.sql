CREATE TABLE IF NOT EXISTS training_categories (
    category_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS training_category_documents (
    category_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    PRIMARY KEY (category_id, document_id)
);

CREATE TABLE IF NOT EXISTS training_user_categories (
    category_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    PRIMARY KEY (category_id, user_id)
);

CREATE TABLE IF NOT EXISTS training_assignments (
    assignment_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    category_id TEXT NOT NULL,
    status TEXT NOT NULL,
    active INTEGER NOT NULL,
    read_confirmed_at TEXT,
    quiz_passed_at TEXT,
    last_score INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_training_assignment_active
ON training_assignments(user_id, document_id, version, category_id, active);

CREATE TABLE IF NOT EXISTS training_quiz_sets (
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    storage_key TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (document_id, version)
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

CREATE TABLE IF NOT EXISTS training_comments (
    comment_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    comment_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
