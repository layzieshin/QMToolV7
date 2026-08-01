-- AP-028 M7: append-only backend audit evidence (version 3).
-- Applied only by modules.usermanagement.postgres_schema after prior migrations.
-- UUID primary keys are supplied by the application (no DB defaults).
-- Do not include BEGIN/COMMIT; the applicator wraps each migration in a transaction.
-- Runtime may INSERT only; SELECT/UPDATE/DELETE are never granted to qmtool_runtime.

CREATE TABLE usermanagement.audit_events (
    audit_id uuid PRIMARY KEY,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    result text NOT NULL,
    reason_code text NULL,
    source text NOT NULL,
    client_type text NOT NULL,
    request_id text NOT NULL,
    actor_kind text NOT NULL,
    actor_user_id uuid NULL
        REFERENCES usermanagement.users (user_id)
        ON DELETE RESTRICT,
    actor_session_id uuid NULL
        REFERENCES usermanagement.sessions (session_id)
        ON DELETE RESTRICT,
    system_actor text NULL,
    target_user_id uuid NULL
        REFERENCES usermanagement.users (user_id)
        ON DELETE RESTRICT,
    target_session_id uuid NULL
        REFERENCES usermanagement.sessions (session_id)
        ON DELETE RESTRICT,
    affected_session_count integer NULL,
    changed_fields text[] NULL,
    role_before text NULL,
    role_after text NULL,
    is_qmb_before boolean NULL,
    is_qmb_after boolean NULL,
    is_active_before boolean NULL,
    is_active_after boolean NULL,
    must_change_password_before boolean NULL,
    must_change_password_after boolean NULL,
    CONSTRAINT audit_events_actor_kind_known
        CHECK (actor_kind IN ('user', 'system', 'anonymous')),
    CONSTRAINT audit_events_actor_form
        CHECK (
            (
                actor_kind = 'user'
                AND actor_user_id IS NOT NULL
                AND actor_session_id IS NOT NULL
                AND system_actor IS NULL
            )
            OR (
                actor_kind = 'system'
                AND system_actor = 'qmtool.session-expiry'
                AND actor_user_id IS NULL
                AND actor_session_id IS NULL
            )
            OR (
                actor_kind = 'anonymous'
                AND actor_user_id IS NULL
                AND actor_session_id IS NULL
                AND system_actor IS NULL
            )
        ),
    CONSTRAINT audit_events_event_type_known
        CHECK (
            event_type IN (
                'auth.login.succeeded',
                'auth.login.denied',
                'auth.logout.succeeded',
                'auth.logout_all.succeeded',
                'auth.session.expired',
                'user.created',
                'user.access_changed',
                'user.password_changed'
            )
        ),
    CONSTRAINT audit_events_result_known
        CHECK (result IN ('succeeded', 'denied', 'failed')),
    CONSTRAINT audit_events_request_id_present
        CHECK (btrim(request_id) <> '')
);

-- One expiry evidence row per session (idempotent via app UniqueViolation
-- handling; arbiter upserts would require SELECT, which qmtool_runtime must not have).
CREATE UNIQUE INDEX audit_events_session_expired_uidx
    ON usermanagement.audit_events (target_session_id)
    WHERE event_type = 'auth.session.expired';

REVOKE ALL ON TABLE usermanagement.audit_events FROM PUBLIC;
GRANT INSERT ON TABLE usermanagement.audit_events TO qmtool_runtime;
