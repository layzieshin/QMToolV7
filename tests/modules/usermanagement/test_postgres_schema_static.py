"""Static (no PostgreSQL) checks for AP-028 M3 schema artifacts."""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.usermanagement import postgres_schema as pgs

ROOT = Path(__file__).resolve().parents[3]


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
    assert "create table usermanagement.users" in sql
    assert "create table usermanagement.sessions" in sql
    assert "schema_fingerprint" in sql
    assert "password_hash" in sql
    assert "token_hash" in sql
    assert "password text" not in sql
    assert "raw_token" not in sql
    assert "on delete restrict" in sql
    assert "lower(username)" in sql
    assert "expires_at > created_at" in sql
    assert "users_active_requires_null_deactivated_at" in sql
    assert "token_hash text not null unique" in sql
    assert "create index sessions_user_id_idx" in sql
    assert "token_hash_idx" not in sql
    assert "default gen_random_uuid" not in sql
    assert "default uuid_generate" not in sql
    assert "grant select, insert, update, delete on usermanagement.users to qmtool_runtime" in sql
    assert "grant select, insert, update, delete on usermanagement.sessions to qmtool_runtime" in sql
    grant_lines = [line.strip() for line in sql.splitlines() if line.strip().startswith("grant ")]
    assert grant_lines
    assert all("_qm_schema_migrations" not in line for line in grant_lines)


def test_provision_roles_bootstrap_contract() -> None:
    text = pgs.PROVISION_ROLES_PATH.read_text(encoding="utf-8")
    assert "qmtool_migrator" in text
    assert "qmtool_runtime" in text
    assert text.count("NOLOGIN") >= 2
    assert "PASSWORD '" not in text.upper()
    assert "LOGIN PASSWORD" not in text.upper()
    assert "CREATE SCHEMA usermanagement AUTHORIZATION qmtool_migrator" in text
    assert "REVOKE CREATE ON SCHEMA usermanagement FROM qmtool_runtime" in text
    assert "pg_has_role('qmtool_runtime', 'qmtool_migrator', 'MEMBER')" in text
    assert "pg_has_role('qmtool_runtime', 'qmtool_migrator', 'SET')" in text
    assert "pg_auth_members" in text
    assert "ALTER DEFAULT PRIVILEGES" not in text.upper()
    assert pgs.PROVISION_ROLES_PATH.parent.name == "postgres"


def test_postgres_migrations_are_outside_sqlite_gate_discovery_glob() -> None:
    discovered = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/*/migrations/*.sql")
    }
    pg_files = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/*/postgres/migrations/*.sql")
    }
    assert pg_files
    assert discovered.isdisjoint(pg_files)
    assert "modules/usermanagement/migrations/0001_initial.sql" in discovered
    assert "modules/usermanagement/postgres/migrations/0001_initial.sql" in pg_files


def test_discover_migrations_rejects_gaps(tmp_path: Path) -> None:
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0003_gap.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(pgs.PostgresSchemaError, match="contiguous"):
        pgs.discover_migrations(tmp_path)


def test_discover_migrations_rejects_duplicate_names(tmp_path: Path) -> None:
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0002_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(pgs.PostgresSchemaError, match="names must be unique"):
        pgs.discover_migrations(tmp_path)


def test_discover_migrations_rejects_invalid_filenames(tmp_path: Path) -> None:
    (tmp_path / "1_bad.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(pgs.PostgresSchemaError, match="invalid migration filename"):
        pgs.discover_migrations(tmp_path)
