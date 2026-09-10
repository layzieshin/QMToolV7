ALTER TABLE documents.document_versions ADD COLUMN edit_signed_at timestamptz;
ALTER TABLE documents.document_versions ADD COLUMN edit_signed_by text;
