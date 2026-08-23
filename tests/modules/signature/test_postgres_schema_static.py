"""Static (no PostgreSQL) checks for AP-029 PG01-A signature schema artifacts."""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.signature import postgres_schema as pgs

ROOT = Path(__file__).resolve().parents[3]
PLATFORM_LOCK = 0x5154_4D5F_504C_4154
UM_LOCK = 0x5154_4D5F_554D_4D47
REGISTRY_LOCK = 0x5154_4D5F_5245_4749


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
    assert "create table signature.signature_assets" in sql
    assert "create table signature.user_signature_templates" in sql
    assert "create table signature.user_active_signatures" in sql
    assert "show_signature boolean not null" in sql
    assert "created_at timestamptz not null" in sql
    assert (
        "grant select, insert, update, delete on signature.signature_assets to qmtool_runtime"
        in sql
    )
    grant_lines = [line.strip() for line in sql.splitlines() if line.strip().startswith("grant ")]
    assert len(grant_lines) == 3
    assert all("_qm_schema_migrations" not in line for line in grant_lines)


def test_history_select_grant_is_versioned_separately() -> None:
    steps = pgs.discover_migrations()
    assert [step.name for step in steps] == ["initial", "grant_history_select"]
    sql = (pgs.MIGRATIONS_DIR / "0002_grant_history_select.sql").read_text(encoding="utf-8").lower()
    assert "grant select on signature._qm_schema_migrations to qmtool_runtime" in sql


def test_provision_signature_schema_bootstrap_contract() -> None:
    text = pgs.PROVISION_SIGNATURE_SCHEMA_PATH.read_text(encoding="utf-8")
    assert "CREATE SCHEMA signature AUTHORIZATION qmtool_migrator" in text
    assert "provision_roles.sql" in text


def test_advisory_lock_is_distinct_from_other_modules() -> None:
    assert pgs.ADVISORY_LOCK_KEY not in {PLATFORM_LOCK, UM_LOCK, REGISTRY_LOCK}
    assert pgs.ADVISORY_LOCK_KEY == 0x5154_4D5F_5349_474E


def test_postgres_migrations_are_outside_sqlite_gate_discovery_glob() -> None:
    discovered = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/*/migrations/*.sql")
    }
    pg_files = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/signature/postgres/migrations/*.sql")
    }
    assert pg_files
    assert discovered.isdisjoint(pg_files)


def test_discover_migrations_rejects_duplicate_names(tmp_path: Path) -> None:
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0002_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(pgs.PostgresSchemaError, match="names must be unique"):
        pgs.discover_migrations(tmp_path)
