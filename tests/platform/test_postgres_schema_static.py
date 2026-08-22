"""Static (no PostgreSQL) checks for AP-029 PG00-A platform schema artifacts."""
from __future__ import annotations

from pathlib import Path

import pytest

from qm_platform.persistence import postgres_schema as pgs

ROOT = Path(__file__).resolve().parents[2]


def test_psycopg_imports_normally() -> None:
    import psycopg

    assert psycopg.connect is not None


def test_migration_chain_is_contiguous_and_checksum_stable() -> None:
    steps = pgs.discover_migrations()
    assert [step.version for step in steps] == list(range(1, len(steps) + 1))
    assert steps[0].name == "platform_settings"
    checksum = steps[0].checksum
    assert len(checksum) == 64
    assert checksum == steps[0].checksum


def test_platform_settings_sql_contains_required_schema_contracts() -> None:
    sql = (
        pgs.MIGRATIONS_DIR / "0001_platform_settings.sql"
    ).read_text(encoding="utf-8").lower()
    assert "create schema" not in sql
    assert "create table platform.platform_settings" in sql
    assert "create table platform.platform_setting_revisions" in sql
    assert "schema_fingerprint" in sql
    assert "scope_kind" in sql
    assert "value_json" in sql
    assert "platform_settings_scope_kind_module" in sql
    assert "platform_settings_scope_id_matches_module" in sql
    assert "platform_settings_revision_positive" in sql
    assert (
        "grant select, insert, update, delete on platform.platform_settings to qmtool_runtime"
        in sql
    )
    assert (
        "grant select, insert, update, delete on platform.platform_setting_revisions to qmtool_runtime"
        in sql
    )
    grant_lines = [line.strip() for line in sql.splitlines() if line.strip().startswith("grant ")]
    assert grant_lines
    assert all("_qm_schema_migrations" not in line for line in grant_lines)


def test_integrity_migration_contains_required_contracts() -> None:
    steps = pgs.discover_migrations()
    assert [step.name for step in steps] == [
        "platform_settings",
        "platform_settings_integrity",
    ]
    sql = (
        pgs.MIGRATIONS_DIR / "0002_platform_settings_integrity.sql"
    ).read_text(encoding="utf-8").lower()
    assert "create table platform.platform_settings_integrity" in sql
    assert "integrity_key" in sql
    assert "integrity_value" in sql
    assert "grant select on platform._qm_schema_migrations to qmtool_runtime" in sql
    assert "insert" not in sql.replace(
        "grant select, insert, update, delete on platform.platform_settings_integrity to qmtool_runtime",
        "",
    )


def test_provision_platform_schema_bootstrap_contract() -> None:
    text = pgs.PROVISION_PLATFORM_SCHEMA_PATH.read_text(encoding="utf-8")
    assert "qmtool_migrator" in text
    assert "qmtool_runtime" in text
    assert "PASSWORD '" not in text.upper()
    assert "LOGIN PASSWORD" not in text.upper()
    assert "CREATE ROLE qmtool_migrator" not in text
    assert "CREATE ROLE qmtool_runtime" not in text
    assert "CREATE SCHEMA platform AUTHORIZATION qmtool_migrator" in text
    assert "REVOKE CREATE ON SCHEMA platform FROM qmtool_runtime" in text
    assert "pg_has_role('qmtool_runtime', 'qmtool_migrator', 'MEMBER')" in text
    assert "pg_has_role('qmtool_runtime', 'qmtool_migrator', 'SET')" in text
    assert "provision_roles.sql" in text
    assert pgs.PROVISION_PLATFORM_SCHEMA_PATH.parent.name == "postgres"


def test_advisory_lock_is_distinct_from_usermanagement() -> None:
    usermanagement_advisory_lock_key = 0x5154_4D5F_554D_4D47  # AP-028 UM "QTM_UMMG"

    assert pgs.ADVISORY_LOCK_KEY != usermanagement_advisory_lock_key
    assert pgs.ADVISORY_LOCK_KEY == 0x5154_4D5F_504C_4154


def test_postgres_migrations_are_outside_sqlite_gate_discovery_glob() -> None:
    discovered = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/*/migrations/*.sql")
    }
    discovered.update(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("qm_platform/persistence/migrations/*.sql")
    )
    pg_files = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("qm_platform/persistence/postgres/migrations/*.sql")
    }
    assert pg_files
    assert discovered.isdisjoint(pg_files)
    assert "qm_platform/persistence/migrations/0001_platform_settings.sql" in discovered
    assert (
        "qm_platform/persistence/postgres/migrations/0001_platform_settings.sql"
        in pg_files
    )


def test_discover_migrations_rejects_gaps(tmp_path: Path) -> None:
    (tmp_path / "0001_platform_settings.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0003_gap.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(pgs.PostgresSchemaError, match="contiguous"):
        pgs.discover_migrations(tmp_path)


def test_discover_migrations_rejects_duplicate_names(tmp_path: Path) -> None:
    (tmp_path / "0001_platform_settings.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0002_platform_settings.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(pgs.PostgresSchemaError, match="names must be unique"):
        pgs.discover_migrations(tmp_path)


def test_discover_migrations_rejects_invalid_filenames(tmp_path: Path) -> None:
    (tmp_path / "1_bad.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(pgs.PostgresSchemaError, match="invalid migration filename"):
        pgs.discover_migrations(tmp_path)
