"""Live PostgreSQL checks for AP-028 M3 schema applicator."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import psycopg
import pytest

from modules.usermanagement import postgres_schema as pgs

DSN = os.environ.get("QMTOOL_PG_DSN", "").strip()
REQUIRED = os.environ.get("QMTOOL_PG_REQUIRED", "").strip() == "1"

pytestmark = pytest.mark.postgres

MIGRATOR_LOGIN = "qmtool_migrator_login_m3"
RUNTIME_LOGIN = "qmtool_runtime_login_m3"
LOGIN_PASSWORD = "m3-ci-only-secret"


def _require_dsn() -> str:
    if not DSN:
        if REQUIRED:
            pytest.fail("QMTOOL_PG_DSN is required when QMTOOL_PG_REQUIRED=1")
        pytest.skip("QMTOOL_PG_DSN not set")
    return DSN


def _dsn_with_user(dsn: str, user: str, password: str) -> str:
    conninfo = psycopg.conninfo.conninfo_to_dict(dsn)
    conninfo["user"] = user
    conninfo["password"] = password
    return psycopg.conninfo.make_conninfo(**conninfo)


def _drop_role_if_exists(conn: psycopg.Connection, role: str) -> None:
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
    if not exists:
        return
    conn.execute(f'DROP OWNED BY "{role}" CASCADE')
    conn.execute(f'DROP ROLE "{role}"')


def _cleanup_all(admin_dsn: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS usermanagement CASCADE")
        for role in (MIGRATOR_LOGIN, RUNTIME_LOGIN, "qmtool_runtime", "qmtool_migrator"):
            _drop_role_if_exists(conn, role)


def _prepare_environment(admin_dsn: str) -> tuple[str, str]:
    _cleanup_all(admin_dsn)
    pgs.provision_usermanagement_roles(admin_dsn)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        dbname = admin.execute("SELECT current_database()").fetchone()[0]
        admin.execute(
            f"""
            CREATE ROLE {MIGRATOR_LOGIN} LOGIN PASSWORD '{LOGIN_PASSWORD}'
                IN ROLE {pgs.MIGRATOR_ROLE}
            """
        )
        admin.execute(
            f"""
            CREATE ROLE {RUNTIME_LOGIN} LOGIN PASSWORD '{LOGIN_PASSWORD}'
                IN ROLE {pgs.RUNTIME_ROLE}
            """
        )
        admin.execute(f'GRANT CONNECT ON DATABASE "{dbname}" TO {MIGRATOR_LOGIN}')
        admin.execute(f'GRANT CONNECT ON DATABASE "{dbname}" TO {RUNTIME_LOGIN}')
    return (
        _dsn_with_user(admin_dsn, MIGRATOR_LOGIN, LOGIN_PASSWORD),
        _dsn_with_user(admin_dsn, RUNTIME_LOGIN, LOGIN_PASSWORD),
    )


@pytest.fixture
def env() -> tuple[str, str, str]:
    admin_dsn = _require_dsn()
    migrator_dsn, runtime_dsn = _prepare_environment(admin_dsn)
    yield admin_dsn, migrator_dsn, runtime_dsn
    _cleanup_all(admin_dsn)


def test_provision_is_idempotent(env: tuple[str, str, str]) -> None:
    admin_dsn, _migrator_dsn, _runtime_dsn = env
    pgs.provision_usermanagement_roles(admin_dsn)
    pgs.provision_usermanagement_roles(admin_dsn)


def test_fresh_install_owners_history_fingerprint_and_noop(env: tuple[str, str, str]) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    version = pgs.migrate_usermanagement_schema(migrator_dsn)
    assert version == 2
    again = pgs.migrate_usermanagement_schema(migrator_dsn)
    assert again == 2
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        rows = conn.execute(
            """
            SELECT version, name, checksum, schema_fingerprint
            FROM usermanagement._qm_schema_migrations
            ORDER BY version
            """
        ).fetchall()
        assert len(rows) == 2
        assert int(rows[0][0]) == 1
        assert rows[0][1] == "initial"
        assert int(rows[1][0]) == 2
        assert rows[1][1] == "grant_history_select"
        assert len(rows[0][2]) == 64
        assert len(rows[0][3]) == 64
        for table in ("users", "sessions", "_qm_schema_migrations"):
            owner = conn.execute(
                "SELECT tableowner FROM pg_tables WHERE schemaname=%s AND tablename=%s",
                ("usermanagement", table),
            ).fetchone()
            assert owner is not None and owner[0] == pgs.MIGRATOR_ROLE


def test_runtime_dml_allowed_ddl_and_history_denied(env: tuple[str, str, str]) -> None:
    _admin_dsn, migrator_dsn, runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    user_id = str(uuid.uuid4())
    with psycopg.connect(runtime_dsn) as runtime:
        runtime.execute("SET ROLE qmtool_runtime")
        runtime.execute(
            """
            INSERT INTO usermanagement.users (
                user_id, username, password_hash, role, is_active,
                created_at, updated_at
            ) VALUES (
                %s::uuid, 'runtime_user', 'hash', 'User', true, now(), now()
            )
            """,
            (user_id,),
        )
        runtime.commit()
        with pytest.raises(Exception):
            runtime.execute("CREATE TABLE usermanagement.should_fail (id int)")
            runtime.commit()
        runtime.rollback()
        with pytest.raises(Exception):
            runtime.execute(
                """
                INSERT INTO usermanagement._qm_schema_migrations
                    (version, name, checksum, schema_fingerprint)
                VALUES (2, 'x', %s, %s)
                """,
                ("a" * 64, "b" * 64),
            )
            runtime.commit()
        runtime.rollback()
        with pytest.raises(Exception):
            runtime.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")


def test_constraints_username_session_time_token_active_fk(env: tuple[str, str, str]) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    user_id = str(uuid.uuid4())
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        conn.execute(
            """
            INSERT INTO usermanagement.users (
                user_id, username, password_hash, role, is_active,
                created_at, updated_at
            ) VALUES (%s::uuid, 'Alice', 'hash', 'User', true, now(), now())
            """,
            (user_id,),
        )
        conn.commit()
        with pytest.raises(Exception):
            conn.execute(
                """
                INSERT INTO usermanagement.users (
                    user_id, username, password_hash, role, is_active,
                    created_at, updated_at
                ) VALUES (%s::uuid, 'alice', 'hash2', 'User', true, now(), now())
                """,
                (str(uuid.uuid4()),),
            )
            conn.commit()
        conn.rollback()
        with pytest.raises(Exception):
            conn.execute(
                """
                INSERT INTO usermanagement.users (
                    user_id, username, password_hash, role, is_active, deactivated_at,
                    created_at, updated_at
                ) VALUES (
                    %s::uuid, 'active_bad', 'hash', 'User', true, now(), now(), now()
                )
                """,
                (str(uuid.uuid4()),),
            )
            conn.commit()
        conn.rollback()
        conn.execute(
            """
            INSERT INTO usermanagement.users (
                user_id, username, password_hash, role, is_active, deactivated_at,
                created_at, updated_at
            ) VALUES (
                %s::uuid, 'legacy_inactive', 'hash', 'User', false, NULL, now(), now()
            )
            """,
            (str(uuid.uuid4()),),
        )
        conn.commit()
        with pytest.raises(Exception):
            conn.execute(
                """
                INSERT INTO usermanagement.sessions (
                    session_id, token_hash, user_id, created_at, last_seen_at,
                    expires_at, client_type
                ) VALUES (
                    %s::uuid, 't1', %s::uuid, now(), now(), now() - interval '1 hour', 'cli'
                )
                """,
                (str(uuid.uuid4()), user_id),
            )
            conn.commit()
        conn.rollback()
        conn.execute(
            """
            INSERT INTO usermanagement.sessions (
                session_id, token_hash, user_id, created_at, last_seen_at,
                expires_at, client_type
            ) VALUES (
                %s::uuid, 't-ok', %s::uuid, now(), now(), now() + interval '1 hour', 'cli'
            )
            """,
            (str(uuid.uuid4()), user_id),
        )
        conn.commit()
        with pytest.raises(Exception):
            conn.execute(
                """
                INSERT INTO usermanagement.sessions (
                    session_id, token_hash, user_id, created_at, last_seen_at,
                    expires_at, client_type
                ) VALUES (
                    %s::uuid, 't-ok', %s::uuid, now(), now(), now() + interval '2 hour', 'cli'
                )
                """,
                (str(uuid.uuid4()), user_id),
            )
            conn.commit()
        conn.rollback()
        with pytest.raises(Exception):
            conn.execute("DELETE FROM usermanagement.users WHERE user_id = %s::uuid", (user_id,))
            conn.commit()
        conn.rollback()


def test_checksum_mismatch_rejected(env: tuple[str, str, str]) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        conn.execute(
            "UPDATE usermanagement._qm_schema_migrations SET checksum = %s WHERE version = 1",
            ("0" * 64,),
        )
        conn.commit()
    with pytest.raises(pgs.PostgresSchemaError, match="checksum"):
        pgs.migrate_usermanagement_schema(migrator_dsn)


def test_name_mismatch_rejected(env: tuple[str, str, str]) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        conn.execute(
            "UPDATE usermanagement._qm_schema_migrations SET name = %s WHERE version = 1",
            ("renamed",),
        )
        conn.commit()
    with pytest.raises(pgs.PostgresSchemaError, match="name mismatch"):
        pgs.migrate_usermanagement_schema(migrator_dsn)


def test_newer_history_rejected(env: tuple[str, str, str]) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        conn.execute(
            """
            INSERT INTO usermanagement._qm_schema_migrations
                (version, name, checksum, schema_fingerprint)
            VALUES (99, 'future', %s, %s)
            """,
            ("a" * 64, "b" * 64),
        )
        conn.commit()
    with pytest.raises(pgs.PostgresSchemaError, match="newer|prefix|contiguous"):
        pgs.migrate_usermanagement_schema(migrator_dsn)


def test_fingerprint_drift_rejected(env: tuple[str, str, str]) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        conn.execute("ALTER TABLE usermanagement.users ADD COLUMN drift_col text")
        conn.commit()
    with pytest.raises(pgs.PostgresSchemaError, match="fingerprint"):
        pgs.migrate_usermanagement_schema(migrator_dsn)


def test_failed_migration_rolls_back_completely(env: tuple[str, str, str], tmp_path: Path) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    steps_dir = tmp_path / "migrations"
    steps_dir.mkdir()
    for name in ("0001_initial.sql", "0002_grant_history_select.sql"):
        (steps_dir / name).write_text(
            (pgs.MIGRATIONS_DIR / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (steps_dir / "0003_broken.sql").write_text(
        "CREATE TABLE usermanagement.partial_step (id int);\nSELECT 1/0;\n",
        encoding="utf-8",
    )
    with pytest.raises(pgs.PostgresSchemaError):
        pgs.migrate_usermanagement_schema(migrator_dsn, migrations_dir=steps_dir)
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        exists = conn.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='usermanagement' AND table_name='partial_step'
            )
            """
        ).fetchone()
        assert exists is not None and exists[0] is False
        count = conn.execute(
            "SELECT COUNT(*) FROM usermanagement._qm_schema_migrations"
        ).fetchone()
        assert count is not None and int(count[0]) == 2


def test_parallel_migration_lock_rejected(env: tuple[str, str, str]) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    holder = psycopg.connect(migrator_dsn, autocommit=True)
    try:
        locked = holder.execute(
            "SELECT pg_try_advisory_lock(%s)", (pgs.ADVISORY_LOCK_KEY,)
        ).fetchone()
        assert locked is not None and locked[0]
        with pytest.raises(pgs.PostgresSchemaError, match="already in progress"):
            pgs.migrate_usermanagement_schema(migrator_dsn)
    finally:
        holder.execute("SELECT pg_advisory_unlock(%s)", (pgs.ADVISORY_LOCK_KEY,))
        holder.close()


def test_unversioned_populated_schema_refused(env: tuple[str, str, str]) -> None:
    admin_dsn, migrator_dsn, _runtime_dsn = env
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("DROP SCHEMA IF EXISTS usermanagement CASCADE")
        admin.execute("CREATE SCHEMA usermanagement AUTHORIZATION qmtool_migrator")
        admin.execute("SET ROLE qmtool_migrator")
        admin.execute("CREATE TABLE usermanagement.orphan (id int)")
        admin.execute("RESET ROLE")
    with pytest.raises(pgs.PostgresSchemaError, match="unversioned|populated"):
        pgs.migrate_usermanagement_schema(migrator_dsn)


def test_migrator_can_apply_followup_migration(env: tuple[str, str, str], tmp_path: Path) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    steps_dir = tmp_path / "migrations"
    steps_dir.mkdir()
    for name in ("0001_initial.sql", "0002_grant_history_select.sql"):
        (steps_dir / name).write_text(
            (pgs.MIGRATIONS_DIR / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (steps_dir / "0003_add_note.sql").write_text(
        "ALTER TABLE usermanagement.users ADD COLUMN m3_note text NULL;\n",
        encoding="utf-8",
    )
    version = pgs.migrate_usermanagement_schema(migrator_dsn, migrations_dir=steps_dir)
    assert version == 3
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        row = conn.execute(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema='usermanagement'
              AND table_name='users'
              AND column_name='m3_note'
            """
        ).fetchone()
        assert row is not None and int(row[0]) == 1


def test_poisoned_runtime_membership_blocks_provision_and_migrate(
    env: tuple[str, str, str],
) -> None:
    admin_dsn, migrator_dsn, _runtime_dsn = env
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("GRANT qmtool_migrator TO qmtool_runtime")
    try:
        with pytest.raises(Exception, match="must not inherit|must not SET ROLE"):
            pgs.provision_usermanagement_roles(admin_dsn)
        with pytest.raises(pgs.PostgresSchemaError, match="must not inherit|must not SET ROLE"):
            pgs.migrate_usermanagement_schema(migrator_dsn)
        with psycopg.connect(admin_dsn) as admin:
            tables = admin.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'usermanagement'
                """
            ).fetchone()
            assert tables is not None and int(tables[0]) == 0
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute("REVOKE qmtool_migrator FROM qmtool_runtime")


def test_runtime_acl_drift_is_rejected(env: tuple[str, str, str]) -> None:
    admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("GRANT CREATE ON SCHEMA usermanagement TO qmtool_runtime")
    try:
        with pytest.raises(pgs.PostgresSchemaError, match="schema USAGE|schema CREATE"):
            pgs.migrate_usermanagement_schema(migrator_dsn)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute("REVOKE CREATE ON SCHEMA usermanagement FROM qmtool_runtime")

    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(
            "GRANT INSERT ON usermanagement._qm_schema_migrations TO qmtool_runtime"
        )
    try:
        with pytest.raises(pgs.PostgresSchemaError, match="must not have INSERT"):
            pgs.migrate_usermanagement_schema(migrator_dsn)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "REVOKE INSERT ON usermanagement._qm_schema_migrations FROM qmtool_runtime"
            )

    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(
            "REVOKE SELECT ON usermanagement._qm_schema_migrations FROM qmtool_runtime"
        )
    try:
        with pytest.raises(pgs.PostgresSchemaError, match="missing SELECT"):
            pgs.migrate_usermanagement_schema(migrator_dsn)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "GRANT SELECT ON usermanagement._qm_schema_migrations TO qmtool_runtime"
            )


def test_fk_definition_drift_is_rejected(env: tuple[str, str, str]) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn = env
    pgs.migrate_usermanagement_schema(migrator_dsn)
    with psycopg.connect(migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        conn.execute(
            "ALTER TABLE usermanagement.sessions DROP CONSTRAINT sessions_user_id_fkey"
        )
        conn.execute(
            """
            ALTER TABLE usermanagement.sessions
            ADD CONSTRAINT sessions_user_id_fkey
            FOREIGN KEY (session_id) REFERENCES usermanagement.users (user_id)
            ON DELETE RESTRICT
            """
        )
        conn.commit()

    with pytest.raises(pgs.PostgresSchemaError, match="fingerprint"):
        pgs.migrate_usermanagement_schema(migrator_dsn)


@pytest.mark.parametrize(
    "ddl",
    (
        "CREATE VIEW usermanagement.orphan_view AS SELECT 1 AS value",
        "CREATE MATERIALIZED VIEW usermanagement.orphan_materialized AS SELECT 1 AS value",
        "CREATE SEQUENCE usermanagement.orphan_sequence",
        """
        CREATE FUNCTION usermanagement.orphan_function() RETURNS integer
        LANGUAGE sql AS $$ SELECT 1 $$
        """,
        "CREATE TYPE usermanagement.orphan_type AS ENUM ('value')",
    ),
)
def test_unversioned_non_table_objects_are_refused(
    env: tuple[str, str, str],
    ddl: str,
) -> None:
    admin_dsn, migrator_dsn, _runtime_dsn = env
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        admin.execute(ddl)
        admin.execute("RESET ROLE")

    with pytest.raises(pgs.PostgresSchemaError, match="populated unversioned"):
        pgs.migrate_usermanagement_schema(migrator_dsn)
