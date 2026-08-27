"""Bootstrap provenance: fresh vs pre-J03 vs post-J03 empty must not be guessed after migrate."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from interfaces.cli.bootstrap import build_container
from modules.documents.bootstrap_provenance import (
    DocumentsBootstrapProvenance,
    derive_documents_bootstrap_provenance,
)
from modules.documents.errors import ValidationError
from qm_platform.persistence.database_evolution import (
    DATABASE_PREFLIGHT_STATUSES_PORT,
    DatabaseEvolutionService,
    DatabaseSpec,
    DatabaseStatus,
    MigrationStep,
)
from qm_platform.persistence.path_resolver import resolve_bootstrap_absolute_path
from qm_platform.runtime import bootstrap as runtime_bootstrap


def _divergent_local_profiles(path: Path) -> None:
    bundled = Path("modules/documents/workflow_profiles.json")
    payload = json.loads(bundled.read_text(encoding="utf-8"))
    payload["profiles"][0]["label"] = "Local Divergent Long Release"
    payload["profiles"].append(
        {
            "profile_id": "local_only_bootstrap",
            "label": "Local Only Bootstrap",
            "control_class": "CONTROLLED",
            "phases": ["IN_PROGRESS", "APPROVED"],
            "four_eyes_required": False,
            "signature_required_transitions": [],
            "requires_editors": True,
            "requires_reviewers": False,
            "requires_approvers": False,
            "allows_content_changes": True,
            "release_evidence_mode": "WORKFLOW",
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _prepare_runtime(tmp_path: Path, monkeypatch):
    from modules.documents.module import create_documents_module_contract
    from qm_platform.runtime.lifecycle import LifecycleManager

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.delenv("QMTOOL_DOCUMENTS_LOCAL_WIRING", raising=False)
    container = build_container()
    lifecycle = LifecycleManager(container)
    # Replace client HTTP documents contract with backend SQLite ownership for provenance.
    for contract in runtime_bootstrap.core_module_contracts():
        if contract.module_id == "documents":
            lifecycle.prepare(create_documents_module_contract())
        else:
            lifecycle.prepare(contract)
    container.register_port("documents_runtime_owner", "backend")
    return container, lifecycle


def test_derive_provenance_mapping() -> None:
    missing = DatabaseStatus(
        database_id="documents",
        path="x",
        state="missing",
        current_version=0,
        target_version=2,
        pending_versions=(1, 2),
        integrity="not_run",
    )
    assert derive_documents_bootstrap_provenance(missing) == DocumentsBootstrapProvenance.FRESH_INSTALL

    v1 = DatabaseStatus(
        database_id="documents",
        path="x",
        state="pending",
        current_version=1,
        target_version=2,
        pending_versions=(2,),
        integrity="ok",
    )
    assert derive_documents_bootstrap_provenance(v1) == DocumentsBootstrapProvenance.PRE_J03_UPGRADE

    v2 = DatabaseStatus(
        database_id="documents",
        path="x",
        state="current",
        current_version=2,
        target_version=2,
        pending_versions=(),
        integrity="ok",
    )
    assert derive_documents_bootstrap_provenance(v2) == DocumentsBootstrapProvenance.POST_J03_SCHEMA


def test_fresh_app_home_with_divergent_local_profiles_uses_bundled_seed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container, lifecycle = _prepare_runtime(tmp_path, monkeypatch)
    local_profiles = resolve_bootstrap_absolute_path(tmp_path, "documents", "profiles_file")
    _divergent_local_profiles(local_profiles)

    runtime_bootstrap.activate_core_modules(container, lifecycle)

    statuses = container.get_port(DATABASE_PREFLIGHT_STATUSES_PORT)
    provenance = derive_documents_bootstrap_provenance(statuses["documents"])
    assert provenance == DocumentsBootstrapProvenance.FRESH_INSTALL
    service = container.get_port("documents_service")
    store = service._profile_store
    codes = {row["profile_code"] for row in store.list_definitions()}
    assert "local_only_bootstrap" not in codes
    assert "long_release" in codes
    assert any(row.classification == "SEED" for row in store.last_import_report)
    assert all(row.source_path.endswith("workflow_profiles.json") for row in store.last_import_report)
    # Bundled seed path, not the divergent local app-home copy.
    assert not any("Local Divergent" in (row.block_reason or "") for row in store.last_import_report)
    assert service.get_profile("long_release").label != "Local Divergent Long Release"


def test_v1_documents_db_imports_local_profiles_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container, lifecycle = _prepare_runtime(tmp_path, monkeypatch)
    local_profiles = resolve_bootstrap_absolute_path(tmp_path, "documents", "profiles_file")
    _divergent_local_profiles(local_profiles)

    service, specs = runtime_bootstrap.configure_database_evolution(container, lifecycle)
    documents_spec = next(spec for spec in specs if spec.database_id == "documents")
    v1_only = DatabaseSpec(
        database_id="documents",
        path=documents_spec.path,
        migrations=(
            MigrationStep(
                version=1,
                name="initial",
                sql_path=Path("modules/documents/migrations/0001_initial.sql").resolve(),
            ),
        ),
    )
    DatabaseEvolutionService(app_home=tmp_path).migrate((v1_only,), reason="test_v1_seed")
    pre = service.status(documents_spec)
    assert pre.current_version == 1
    assert derive_documents_bootstrap_provenance(pre) == DocumentsBootstrapProvenance.PRE_J03_UPGRADE

    runtime_bootstrap.activate_core_modules(container, lifecycle)

    statuses = container.get_port(DATABASE_PREFLIGHT_STATUSES_PORT)
    provenance = derive_documents_bootstrap_provenance(statuses["documents"])
    assert provenance == DocumentsBootstrapProvenance.PRE_J03_UPGRADE
    store = container.get_port("documents_service")._profile_store
    codes = {row["profile_code"] for row in store.list_definitions()}
    assert "local_only_bootstrap" in codes
    assert any(row.classification == "MIGRATED" for row in store.last_import_report)
    assert any(
        row.import_status == "imported" and "local_only_bootstrap" == row.profile_id
        for row in store.last_import_report
    )
    assert store._is_pre_j03_upgrade is True


def test_post_j03_empty_profiles_are_not_treated_as_fresh_install(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container, lifecycle = _prepare_runtime(tmp_path, monkeypatch)
    local_profiles = resolve_bootstrap_absolute_path(tmp_path, "documents", "profiles_file")
    _divergent_local_profiles(local_profiles)

    service, specs = runtime_bootstrap.configure_database_evolution(container, lifecycle)
    service.migrate(specs, reason="test_post_j03_empty")
    documents_spec = next(spec for spec in specs if spec.database_id == "documents")
    pre = service.status(documents_spec)
    assert pre.current_version >= 2
    assert derive_documents_bootstrap_provenance(pre) == DocumentsBootstrapProvenance.POST_J03_SCHEMA

    with sqlite3.connect(documents_spec.path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "workflow_profile_definitions" in tables
        # Schema is J03 but profile stock is empty/manipulated.
        conn.execute("DELETE FROM workflow_profile_transitions")
        conn.execute("DELETE FROM workflow_profile_versions")
        conn.execute("DELETE FROM workflow_profile_definitions")
        conn.execute("DELETE FROM document_type_definitions")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM workflow_profile_definitions").fetchone()[0] == 0

    with pytest.raises(ValidationError, match="refusing silent re-seed"):
        runtime_bootstrap.activate_core_modules(container, lifecycle)


class _FakeStockResult:
    def __init__(self, count: int) -> None:
        self._count = count

    def fetchone(self):
        return (self._count,)


class _FakeCombinedStockResult:
    def __init__(self, definitions: int, imports: int, types: int) -> None:
        self._row = {
            "definitions": definitions,
            "imports": imports,
            "types": types,
        }

    def fetchone(self):
        return self._row


_STOCK_TABLES = (
    "workflow_profile_definitions",
    "workflow_profile_imports",
    "document_type_definitions",
)


def _is_combined_stock_sql(sql: str) -> bool:
    return all(table in sql for table in _STOCK_TABLES)


class _FakeStockConn:
    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts

    def execute(self, sql, params=()):
        sql_str = str(sql)
        if "pg_advisory_xact_lock" in sql_str:
            return _FakeStockResult(0)
        if _is_combined_stock_sql(sql_str):
            return _FakeCombinedStockResult(
                self._counts["workflow_profile_definitions"],
                self._counts["workflow_profile_imports"],
                self._counts["document_type_definitions"],
            )
        for table, count in self._counts.items():
            if table in sql_str:
                return _FakeStockResult(count)
        raise AssertionError(f"unexpected stock SQL: {sql}")


class _FakeStockRepository:
    def __init__(self, *, definitions: int = 0, imports: int = 0, types: int = 0) -> None:
        self.connect_count = 0
        self._counts = {
            "workflow_profile_definitions": definitions,
            "workflow_profile_imports": imports,
            "document_type_definitions": types,
        }

    def _connect(self):
        from contextlib import contextmanager

        self.connect_count += 1

        @contextmanager
        def _cm():
            yield _FakeStockConn(self._counts)

        return _cm()


class _RecordingTxnConn:
    def __init__(self, counts: dict[str, int], sql_log: list[tuple[str, tuple]]) -> None:
        self._counts = counts
        self.sql_log = sql_log

    def execute(self, sql, params=()):
        param_tuple = tuple(params) if params else ()
        self.sql_log.append((str(sql), param_tuple))
        sql_str = str(sql)
        if "pg_advisory_xact_lock" in sql_str:
            return _FakeStockResult(0)
        if _is_combined_stock_sql(sql_str):
            return _FakeCombinedStockResult(
                self._counts["workflow_profile_definitions"],
                self._counts["workflow_profile_imports"],
                self._counts["document_type_definitions"],
            )
        for table, count in self._counts.items():
            if table in sql_str:
                return _FakeStockResult(count)
        raise AssertionError(f"unexpected stock SQL: {sql}")


class _FakeTxnRepository:
    def __init__(self, *, definitions: int = 0, imports: int = 0, types: int = 0) -> None:
        self.sql_log: list[tuple[str, tuple]] = []
        self.commits = 0
        self.rollbacks = 0
        self._in_txn = False
        self._conn = _RecordingTxnConn(
            {
                "workflow_profile_definitions": definitions,
                "workflow_profile_imports": imports,
                "document_type_definitions": types,
            },
            self.sql_log,
        )
        self.txn_connections: list[int] = []

    def write_transaction(self):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            if self._in_txn:
                yield
                return
            self._in_txn = True
            try:
                yield
                self.commits += 1
            except Exception:
                self.rollbacks += 1
                raise
            finally:
                self._in_txn = False

        return _cm()

    def _connect(self):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            assert self._in_txn, "seed must use _connect inside write_transaction"
            self.txn_connections.append(id(self._conn))
            yield self._conn

        return _cm()


def test_postgres_stock_all_empty_is_not_fresh_install() -> None:
    from modules.documents.bootstrap_provenance import (
        observe_postgres_profile_stock,
        resolve_documents_postgres_bootstrap_provenance,
    )

    repo = _FakeStockRepository()
    provenance = resolve_documents_postgres_bootstrap_provenance(repo)
    stock = observe_postgres_profile_stock(_FakeStockRepository())
    assert provenance == DocumentsBootstrapProvenance.POST_J03_SCHEMA
    assert provenance != DocumentsBootstrapProvenance.FRESH_INSTALL
    assert stock == (0, 0, 0)
    assert repo.connect_count == 1


def test_postgres_stock_observation_uses_one_connection() -> None:
    from modules.documents.bootstrap_provenance import observe_postgres_profile_stock

    repo = _FakeStockRepository(definitions=2, imports=1, types=3)
    stock = observe_postgres_profile_stock(repo)
    assert stock == (2, 1, 3)
    assert repo.connect_count == 1


def test_postgres_stock_definitions_are_post_j03() -> None:
    from modules.documents.bootstrap_provenance import resolve_documents_postgres_bootstrap_provenance

    provenance = resolve_documents_postgres_bootstrap_provenance(
        _FakeStockRepository(definitions=2)
    )
    assert provenance == DocumentsBootstrapProvenance.POST_J03_SCHEMA


def test_postgres_leftover_imports_or_types_are_post_j03_not_pre_j03() -> None:
    from modules.documents.bootstrap_provenance import resolve_documents_postgres_bootstrap_provenance

    leftover_imports = resolve_documents_postgres_bootstrap_provenance(
        _FakeStockRepository(imports=1)
    )
    leftover_types = resolve_documents_postgres_bootstrap_provenance(
        _FakeStockRepository(types=1)
    )
    assert leftover_imports == DocumentsBootstrapProvenance.POST_J03_SCHEMA
    assert leftover_types == DocumentsBootstrapProvenance.POST_J03_SCHEMA
    assert leftover_imports != DocumentsBootstrapProvenance.PRE_J03_UPGRADE
    assert leftover_imports != DocumentsBootstrapProvenance.FRESH_INSTALL


def test_postgres_stock_observation_fails_closed() -> None:
    from modules.documents.bootstrap_provenance import resolve_documents_postgres_bootstrap_provenance

    class _Broken:
        def _connect(self):
            raise RuntimeError("dsn unreachable")

    with pytest.raises(RuntimeError, match="cannot observe PostgreSQL documents bootstrap stock"):
        resolve_documents_postgres_bootstrap_provenance(_Broken())


def test_explicit_seed_all_zero_uses_fresh_and_ensure_seeded(monkeypatch) -> None:
    from modules.documents.api import (
        DOCUMENTS_PG_SEED_ADVISORY_LOCK_KEY,
        seed_postgres_workflow_profiles,
    )
    from modules.documents.postgres_schema import ADVISORY_LOCK_KEY as MIGRATE_LOCK_KEY
    from modules.documents.workflow_profile_seed_reader import WorkflowProfileSeedReader

    seen: list[object] = []
    repo = _FakeTxnRepository()
    monkeypatch.setattr(
        "modules.documents.postgres_repository.PostgresDocumentsRepository",
        lambda dsn: repo,
    )

    class _Store:
        def __init__(self, repository, *, bundled_seed_path, legacy_profiles_path, bootstrap_provenance):
            self._repo = repository
            seen.append(bootstrap_provenance)

        def ensure_seeded(self, seed_reader) -> None:
            seen.append(type(seed_reader))
            with self._repo.write_transaction():
                with self._repo._connect() as conn:
                    conn.execute("SELECT COUNT(*) FROM workflow_profile_definitions")

    monkeypatch.setattr("modules.documents.workflow_profile_store.WorkflowProfileRelationalStore", _Store)
    seed_postgres_workflow_profiles("postgresql://example.invalid/db")
    assert seen[0] == DocumentsBootstrapProvenance.FRESH_INSTALL
    assert seen[1] is WorkflowProfileSeedReader
    assert DOCUMENTS_PG_SEED_ADVISORY_LOCK_KEY != MIGRATE_LOCK_KEY
    assert "pg_advisory_xact_lock" in repo.sql_log[0][0]
    assert repo.sql_log[0][1] == (DOCUMENTS_PG_SEED_ADVISORY_LOCK_KEY,)
    combined_indexes = [
        i for i, (sql, _p) in enumerate(repo.sql_log) if _is_combined_stock_sql(sql)
    ]
    assert len(combined_indexes) == 1
    assert combined_indexes[0] > 0
    per_table_count_executes = [
        sql
        for sql, _p in repo.sql_log
        if "COUNT(*)" in sql and not _is_combined_stock_sql(sql)
    ]
    assert len(per_table_count_executes) == 1
    assert repo.commits == 1
    assert repo.rollbacks == 0
    assert len(set(repo.txn_connections)) == 1


def test_explicit_seed_residue_is_refused_without_fresh(monkeypatch) -> None:
    from modules.documents.api import seed_postgres_workflow_profiles

    repo = _FakeTxnRepository(imports=1)
    monkeypatch.setattr(
        "modules.documents.postgres_repository.PostgresDocumentsRepository",
        lambda dsn: repo,
    )
    constructed: list[object] = []

    class _Store:
        def __init__(self, *args, **kwargs):
            constructed.append(kwargs.get("bootstrap_provenance"))

        def ensure_seeded(self, seed_reader) -> None:
            constructed.append("ensure_seeded")

    monkeypatch.setattr("modules.documents.workflow_profile_store.WorkflowProfileRelationalStore", _Store)
    with pytest.raises(ValidationError, match="refusing silent re-seed"):
        seed_postgres_workflow_profiles("postgresql://example.invalid/db")
    assert constructed == []
    assert "pg_advisory_xact_lock" in repo.sql_log[0][0]
    assert repo.rollbacks == 1
    assert repo.commits == 0


def test_explicit_seed_populated_uses_post_j03_not_fresh(monkeypatch) -> None:
    from modules.documents.api import seed_postgres_workflow_profiles

    repo = _FakeTxnRepository(definitions=4)
    monkeypatch.setattr(
        "modules.documents.postgres_repository.PostgresDocumentsRepository",
        lambda dsn: repo,
    )
    seen: list[object] = []

    class _Store:
        def __init__(self, repository, *, bundled_seed_path, legacy_profiles_path, bootstrap_provenance):
            seen.append(bootstrap_provenance)

        def ensure_seeded(self, seed_reader) -> None:
            seen.append("ensure_seeded")

    monkeypatch.setattr("modules.documents.workflow_profile_store.WorkflowProfileRelationalStore", _Store)
    seed_postgres_workflow_profiles("postgresql://example.invalid/db")
    assert seen == [DocumentsBootstrapProvenance.POST_J03_SCHEMA, "ensure_seeded"]
    assert repo.commits == 1


def test_explicit_seed_import_failure_rolls_back(monkeypatch) -> None:
    from modules.documents.api import seed_postgres_workflow_profiles

    repo = _FakeTxnRepository()
    monkeypatch.setattr(
        "modules.documents.postgres_repository.PostgresDocumentsRepository",
        lambda dsn: repo,
    )

    class _Store:
        def __init__(self, repository, *, bundled_seed_path, legacy_profiles_path, bootstrap_provenance):
            pass

        def ensure_seeded(self, seed_reader) -> None:
            raise RuntimeError("import aborted; no partial write")

    monkeypatch.setattr("modules.documents.workflow_profile_store.WorkflowProfileRelationalStore", _Store)
    with pytest.raises(RuntimeError, match="import aborted"):
        seed_postgres_workflow_profiles("postgresql://example.invalid/db")
    assert repo.rollbacks == 1
    assert repo.commits == 0


def test_observe_postgres_stock_single_combined_execute() -> None:
    from modules.documents.bootstrap_provenance import observe_postgres_profile_stock

    repo = _FakeStockRepository(definitions=2, imports=1, types=3)
    stock = observe_postgres_profile_stock(repo)
    assert stock == (2, 1, 3)
    assert repo.connect_count == 1


class _SerializingRecordingTxnConn(_RecordingTxnConn):
    _advisory_lock = threading.Lock()

    def execute(self, sql, params=()):
        sql_str = str(sql)
        param_tuple = tuple(params) if params else ()
        if "pg_advisory_xact_lock" in sql_str:
            self.sql_log.append((sql_str, param_tuple))
            self._advisory_lock.acquire(blocking=True)
            return _FakeStockResult(0)
        return super().execute(sql, params)


class _SerializingTxnRepository(_FakeTxnRepository):
    def __init__(self, *, definitions: int = 0, imports: int = 0, types: int = 0) -> None:
        super().__init__(definitions=definitions, imports=imports, types=types)
        self._conn = _SerializingRecordingTxnConn(
            {
                "workflow_profile_definitions": definitions,
                "workflow_profile_imports": imports,
                "document_type_definitions": types,
            },
            self.sql_log,
        )

    def write_transaction(self):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            if self._in_txn:
                yield
                return
            self._in_txn = True
            try:
                yield
                self.commits += 1
                if self._conn._counts["workflow_profile_definitions"] == 0:
                    self._conn._counts["workflow_profile_definitions"] = 4
            except Exception:
                self.rollbacks += 1
                raise
            finally:
                self._in_txn = False
                if _SerializingRecordingTxnConn._advisory_lock.locked():
                    _SerializingRecordingTxnConn._advisory_lock.release()

        return _cm()


def test_explicit_seed_concurrent_waiter_becomes_post_j03(monkeypatch) -> None:
    from modules.documents.api import seed_postgres_workflow_profiles

    repo = _SerializingTxnRepository()
    outcomes: list[object] = []
    barrier = threading.Barrier(2)
    monkeypatch.setattr(
        "modules.documents.postgres_repository.PostgresDocumentsRepository",
        lambda dsn: repo,
    )

    class _Store:
        def __init__(self, repository, *, bundled_seed_path, legacy_profiles_path, bootstrap_provenance):
            self._provenance = bootstrap_provenance

        def ensure_seeded(self, seed_reader) -> None:
            outcomes.append(self._provenance)

    monkeypatch.setattr("modules.documents.workflow_profile_store.WorkflowProfileRelationalStore", _Store)

    def _run_seed() -> None:
        barrier.wait()
        seed_postgres_workflow_profiles("postgresql://example.invalid/db")

    threads = [threading.Thread(target=_run_seed) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count(DocumentsBootstrapProvenance.FRESH_INSTALL) == 1
    assert outcomes.count(DocumentsBootstrapProvenance.POST_J03_SCHEMA) == 1
    lock_executes = [sql for sql, _p in repo.sql_log if "pg_advisory_xact_lock" in sql]
    assert len(lock_executes) == 2
    combined_executes = [sql for sql, _p in repo.sql_log if _is_combined_stock_sql(sql)]
    assert len(combined_executes) == 2


def test_explicit_seed_unique_violation_propagates(monkeypatch) -> None:
    from modules.documents.api import seed_postgres_workflow_profiles

    try:
        from psycopg.errors import UniqueViolation as _UniqueViolation
    except ImportError:
        _UniqueViolation = type("UniqueViolation", (Exception,), {})

    repo = _FakeTxnRepository()
    monkeypatch.setattr(
        "modules.documents.postgres_repository.PostgresDocumentsRepository",
        lambda dsn: repo,
    )

    class _Store:
        def __init__(self, repository, *, bundled_seed_path, legacy_profiles_path, bootstrap_provenance):
            pass

        def ensure_seeded(self, seed_reader) -> None:
            raise _UniqueViolation("duplicate key value violates unique constraint")

    monkeypatch.setattr("modules.documents.workflow_profile_store.WorkflowProfileRelationalStore", _Store)
    with pytest.raises(_UniqueViolation):
        seed_postgres_workflow_profiles("postgresql://example.invalid/db")
    assert repo.rollbacks == 1
    assert repo.commits == 0
