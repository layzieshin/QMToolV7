-- AP-029 PG01-A: Administrative bootstrap for the registry schema only.
--
-- Run ONLY as a database superuser / cloud admin BEFORE any registry schema migration.
-- Never executed by the migration applicator.
--
-- Requires shared NOLOGIN privilege roles from
-- modules/usermanagement/postgres/provision_roles.sql (does not create roles or passwords).
--
-- Idempotent for the empty bootstrap state. Aborts on populated/unknown schema
-- or unsuitable existing role membership.

DO $$
DECLARE
    table_count integer;
    schema_owner name;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qmtool_migrator') THEN
        RAISE EXCEPTION
            'qmtool_migrator missing; run modules/usermanagement/postgres/provision_roles.sql first';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qmtool_runtime') THEN
        RAISE EXCEPTION
            'qmtool_runtime missing; run modules/usermanagement/postgres/provision_roles.sql first';
    END IF;

    IF pg_has_role('qmtool_runtime', 'qmtool_migrator', 'MEMBER')
       OR pg_has_role('qmtool_runtime', 'qmtool_migrator', 'SET') THEN
        RAISE EXCEPTION
            'qmtool_runtime must not inherit or SET ROLE to qmtool_migrator';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'registry') THEN
        SELECT r.rolname INTO schema_owner
        FROM pg_namespace n
        JOIN pg_roles r ON r.oid = n.nspowner
        WHERE n.nspname = 'registry';
        IF schema_owner IS DISTINCT FROM 'qmtool_migrator' THEN
            RAISE EXCEPTION
                'schema registry owner is %, expected qmtool_migrator',
                schema_owner;
        END IF;
        SELECT COUNT(*) INTO table_count
        FROM information_schema.tables
        WHERE table_schema = 'registry'
          AND table_type = 'BASE TABLE';
        IF table_count > 0 THEN
            RAISE EXCEPTION
                'schema registry is not empty (% tables); refuse to re-provision',
                table_count;
        END IF;
    ELSE
        EXECUTE 'CREATE SCHEMA registry AUTHORIZATION qmtool_migrator';
    END IF;

    REVOKE ALL ON SCHEMA registry FROM PUBLIC;
    GRANT USAGE, CREATE ON SCHEMA registry TO qmtool_migrator;
    GRANT USAGE ON SCHEMA registry TO qmtool_runtime;
    REVOKE CREATE ON SCHEMA registry FROM qmtool_runtime;
END
$$;
