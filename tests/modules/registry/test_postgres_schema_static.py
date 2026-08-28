"""Static (no PostgreSQL) checks for AP-029 PG01-A registry schema artifacts."""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.registry import postgres_schema as pgs

ROOT = Path(__file__).resolve().parents[3]
PLATFORM_LOCK = 0x5154_4D5F_504C_4154
UM_LOCK = 0x5154_4D5F_554D_4D47


def test_psycopg_imports_normally() -> None:
    import psycopg

    assert psycopg.connect is not None


def test_migration_chain_is_contiguous_and_checksum_stable() -> None:
    steps = pgs.discover_migrations()
    assert [step.version for step in steps] == list(range(1, len(steps) + 1))
    assert steps[0].name == "initial"
    checksum = steps[0].checksum
    assert len(checksum) == 64
    assert checksum == steps[0].checksum


def test_initial_sql_contains_required_schema_contracts() -> None:
    sql = (pgs.MIGRATIONS_DIR / "0001_initial.sql").read_text(encoding="utf-8").lower()
    assert "create schema" not in sql
    assert "create table registry.document_registry" in sql
    assert "create table registry._qm_schema_migrations" in sql
    assert "schema_fingerprint" in sql
    assert "is_findable boolean not null" in sql
    assert "last_update_at timestamptz not null" in sql
    assert (
        "grant select, insert, update, delete on registry.document_registry to qmtool_runtime"
        in sql
    )
    grant_lines = [line.strip() for line in sql.splitlines() if line.strip().startswith("grant ")]
    assert grant_lines
    assert all("_qm_schema_migrations" not in line for line in grant_lines)


def test_history_select_grant_is_versioned_separately() -> None:
    steps = pgs.discover_migrations()
    assert [step.name for step in steps] == ["initial", "grant_history_select"]
    sql = (pgs.MIGRATIONS_DIR / "0002_grant_history_select.sql").read_text(encoding="utf-8").lower()
    assert "grant select on registry._qm_schema_migrations to qmtool_runtime" in sql
    assert "insert" not in sql
    assert "update" not in sql
    assert "delete" not in sql


def test_provision_registry_schema_bootstrap_contract() -> None:
    text = pgs.PROVISION_REGISTRY_SCHEMA_PATH.read_text(encoding="utf-8")
    assert "qmtool_migrator" in text
    assert "qmtool_runtime" in text
    assert "PASSWORD '" not in text.upper()
    assert "LOGIN PASSWORD" not in text.upper()
    assert "CREATE ROLE qmtool_migrator" not in text
    assert "CREATE ROLE qmtool_runtime" not in text
    assert "CREATE SCHEMA registry AUTHORIZATION qmtool_migrator" in text
    assert "REVOKE CREATE ON SCHEMA registry FROM qmtool_runtime" in text
    assert "pg_has_role('qmtool_runtime', 'qmtool_migrator', 'MEMBER')" in text
    assert "provision_roles.sql" in text


def test_advisory_lock_is_distinct_from_platform_and_usermanagement() -> None:
    assert pgs.ADVISORY_LOCK_KEY not in {PLATFORM_LOCK, UM_LOCK}
    assert pgs.ADVISORY_LOCK_KEY == 0x5154_4D5F_5245_4749


def test_postgres_migrations_are_outside_sqlite_gate_discovery_glob() -> None:
    discovered = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/*/migrations/*.sql")
    }
    pg_files = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/registry/postgres/migrations/*.sql")
    }
    assert pg_files
    assert discovered.isdisjoint(pg_files)
    assert "modules/registry/migrations/0001_initial.sql" in discovered
    assert "modules/registry/postgres/migrations/0001_initial.sql" in pg_files


def test_discover_migrations_rejects_gaps(tmp_path: Path) -> None:
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0003_gap.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(pgs.PostgresSchemaError, match="contiguous"):
        pgs.discover_migrations(tmp_path)
