"""Live PostgreSQL checks for AP-029 PG00-A platform schema applicator."""
from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from qm_platform.persistence import postgres_schema as pgs
from tests.postgres_destructive_guard import (
    EXPECTED_DATABASE,
    DestructivePostgresGuardError,
    require_approved_admin_dsn,
)
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres


def _guarded_drop_platform_schema(*, admin_dsn: str | None = None) -> None:
    approved = require_approved_admin_dsn(candidate=admin_dsn)
    with psycopg.connect(approved, autocommit=True) as conn:
        current = conn.execute("SELECT current_database()").fetchone()[0]
        if str(current) != EXPECTED_DATABASE:
            raise DestructivePostgresGuardError(
                "refusing DROP SCHEMA outside isolated test database"
            )
        conn.execute("DROP SCHEMA IF EXISTS platform CASCADE")


def _prepare_platform_schema(env: LivePostgresEnv) -> None:
    _guarded_drop_platform_schema(admin_dsn=env.admin_dsn)
    pgs.provision_platform_schema(env.admin_dsn)


@pytest.fixture
def platform_env(live_postgres_env: LivePostgresEnv) -> LivePostgresEnv:
    _prepare_platform_schema(live_postgres_env)
    yield live_postgres_env
    _guarded_drop_platform_schema(admin_dsn=live_postgres_env.admin_dsn)


def test_provision_is_idempotent(platform_env: LivePostgresEnv) -> None:
    pgs.provision_platform_schema(platform_env.admin_dsn)
    pgs.provision_platform_schema(platform_env.admin_dsn)


def test_fresh_install_owners_history_fingerprint_and_noop(
    platform_env: LivePostgresEnv,
) -> None:
    version = pgs.migrate_platform_schema(platform_env.migrator_dsn)
    assert version == 2
    again = pgs.migrate_platform_schema(platform_env.migrator_dsn)
    assert again == 2
    with psycopg.connect(platform_env.migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        rows = conn.execute(
            """
            SELECT version, name, checksum, schema_fingerprint
            FROM platform._qm_schema_migrations
            ORDER BY version
            """
        ).fetchall()
        assert len(rows) == 2
        assert int(rows[0][0]) == 1
        assert rows[0][1] == "platform_settings"
        assert int(rows[1][0]) == 2
        assert rows[1][1] == "platform_settings_integrity"
        assert len(rows[0][2]) == 64
        assert len(rows[0][3]) == 64
        for table in (
            "platform_settings",
            "platform_setting_revisions",
            "platform_settings_integrity",
            "_qm_schema_migrations",
        ):
            owner = conn.execute(
                "SELECT tableowner FROM pg_tables WHERE schemaname=%s AND tablename=%s",
                ("platform", table),
            ).fetchone()
            assert owner is not None and owner[0] == pgs.MIGRATOR_ROLE


def test_runtime_dml_allowed_ddl_and_history_denied(platform_env: LivePostgresEnv) -> None:
    pgs.migrate_platform_schema(platform_env.migrator_dsn)
    with psycopg.connect(platform_env.runtime_dsn) as runtime:
        runtime.execute("SET ROLE qmtool_runtime")
        runtime.execute(
            """
            INSERT INTO platform.platform_settings (
                scope_kind, scope_id, module_id, setting_key,
                value_type, value_json, schema_version, revision,
                updated_at, updated_by_user_id
            ) VALUES (
                'MODULE', 'documents', 'documents', 'sample_key',
                'string', '"value"', 1, 1, '2026-01-01T00:00:00+00:00', 'runtime-user'
            )
            """
        )
        runtime.commit()
        with pytest.raises(Exception):
            runtime.execute("CREATE TABLE platform.should_fail (id int)")
            runtime.commit()
        runtime.rollback()
        with pytest.raises(Exception):
            runtime.execute(
                """
                INSERT INTO platform._qm_schema_migrations
                    (version, name, checksum, schema_fingerprint)
                VALUES (2, 'x', %s, %s)
                """,
                ("a" * 64, "b" * 64),
            )
            runtime.commit()
        runtime.rollback()
        with pytest.raises(Exception):
            runtime.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        runtime.rollback()
        runtime.execute(
            """
            SELECT version FROM platform._qm_schema_migrations ORDER BY version
            """
        ).fetchall()


def test_checksum_mismatch_rejected(platform_env: LivePostgresEnv) -> None:
    pgs.migrate_platform_schema(platform_env.migrator_dsn)
    with psycopg.connect(platform_env.migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        conn.execute(
            "UPDATE platform._qm_schema_migrations SET checksum = %s WHERE version = 1",
            ("0" * 64,),
        )
        conn.commit()
    with pytest.raises(pgs.PostgresSchemaError, match="checksum"):
        pgs.migrate_platform_schema(platform_env.migrator_dsn)


def test_fingerprint_drift_rejected(platform_env: LivePostgresEnv) -> None:
    pgs.migrate_platform_schema(platform_env.migrator_dsn)
    with psycopg.connect(platform_env.migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        conn.execute(
            "ALTER TABLE platform.platform_settings ADD COLUMN drift_col text"
        )
        conn.commit()
    with pytest.raises(pgs.PostgresSchemaError, match="fingerprint"):
        pgs.migrate_platform_schema(platform_env.migrator_dsn)


def test_parallel_migration_lock_rejected(platform_env: LivePostgresEnv) -> None:
    pgs.migrate_platform_schema(platform_env.migrator_dsn)
    holder = psycopg.connect(platform_env.migrator_dsn, autocommit=True)
    try:
        locked = holder.execute(
            "SELECT pg_try_advisory_lock(%s)", (pgs.ADVISORY_LOCK_KEY,)
        ).fetchone()
        assert locked is not None and locked[0]
        with pytest.raises(pgs.PostgresSchemaError, match="already in progress"):
            pgs.migrate_platform_schema(platform_env.migrator_dsn)
    finally:
        holder.execute("SELECT pg_advisory_unlock(%s)", (pgs.ADVISORY_LOCK_KEY,))
        holder.close()


def test_unversioned_populated_schema_refused(platform_env: LivePostgresEnv) -> None:
    _guarded_drop_platform_schema(admin_dsn=platform_env.admin_dsn)
    with psycopg.connect(platform_env.admin_dsn, autocommit=True) as admin:
        admin.execute("CREATE SCHEMA platform AUTHORIZATION qmtool_migrator")
        admin.execute("SET ROLE qmtool_migrator")
        admin.execute("CREATE TABLE platform.orphan (id int)")
        admin.execute("RESET ROLE")
    with pytest.raises(pgs.PostgresSchemaError, match="unversioned|populated"):
        pgs.migrate_platform_schema(platform_env.migrator_dsn)


def test_runtime_acl_drift_is_rejected(platform_env: LivePostgresEnv) -> None:
    pgs.migrate_platform_schema(platform_env.migrator_dsn)
    with psycopg.connect(platform_env.admin_dsn, autocommit=True) as admin:
        admin.execute("GRANT CREATE ON SCHEMA platform TO qmtool_runtime")
    try:
        with pytest.raises(pgs.PostgresSchemaError, match="schema USAGE|schema CREATE"):
            pgs.migrate_platform_schema(platform_env.migrator_dsn)
    finally:
        with psycopg.connect(platform_env.admin_dsn, autocommit=True) as admin:
            admin.execute("REVOKE CREATE ON SCHEMA platform FROM qmtool_runtime")

    with psycopg.connect(platform_env.admin_dsn, autocommit=True) as admin:
        admin.execute(
            "GRANT INSERT ON platform._qm_schema_migrations TO qmtool_runtime"
        )
    try:
        with pytest.raises(pgs.PostgresSchemaError, match="must not have INSERT"):
            pgs.migrate_platform_schema(platform_env.migrator_dsn)
    finally:
        with psycopg.connect(platform_env.admin_dsn, autocommit=True) as admin:
            admin.execute(
                "REVOKE INSERT ON platform._qm_schema_migrations FROM qmtool_runtime"
            )


def test_assert_runtime_schema_ready(platform_env: LivePostgresEnv) -> None:
    pgs.migrate_platform_schema(platform_env.migrator_dsn)
    assert pgs.assert_runtime_schema_ready(platform_env.runtime_dsn) == 2


def test_failed_migration_rolls_back_completely(
    platform_env: LivePostgresEnv,
    tmp_path: Path,
) -> None:
    pgs.migrate_platform_schema(platform_env.migrator_dsn)
    steps_dir = tmp_path / "migrations"
    steps_dir.mkdir()
    for name in (
        "0001_platform_settings.sql",
        "0002_platform_settings_integrity.sql",
    ):
        (steps_dir / name).write_text(
            (pgs.MIGRATIONS_DIR / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (steps_dir / "0003_broken.sql").write_text(
        "CREATE TABLE platform.partial_step (id int);\nSELECT 1/0;\n",
        encoding="utf-8",
    )
    with pytest.raises(pgs.PostgresSchemaError):
        pgs.migrate_platform_schema(
            platform_env.migrator_dsn,
            migrations_dir=steps_dir,
        )
    with psycopg.connect(platform_env.migrator_dsn) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        exists = conn.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='platform' AND table_name='partial_step'
            )
            """
        ).fetchone()
        assert exists is not None and exists[0] is False
        count = conn.execute(
            "SELECT COUNT(*) FROM platform._qm_schema_migrations"
        ).fetchone()
        assert count is not None and int(count[0]) == 2
