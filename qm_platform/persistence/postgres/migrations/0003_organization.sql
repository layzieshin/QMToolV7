-- AP-029 PG00-B: single active organization record for server-side context.
-- Applied only by qm_platform.persistence.postgres_schema after prior platform migrations.

CREATE TABLE platform.organizations (
    organization_id text PRIMARY KEY,
    display_name text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT organizations_organization_id_nonempty
        CHECK (length(trim(organization_id)) > 0),
    CONSTRAINT organizations_display_name_nonempty
        CHECK (length(trim(display_name)) > 0)
);

CREATE UNIQUE INDEX organizations_single_active
    ON platform.organizations (is_active)
    WHERE is_active = true;

INSERT INTO platform.organizations (organization_id, display_name, is_active)
VALUES (
    '00000000-0000-4000-8000-000000000001',
    'Default Installation',
    true
);

GRANT SELECT ON platform.organizations TO qmtool_runtime;
REVOKE ALL ON TABLE platform.organizations FROM PUBLIC;
