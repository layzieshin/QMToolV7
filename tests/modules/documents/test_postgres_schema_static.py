"""Static (no PostgreSQL) checks for AP-029 PG01-A documents schema artifacts."""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.documents import postgres_schema as pgs

ROOT = Path(__file__).resolve().parents[3]
PLATFORM_LOCK = 0x5154_4D5F_504C_4154
UM_LOCK = 0x5154_4D5F_554D_4D47


def test_psycopg_imports_normally() -> None:
    import psycopg

    assert psycopg.connect is not None


def test_migration_chain_is_contiguous_and_checksum_stable() -> None:
    steps = pgs.discover_migrations()
    assert [step.version for step in steps] == list(range(1, len(steps) + 1))
    assert [step.name for step in steps] == [
        "initial",
        "workflow_profiles",
        "grant_history_select",
    ]


def test_initial_sql_contains_required_schema_contracts() -> None:
    sql = (pgs.MIGRATIONS_DIR / "0001_initial.sql").read_text(encoding="utf-8").lower()
    assert "create schema" not in sql
    assert "create table documents.document_headers" in sql
    assert "create table documents.document_versions" in sql
    assert "register_binding boolean not null" in sql
    assert "workflow_active boolean not null" in sql
    assert "reached_threshold boolean not null" in sql
    assert "where status = 'approved'" in sql
    grant_lines = [line.strip() for line in sql.splitlines() if line.strip().startswith("grant ")]
    assert len(grant_lines) == 7
    assert all("_qm_schema_migrations" not in line for line in grant_lines)


def test_workflow_profiles_sql_contains_immutability_contracts() -> None:
    sql = (pgs.MIGRATIONS_DIR / "0002_workflow_profiles.sql").read_text(encoding="utf-8").lower()
    assert "create table documents.workflow_profile_definitions" in sql
    assert "four_eyes_required boolean not null" in sql
    assert "workflow_profile_versions_version_no_positive" in sql
    assert "create or replace function documents.deny_workflow_profile_versions_mutation" in sql
    assert "trg_workflow_profile_versions_no_update" in sql
    assert "guard_workflow_profile_definitions_update" in sql
    assert "workflow_profile_definitions only allow activation updates" in sql


def test_history_select_grant_is_versioned_separately() -> None:
    sql = (pgs.MIGRATIONS_DIR / "0003_grant_history_select.sql").read_text(encoding="utf-8").lower()
    assert "grant select on documents._qm_schema_migrations to qmtool_runtime" in sql


def test_provision_documents_schema_bootstrap_contract() -> None:
    text = pgs.PROVISION_DOCUMENTS_SCHEMA_PATH.read_text(encoding="utf-8")
    assert "CREATE SCHEMA documents AUTHORIZATION qmtool_migrator" in text
    assert "provision_roles.sql" in text


def test_advisory_lock_is_distinct_from_platform_and_usermanagement() -> None:
    assert pgs.ADVISORY_LOCK_KEY not in {PLATFORM_LOCK, UM_LOCK}
    assert pgs.ADVISORY_LOCK_KEY == 0x5154_4D5F_444F_4353


def test_postgres_migrations_are_outside_sqlite_gate_discovery_glob() -> None:
    discovered = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/*/migrations/*.sql")
    }
    pg_files = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/documents/postgres/migrations/*.sql")
    }
    assert pg_files
    assert discovered.isdisjoint(pg_files)


def test_discover_migrations_rejects_invalid_filenames(tmp_path: Path) -> None:
    (tmp_path / "1_bad.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(pgs.PostgresSchemaError, match="invalid migration filename"):
        pgs.discover_migrations(tmp_path)
