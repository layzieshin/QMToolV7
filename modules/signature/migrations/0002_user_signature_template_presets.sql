-- AP-029 WCON00-E: preset fields on existing user_signature_templates (SQLite test path).

ALTER TABLE user_signature_templates ADD COLUMN show_time INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_signature_templates ADD COLUMN document_type TEXT;
ALTER TABLE user_signature_templates ADD COLUMN role_context TEXT;
ALTER TABLE user_signature_templates ADD COLUMN last_used_at TEXT;
