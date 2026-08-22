-- AP-029 PG00-D rework: enforce organization-scoped backup_set references.
-- Applied only by qm_platform.persistence.postgres_schema after prior platform migrations.

ALTER TABLE platform.backup_sets
    ADD CONSTRAINT backup_sets_id_org_unique
    UNIQUE (backup_set_id, organization_id);

ALTER TABLE platform.blob_artifacts
    DROP CONSTRAINT blob_artifacts_backup_set_id_fkey;

ALTER TABLE platform.blob_artifacts
    ADD CONSTRAINT blob_artifacts_backup_set_org_fkey
    FOREIGN KEY (backup_set_id, organization_id)
    REFERENCES platform.backup_sets (backup_set_id, organization_id)
    ON DELETE RESTRICT;
