-- AP-029 PG00-D: platform blob metadata + shared backup-set contract (D08).
-- Applied only by qm_platform.persistence.postgres_schema after prior platform migrations.
-- UUID primary keys are supplied by the application (no DB defaults).

CREATE TABLE platform.backup_sets (
    backup_set_id uuid PRIMARY KEY,
    organization_id text NOT NULL
        REFERENCES platform.organizations (organization_id)
        ON DELETE RESTRICT,
    label text NULL,
    status text NOT NULL DEFAULT 'open',
    created_at timestamptz NOT NULL,
    CONSTRAINT backup_sets_organization_id_nonempty
        CHECK (length(trim(organization_id)) > 0),
    CONSTRAINT backup_sets_status_known
        CHECK (status IN ('open', 'sealed'))
);

CREATE TABLE platform.blob_artifacts (
    artifact_id uuid PRIMARY KEY,
    organization_id text NOT NULL
        REFERENCES platform.organizations (organization_id)
        ON DELETE RESTRICT,
    backup_set_id uuid NOT NULL
        REFERENCES platform.backup_sets (backup_set_id)
        ON DELETE RESTRICT,
    checksum_sha256 text NOT NULL,
    size_bytes bigint NOT NULL,
    media_type text NOT NULL,
    version_no integer NOT NULL,
    storage_key text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT blob_artifacts_organization_id_nonempty
        CHECK (length(trim(organization_id)) > 0),
    CONSTRAINT blob_artifacts_checksum_format
        CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT blob_artifacts_size_positive
        CHECK (size_bytes > 0),
    CONSTRAINT blob_artifacts_media_type_present
        CHECK (btrim(media_type) <> ''),
    CONSTRAINT blob_artifacts_version_positive
        CHECK (version_no > 0),
    CONSTRAINT blob_artifacts_storage_key_present
        CHECK (btrim(storage_key) <> '')
);

CREATE UNIQUE INDEX blob_artifacts_storage_key_uidx
    ON platform.blob_artifacts (storage_key);

REVOKE ALL ON TABLE platform.backup_sets FROM PUBLIC;
REVOKE ALL ON TABLE platform.blob_artifacts FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE platform.backup_sets TO qmtool_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE platform.blob_artifacts TO qmtool_runtime;
