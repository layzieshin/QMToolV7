-- AP-029 WCON00-E: preset fields on existing user_signature_templates.

ALTER TABLE signature.user_signature_templates
    ADD COLUMN show_time boolean NOT NULL DEFAULT false;

ALTER TABLE signature.user_signature_templates
    ADD COLUMN document_type text NULL;

ALTER TABLE signature.user_signature_templates
    ADD COLUMN role_context text NULL;

ALTER TABLE signature.user_signature_templates
    ADD COLUMN last_used_at timestamptz NULL;
