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


class _FakeResult:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return list(self._rows)

    def fetchone(self) -> tuple | None:
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Minimal connection stand-in for `_validate_schema_contracts` behavior tests."""

    def __init__(
        self,
        *,
        tables: set[str],
        columns: dict[str, set[str]],
        checks: set[str],
        table_owners: dict[str, str] | None = None,
    ) -> None:
        self.tables = set(tables)
        self.columns = {k: set(v) for k, v in columns.items()}
        self.checks = set(checks)
        self.table_owners = table_owners or {}
        self.queries: list[tuple[str, tuple | None]] = []

    def execute(self, query: str, params: tuple | None = None) -> _FakeResult:
        sql = " ".join(str(query).split())
        self.queries.append((sql, params))
        low = sql.lower()

        if "from information_schema.tables" in low:
            return _FakeResult([(name,) for name in sorted(self.tables)])

        if "from information_schema.columns" in low and params and len(params) >= 2:
            table = str(params[1])
            return _FakeResult([(col,) for col in sorted(self.columns.get(table, set()))])

        if "from pg_constraint" in low and "con.contype = 'c'" in low.replace(" ", ""):
            # tolerate spacing variants
            pass
        if "from pg_constraint" in low and "contype" in low:
            return _FakeResult([(name,) for name in sorted(self.checks)])

        if "from pg_tables" in low and params and len(params) >= 2:
            table = str(params[1])
            owner = self.table_owners.get(table, pgs.MIGRATOR_ROLE)
            return _FakeResult([(owner,)])

        if "has_schema_privilege" in low and params:
            role, _schema, priv = params
            if role == pgs.RUNTIME_ROLE and priv == "USAGE":
                return _FakeResult([(True,)])
            if role == pgs.RUNTIME_ROLE and priv == "CREATE":
                return _FakeResult([(False,)])
            return _FakeResult([(False,)])

        if "has_table_privilege" in low and params:
            role, qualified, priv = params
            if role != pgs.RUNTIME_ROLE:
                return _FakeResult([(False,)])
            if qualified.endswith(f".{pgs.MIGRATIONS_TABLE}"):
                # history defaults: no SELECT unless test opts in via require_history_select callers
                return _FakeResult([(False,)])
            if priv in {"SELECT", "INSERT", "UPDATE", "DELETE"}:
                return _FakeResult([(True,)])
            return _FakeResult([(False,)])

        if "aclexplode" in low or "grantee = 0" in low:
            return _FakeResult([(False,)])

        raise AssertionError(f"unexpected fake query: {sql!r} params={params!r}")


def _v1_columns() -> dict[str, set[str]]:
    return {
        "document_headers": set(pgs.EXPECTED_DOCUMENT_HEADERS_COLUMNS),
        "document_versions": set(pgs.EXPECTED_DOCUMENT_VERSIONS_COLUMNS),
        pgs.MIGRATIONS_TABLE: set(pgs.EXPECTED_HISTORY_COLUMNS),
        # other V1 tables: empty column sets are fine; validator only checks headers/versions/history
    }


def test_validate_schema_contracts_require_full_false_skips_v2_contracts() -> None:
    conn = _FakeConn(
        tables=set(pgs.EXPECTED_TABLES),
        columns=_v1_columns(),
        checks=set(),  # V2 checks absent; must not be queried
    )
    pgs._validate_schema_contracts(
        conn,  # type: ignore[arg-type]
        require_history_select=False,
        require_full=False,
    )
    joined = "\n".join(q for q, _ in conn.queries).lower()
    assert "workflow_profile_definitions" not in joined
    assert "pg_constraint" not in joined


def test_validate_schema_contracts_require_full_true_enforces_v2_columns() -> None:
    columns = _v1_columns()
    columns["workflow_profile_definitions"] = set()  # present table, missing columns
    conn = _FakeConn(
        tables=set(pgs.EXPECTED_TABLES_FULL),
        columns=columns,
        checks=set(pgs.EXPECTED_CHECK_CONSTRAINTS),
    )
    with pytest.raises(pgs.PostgresSchemaError, match="workflow_profile_definitions missing columns"):
        pgs._validate_schema_contracts(
            conn,  # type: ignore[arg-type]
            require_history_select=False,
            require_full=True,
        )


def test_validate_schema_contracts_require_full_true_enforces_v2_check_constraints() -> None:
    columns = _v1_columns()
    columns["workflow_profile_definitions"] = set(pgs.EXPECTED_WORKFLOW_PROFILE_DEFINITIONS_COLUMNS)
    conn = _FakeConn(
        tables=set(pgs.EXPECTED_TABLES_FULL),
        columns=columns,
        checks=set(),  # missing all V2 checks
    )
    with pytest.raises(pgs.PostgresSchemaError, match="missing check constraints"):
        pgs._validate_schema_contracts(
            conn,  # type: ignore[arg-type]
            require_history_select=False,
            require_full=True,
        )


def test_validate_schema_contracts_require_full_true_accepts_complete_v2_contract() -> None:
    columns = _v1_columns()
    columns["workflow_profile_definitions"] = set(pgs.EXPECTED_WORKFLOW_PROFILE_DEFINITIONS_COLUMNS)
    conn = _FakeConn(
        tables=set(pgs.EXPECTED_TABLES_FULL),
        columns=columns,
        checks=set(pgs.EXPECTED_CHECK_CONSTRAINTS),
    )
    pgs._validate_schema_contracts(
        conn,  # type: ignore[arg-type]
        require_history_select=False,
        require_full=True,
    )
    param_blobs = " ".join(str(params) for _, params in conn.queries)
    joined = "\n".join(q for q, _ in conn.queries).lower()
    assert "workflow_profile_definitions" in param_blobs
    assert "pg_constraint" in joined
