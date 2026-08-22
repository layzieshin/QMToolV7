-- AP-029 PG00-C: platform-wide append-only fachliche audit contract (D07).
-- Applied only by qm_platform.persistence.postgres_schema after prior platform migrations.
-- UUID primary keys are supplied by the application (no DB defaults).
-- Runtime may INSERT only; SELECT/UPDATE/DELETE are never granted to qmtool_runtime.

CREATE TABLE platform.audit_events (
    audit_id uuid PRIMARY KEY,
    organization_id text NOT NULL
        REFERENCES platform.organizations (organization_id)
        ON DELETE RESTRICT,
    occurred_at timestamptz NOT NULL,
    request_id text NOT NULL,
    correlation_id text NULL,
    actor_kind text NOT NULL,
    actor_user_id uuid NULL,
    actor_label text NULL,
    action text NOT NULL,
    object_type text NOT NULL,
    object_id text NOT NULL,
    result text NOT NULL,
    reason_code text NULL,
    details_json jsonb NULL,
    CONSTRAINT audit_events_organization_id_nonempty
        CHECK (length(trim(organization_id)) > 0),
    CONSTRAINT audit_events_request_id_present
        CHECK (btrim(request_id) <> ''),
    CONSTRAINT audit_events_action_present
        CHECK (btrim(action) <> ''),
    CONSTRAINT audit_events_object_type_present
        CHECK (btrim(object_type) <> ''),
    CONSTRAINT audit_events_object_id_present
        CHECK (btrim(object_id) <> ''),
    CONSTRAINT audit_events_actor_kind_known
        CHECK (actor_kind IN ('user', 'system', 'anonymous')),
    CONSTRAINT audit_events_result_known
        CHECK (result IN ('succeeded', 'denied', 'failed')),
    CONSTRAINT audit_events_actor_form
        CHECK (
            (
                actor_kind = 'user'
                AND actor_user_id IS NOT NULL
                AND actor_label IS NULL
            )
            OR (
                actor_kind = 'system'
                AND actor_user_id IS NULL
                AND actor_label IS NOT NULL
                AND btrim(actor_label) <> ''
            )
            OR (
                actor_kind = 'anonymous'
                AND actor_user_id IS NULL
                AND actor_label IS NULL
            )
        )
);

REVOKE ALL ON TABLE platform.audit_events FROM PUBLIC;
GRANT INSERT ON TABLE platform.audit_events TO qmtool_runtime;
