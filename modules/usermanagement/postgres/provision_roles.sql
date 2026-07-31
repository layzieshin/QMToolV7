-- AP-028 M3: Administrative role + empty-schema bootstrap for Usermanagement.
--
-- Run ONLY as a database superuser / cloud admin BEFORE any schema migration.
-- Never executed by the migration applicator.
--
-- Creates NOLOGIN privilege roles (without credentials, without login). Deployment-specific
-- LOGIN roles are created outside this repository and granted membership in
-- exactly one of these privilege roles.
--
-- Idempotent for the empty bootstrap state. Aborts on populated/unknown schema
-- or unsuitable existing role attributes (does not heuristically ALTER them).

DO $$
DECLARE
    role_rec pg_roles%ROWTYPE;
    table_count integer;
    schema_owner name;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qmtool_migrator') THEN
        SELECT * INTO role_rec FROM pg_roles WHERE rolname = 'qmtool_migrator';
        IF role_rec.rolcanlogin
           OR role_rec.rolsuper
           OR role_rec.rolcreatedb
           OR role_rec.rolcreaterole
           OR role_rec.rolreplication
           OR role_rec.rolbypassrls THEN
            RAISE EXCEPTION
                'qmtool_migrator exists with unsuitable attributes (must be NOLOGIN privilege role)';
        END IF;
    ELSE
        CREATE ROLE qmtool_migrator
            NOLOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qmtool_runtime') THEN
        SELECT * INTO role_rec FROM pg_roles WHERE rolname = 'qmtool_runtime';
        IF role_rec.rolcanlogin
           OR role_rec.rolsuper
           OR role_rec.rolcreatedb
           OR role_rec.rolcreaterole
           OR role_rec.rolreplication
           OR role_rec.rolbypassrls THEN
            RAISE EXCEPTION
                'qmtool_runtime exists with unsuitable attributes (must be NOLOGIN privilege role)';
        END IF;
    ELSE
        CREATE ROLE qmtool_runtime
            NOLOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members memberships
        JOIN pg_roles member_role ON member_role.oid = memberships.member
        WHERE member_role.rolname IN ('qmtool_migrator', 'qmtool_runtime')
    ) THEN
        RAISE EXCEPTION
            'qmtool privilege roles must not inherit membership in other roles';
    END IF;

    IF pg_has_role('qmtool_runtime', 'qmtool_migrator', 'MEMBER')
       OR pg_has_role('qmtool_runtime', 'qmtool_migrator', 'SET') THEN
        RAISE EXCEPTION
            'qmtool_runtime must not inherit or SET ROLE to qmtool_migrator';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'usermanagement') THEN
        SELECT r.rolname INTO schema_owner
        FROM pg_namespace n
        JOIN pg_roles r ON r.oid = n.nspowner
        WHERE n.nspname = 'usermanagement';
        IF schema_owner IS DISTINCT FROM 'qmtool_migrator' THEN
            RAISE EXCEPTION
                'schema usermanagement owner is %, expected qmtool_migrator',
                schema_owner;
        END IF;
        SELECT COUNT(*) INTO table_count
        FROM information_schema.tables
        WHERE table_schema = 'usermanagement'
          AND table_type = 'BASE TABLE';
        IF table_count > 0 THEN
            RAISE EXCEPTION
                'schema usermanagement is not empty (% tables); refuse to re-provision',
                table_count;
        END IF;
    ELSE
        EXECUTE 'CREATE SCHEMA usermanagement AUTHORIZATION qmtool_migrator';
    END IF;

    REVOKE ALL ON SCHEMA usermanagement FROM PUBLIC;
    GRANT USAGE, CREATE ON SCHEMA usermanagement TO qmtool_migrator;
    GRANT USAGE ON SCHEMA usermanagement TO qmtool_runtime;
    REVOKE CREATE ON SCHEMA usermanagement FROM qmtool_runtime;
END
$$;
