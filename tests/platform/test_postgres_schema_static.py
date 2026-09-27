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
        "organization",
        "audit_events",
        "blob_artifacts",
        "blob_backup_set_org_fk",
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


class _Rows:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return list(self._rows)

    def fetchone(self) -> tuple | None:
        return self._rows[0] if self._rows else None


class MemorySettingsStore:
    """In-memory stand-in for platform.platform_settings. Not a SQLite fallback."""

    def __init__(self, *, ready: bool = True, down: bool = False) -> None:
        self.ready = ready
        self.down = down
        self.settings: dict[tuple[str, str], dict] = {}
        self.revisions: list[dict] = []
        self.integrity: dict[str, str] = {}
        self.lock_statements: list[str] = []
        self.live_connections = 0


class _MemoryConn:
    def __init__(self, store: MemorySettingsStore) -> None:
        self.store = store
        self.closed = False
        store.live_connections += 1

    def execute(self, sql: str, params=None):
        compact = " ".join(sql.split())
        values = tuple(params or ())
        import psycopg

        if "pg_has_role" in compact:
            return _Rows([("qmtool_runtime", "qmtool_runtime", True, True, False, False)])
        if "LIMIT 0" in compact:
            if not self.store.ready:
                raise psycopg.errors.UndefinedTable("platform settings table missing")
            return _Rows([])
        if compact.startswith("SELECT COUNT(*)"):
            if "platform_settings_integrity" in compact:
                count = len(self.store.integrity)
            elif "platform_setting_revisions" in compact:
                count = len(self.store.revisions)
            else:
                count = len(self.store.settings)
            return _Rows([(count,)])
        if "FOR UPDATE" in compact:
            self.store.lock_statements.append(compact)
            module_id = str(values[0])
            rows = [
                (key, row["value_json"], row["revision"])
                for (module, key), row in sorted(self.store.settings.items())
                if module == module_id
            ]
            return _Rows(rows)
        if compact.startswith("SELECT setting_key, value_json"):
            module_id = str(values[0])
            rows = [
                (key, row["value_json"])
                for (module, key), row in sorted(self.store.settings.items())
                if module == module_id
            ]
            return _Rows(rows)
        if compact.startswith("SELECT module_id, setting_key"):
            return _Rows([(module, key) for module, key in self.store.settings])
        if compact.startswith("SELECT integrity_value"):
            key = str(values[0])
            if key not in self.store.integrity:
                return _Rows([])
            return _Rows([(self.store.integrity[key],)])
        if compact.startswith("DELETE FROM platform.platform_settings "):
            module_id, _, key = str(values[0]), str(values[1]), str(values[2])
            self.store.settings.pop((module_id, key), None)
            return _Rows([])
        if compact.startswith("DELETE FROM platform.platform_settings_integrity"):
            self.store.integrity.pop(str(values[0]), None)
            return _Rows([])
        if compact.startswith("INSERT INTO platform.platform_settings "):
            if "ON CONFLICT" in compact:
                module_id, key = str(values[0]), str(values[2])
                self.store.settings[(module_id, key)] = {
                    "value_json": str(values[4]),
                    "revision": int(values[6]),
                    "actor": str(values[8]),
                    "value_type": str(values[3]),
                }
            else:
                scope_kind, scope_id, module_id = str(values[0]), str(values[1]), str(values[2])
                if scope_kind != "MODULE" or scope_id != module_id:
                    raise AssertionError("non-module settings row")
                self.store.settings[(module_id, str(values[3]))] = {
                    "value_json": str(values[5]),
                    "revision": int(values[7]),
                    "actor": str(values[9]),
                    "value_type": str(values[4]),
                }
            return _Rows([])
        if compact.startswith("INSERT INTO platform.platform_setting_revisions"):
            if "ON CONFLICT" in compact or compact.find("VALUES (%s, 'MODULE'") >= 0 or "VALUES (%s, 'MODULE'" in compact:
                self.store.revisions.append(
                    {
                        "module_id": str(values[1]),
                        "setting_key": str(values[3]),
                        "revision_no": int(values[4]),
                        "actor": str(values[8]),
                        "new_value_json": str(values[6]),
                    }
                )
            else:
                scope_kind, scope_id, module_id = str(values[1]), str(values[2]), str(values[3])
                if scope_kind != "MODULE" or scope_id != module_id:
                    raise AssertionError("non-module revision row")
                self.store.revisions.append(
                    {
                        "module_id": module_id,
                        "setting_key": str(values[4]),
                        "revision_no": int(values[5]),
                        "actor": str(values[9]),
                        "new_value_json": str(values[7]),
                    }
                )
            return _Rows([])
        if compact.startswith("INSERT INTO platform.platform_settings_integrity"):
            self.store.integrity[str(values[0])] = str(values[1])
            return _Rows([])
        raise AssertionError(f"unexpected settings SQL: {compact}")

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.store.live_connections -= 1


def _install_settings_store(monkeypatch, store: MemorySettingsStore) -> None:
    import psycopg

    def connect(_dsn: str, connect_timeout: int = 5):
        if store.down:
            raise psycopg.OperationalError("postgres settings down")
        return _MemoryConn(store)

    monkeypatch.setattr(psycopg, "connect", connect)


def test_backend_attach_uses_one_postgres_repository_and_skips_sqlite(tmp_path: Path, monkeypatch) -> None:
    import sqlite3

    from qm_platform.runtime.container import RuntimeContainer
    from qm_platform.settings.persistence_bootstrap import attach_settings_persistence
    from qm_platform.settings.postgres_settings_repository import PostgresSettingsRepository
    from qm_platform.settings.settings_registry import SettingsRegistry
    from qm_platform.settings.settings_service import SettingsService
    from modules.usermanagement.module import USERMANAGEMENT_SETTINGS_CONTRIBUTION

    store = MemorySettingsStore()
    _install_settings_store(monkeypatch, store)

    def refuse_sqlite(*_args, **_kwargs):
        raise AssertionError("backend attach opened sqlite")

    monkeypatch.setattr(sqlite3, "connect", refuse_sqlite)
    legacy = tmp_path / "storage" / "platform" / "platform_settings.db"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy-sqlite-not-runtime")
    before = legacy.read_bytes()

    container = RuntimeContainer()
    service = SettingsService(SettingsRegistry())
    service.registry.register(USERMANAGEMENT_SETTINGS_CONTRIBUTION)
    container.register_port("settings_service", service)
    container.register_port("app_home", tmp_path)
    container.register_port("usermanagement_postgres_dsn", "postgresql://qmtool_runtime@db/qmtool")
    attach_settings_persistence(container, app_home=tmp_path)

    repository = service.repository
    assert isinstance(repository, PostgresSettingsRepository)
    assert set(repository.__dict__) == {"_dsn"}
    assert store.live_connections == 0
    assert legacy.read_bytes() == before
    loaded = service.get_module_settings("usermanagement")
    assert loaded["seed_mode"] == "admin_only"
    assert store.lock_statements

    restarted = SettingsService(service.registry)
    container.register_port("settings_service", restarted)
    attach_settings_persistence(container, app_home=tmp_path)
    assert restarted.get_module_settings("usermanagement")["seed_mode"] == "admin_only"
    assert restarted.repository is not repository
    assert store.live_connections == 0


def test_backend_settings_outage_and_missing_schema_fail_closed(tmp_path: Path, monkeypatch) -> None:
    import sqlite3

    from qm_platform.runtime.container import RuntimeContainer
    from qm_platform.settings.persistence_bootstrap import attach_settings_persistence
    from qm_platform.settings.postgres_settings_repository import SettingsPersistenceUnavailable
    from qm_platform.settings.settings_registry import SettingsRegistry
    from qm_platform.settings.settings_service import SettingsService

    def refuse_sqlite(*_args, **_kwargs):
        raise AssertionError("outage path opened sqlite")

    monkeypatch.setattr(sqlite3, "connect", refuse_sqlite)
    down = MemorySettingsStore(down=True)
    _install_settings_store(monkeypatch, down)
    container = RuntimeContainer()
    container.register_port("settings_service", SettingsService(SettingsRegistry()))
    container.register_port("app_home", tmp_path)
    container.register_port("usermanagement_postgres_dsn", "postgresql://qmtool_runtime@db/qmtool")
    with pytest.raises(SettingsPersistenceUnavailable, match="unavailable"):
        attach_settings_persistence(container, app_home=tmp_path)
    assert not (tmp_path / "storage" / "platform" / "platform_settings.db").exists()

    missing = MemorySettingsStore(ready=False)
    _install_settings_store(monkeypatch, missing)
    with pytest.raises(SettingsPersistenceUnavailable, match="runtime DDL is forbidden"):
        attach_settings_persistence(container, app_home=tmp_path)
    assert not (tmp_path / "storage" / "platform" / "platform_settings.db").exists()


def test_postgres_settings_keep_governance_actor_and_module_scope(tmp_path: Path, monkeypatch) -> None:
    from datetime import datetime, timezone

    from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
    from modules.usermanagement.contracts import issue_user_context
    from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
    from qm_platform.settings.postgres_settings_repository import PostgresSettingsRepository
    from qm_platform.settings.settings_registry import SettingsRegistry
    from qm_platform.settings.settings_service import SettingsService

    store = MemorySettingsStore()
    _install_settings_store(monkeypatch, store)
    service = SettingsService(SettingsRegistry())
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
    service.attach_persistence(
        PostgresSettingsRepository("postgresql://qmtool_runtime@db/qmtool"),
        None,
        require_residual_if_present=False,
    )
    actor = issue_user_context(
        user_id="u1",
        session_id="s1",
        request_id="r1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
        username="admin",
        global_roles=["Admin"],
        is_qmb=False,
        authenticated_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError, match="governance_critical"):
        service.set_module_settings(
            "signature",
            {"require_password": False, "default_mode": "visual"},
            actor=actor,
        )
    service.set_module_settings(
        "signature",
        {"require_password": False, "default_mode": "visual"},
        actor=actor,
        acknowledge_governance_change=True,
        reason="governance-check",
    )
    assert service.get_module_settings("signature")["require_password"] is False
    assert store.revisions[-1]["actor"] == "u1"
    assert store.revisions[-1]["actor"] != INSTALLATION_ORGANIZATION_ID
    assert store.lock_statements
    assert store.live_connections == 0


def test_documents_backend_path_reuses_postgres_repository_and_skips_settings_sqlite(
    tmp_path: Path, monkeypatch
) -> None:
    import sqlite3

    from qm_platform.persistence.database_evolution import DatabaseEvolutionService
    from qm_platform.runtime.backend_bootstrap import wire_backend_documents
    from qm_platform.runtime.container import RuntimeContainer
    from qm_platform.runtime.lifecycle import LifecycleManager
    from qm_platform.settings.postgres_settings_repository import PostgresSettingsRepository
    from qm_platform.settings.settings_registry import SettingsRegistry
    from qm_platform.settings.settings_service import SettingsService

    store = MemorySettingsStore()
    _install_settings_store(monkeypatch, store)
    service = SettingsService(SettingsRegistry())
    repository = PostgresSettingsRepository("postgresql://qmtool_runtime@db/qmtool")
    service.attach_persistence(repository, None, require_residual_if_present=False)
    container = RuntimeContainer()
    container.register_port("settings_service", service)
    container.register_port("app_home", tmp_path)
    container.register_port("usermanagement_postgres_dsn", "postgresql://qmtool_runtime@db/qmtool")
    seen: list[object] = []
    original_init = DatabaseEvolutionService.__init__

    def _init(self, *args, **kwargs):
        seen.append(kwargs.get("settings_repository"))
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(DatabaseEvolutionService, "__init__", _init)
    monkeypatch.setattr(LifecycleManager, "wire", lambda self, module_id: None)
    monkeypatch.setattr(LifecycleManager, "start", lambda self, strict=True: None)
    real_connect = sqlite3.connect
    opened: list[str] = []

    def guarded(database, *args, **kwargs):
        opened.append(str(database))
        if "platform_settings" in str(database).replace("\\", "/"):
            raise AssertionError(database)
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded)
    wire_backend_documents(container)
    assert seen == [repository]
    assert service.repository is repository
    assert not (tmp_path / "storage" / "platform" / "platform_settings.db").exists()
    assert not any("platform_settings" in path.replace("\\", "/") for path in opened)
    assert store.live_connections == 0


def test_productive_documents_path_does_not_open_settings_sqlite(tmp_path: Path, monkeypatch) -> None:
    import sqlite3

    from qm_platform.runtime.backend_bootstrap import wire_backend_documents
    from qm_platform.runtime.container import RuntimeContainer
    from qm_platform.runtime.lifecycle import LifecycleManager
    from qm_platform.settings.postgres_settings_repository import PostgresSettingsRepository
    from qm_platform.settings.settings_registry import SettingsRegistry
    from qm_platform.settings.settings_service import SettingsService

    store = MemorySettingsStore()
    _install_settings_store(monkeypatch, store)
    service = SettingsService(SettingsRegistry())
    repository = PostgresSettingsRepository("postgresql://qmtool_runtime@db/qmtool")
    service.attach_persistence(repository, None, require_residual_if_present=False)
    container = RuntimeContainer()
    container.register_port("settings_service", service)
    container.register_port("app_home", tmp_path)
    dsn = "postgresql://qmtool_runtime@db/qmtool"
    container.register_port("usermanagement_postgres_dsn", dsn)
    container.register_port("documents_postgres_dsn", dsn)
    container.register_port("registry_postgres_dsn", dsn)
    container.register_port("signature_postgres_dsn", dsn)
    monkeypatch.setattr("modules.documents.api.ensure_postgres_schema_ready", lambda _container: None)
    monkeypatch.setattr("modules.registry.api.ensure_postgres_schema_ready", lambda _container: None)
    monkeypatch.setattr("modules.signature.api.ensure_postgres_schema_ready", lambda _container: None)
    monkeypatch.setattr(LifecycleManager, "wire", lambda self, module_id: None)
    monkeypatch.setattr(LifecycleManager, "start", lambda self, strict=True: None)

    def refuse_sqlite(*_args, **_kwargs):
        raise AssertionError("productive documents path opened sqlite")

    monkeypatch.setattr(sqlite3, "connect", refuse_sqlite)
    wire_backend_documents(container)
    assert service.repository is repository
    assert not (tmp_path / "storage" / "platform" / "platform_settings.db").exists()
    assert store.live_connections == 0


def _refuse_platform_settings_sqlite(monkeypatch) -> None:
    import sqlite3

    real_connect = sqlite3.connect

    def guarded(database, *args, **kwargs):
        if "platform_settings" in str(database).replace("\\", "/"):
            raise AssertionError(database)
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded)


def _postgres_residual_backup(tmp_path: Path, monkeypatch):
    import sqlite3

    from qm_platform.persistence.database_evolution import (
        DatabaseEvolutionService,
        DatabaseSpec,
        MigrationStep,
    )
    from qm_platform.settings.actors import MIGRATION_SETTINGS_IMPORT_ACTOR
    from qm_platform.settings.postgres_settings_repository import PostgresSettingsRepository
    from qm_platform.settings.testing import write_residual_policy_archive

    _refuse_platform_settings_sqlite(monkeypatch)
    store = MemorySettingsStore()
    _install_settings_store(monkeypatch, store)
    repository = PostgresSettingsRepository("postgresql://qmtool_runtime@db/qmtool")
    residual = write_residual_policy_archive(
        tmp_path,
        {"usermanagement": {"password_policy": {"min_length": 11}}},
    )
    digest = residual.sha256()
    repository.set_integrity(
        PostgresSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
        digest,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    repository.set_integrity(
        PostgresSettingsRepository.INTEGRITY_CUTOVER_STATUS,
        "completed",
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    sql_path = tmp_path / "0001_module_row.sql"
    sql_path.write_text(
        "CREATE TABLE module_row (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )
    spec = DatabaseSpec(
        database_id="documents",
        path=tmp_path / "storage" / "documents" / "documents.db",
        migrations=(MigrationStep(version=1, name="initial", sql_path=sql_path),),
    )
    service = DatabaseEvolutionService(
        app_home=tmp_path,
        settings_repository=repository,
    )
    service.migrate((spec,), reason="seed_module_sqlite")
    before = spec.path.read_bytes()
    backup = service.create_backup(specs=(spec,), reason="pg_residual")
    with sqlite3.connect(spec.path) as conn:
        conn.execute("CREATE TABLE restore_drill_mutation (id INTEGER)")
        conn.commit()
    conn.close()
    mutated = spec.path.read_bytes()
    assert mutated != before
    return store, repository, service, spec, backup, before, mutated, digest


def _backup_names(tmp_path: Path) -> list[str]:
    root = tmp_path / "storage" / "platform" / "backups" / "databases"
    return sorted(path.name for path in root.iterdir())


def test_postgres_residual_backup_restores_other_sqlite_without_settings_db(
    tmp_path: Path, monkeypatch
) -> None:
    import json

    _store, _repository, service, spec, backup, before, _mutated, digest = (
        _postgres_residual_backup(tmp_path, monkeypatch)
    )
    manifest = json.loads((Path(backup.path) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["residual_archive"]["present"] is True
    assert manifest["residual_archive"]["cutover_status"] == "completed"
    assert manifest["residual_archive"]["db_hash_anchor"] == digest
    assert [entry["database_id"] for entry in manifest["databases"]] == ["documents"]
    settings_db = tmp_path / "storage" / "platform" / "platform_settings.db"

    result = service.restore(backup.backup_id, specs=(spec,))

    assert result["ok"] is True
    assert spec.path.read_bytes() == before
    assert not settings_db.exists()
    from qm_platform.settings.residual_store import ResidualSettingsStore

    assert ResidualSettingsStore.under_app_home(tmp_path).sha256() == digest


def test_postgres_integrity_mismatch_rejects_restore_before_mutation(
    tmp_path: Path, monkeypatch
) -> None:
    from qm_platform.persistence import DatabaseEvolutionError
    from qm_platform.settings.postgres_settings_repository import PostgresSettingsRepository
    from qm_platform.settings.residual_store import ResidualSettingsStore

    store, _repository, service, spec, backup, _before, mutated, digest = (
        _postgres_residual_backup(tmp_path, monkeypatch)
    )
    store.integrity[PostgresSettingsRepository.INTEGRITY_RESIDUAL_SHA256] = "0" * 64
    backups = _backup_names(tmp_path)
    residual_before = ResidualSettingsStore.under_app_home(tmp_path).archive_path.read_bytes()
    settings_db = tmp_path / "storage" / "platform" / "platform_settings.db"

    with pytest.raises(DatabaseEvolutionError, match="db_hash_anchor"):
        service.restore(backup.backup_id, specs=(spec,))

    assert spec.path.read_bytes() == mutated
    assert _backup_names(tmp_path) == backups
    assert ResidualSettingsStore.under_app_home(tmp_path).archive_path.read_bytes() == residual_before
    assert not settings_db.exists()
    assert ResidualSettingsStore.under_app_home(tmp_path).sha256() == digest


def test_unreadable_postgres_integrity_rejects_restore_before_mutation(
    tmp_path: Path, monkeypatch
) -> None:
    from qm_platform.persistence import DatabaseEvolutionError
    from qm_platform.settings.residual_store import ResidualSettingsStore

    store, _repository, service, spec, backup, _before, mutated, _digest = (
        _postgres_residual_backup(tmp_path, monkeypatch)
    )
    store.down = True
    backups = _backup_names(tmp_path)
    residual_before = ResidualSettingsStore.under_app_home(tmp_path).archive_path.read_bytes()
    settings_db = tmp_path / "storage" / "platform" / "platform_settings.db"

    with pytest.raises(DatabaseEvolutionError, match="integrity metadata unavailable"):
        service.restore(backup.backup_id, specs=(spec,))

    assert spec.path.read_bytes() == mutated
    assert _backup_names(tmp_path) == backups
    assert ResidualSettingsStore.under_app_home(tmp_path).archive_path.read_bytes() == residual_before
    assert not settings_db.exists()


def test_postgres_residual_rollback_accepts_safety_backup_without_settings_db(
    tmp_path: Path, monkeypatch
) -> None:
    import os

    _store, _repository, service, spec, backup, _before, mutated, _digest = (
        _postgres_residual_backup(tmp_path, monkeypatch)
    )
    real_replace = os.replace
    failed = {"done": False}

    def fail_first_live_replace(src, dst, *args, **kwargs):
        if not failed["done"] and Path(dst) == spec.path:
            failed["done"] = True
            raise OSError("injected restore failure")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", fail_first_live_replace)
    settings_db = tmp_path / "storage" / "platform" / "platform_settings.db"
    names_before = _backup_names(tmp_path)

    with pytest.raises(OSError, match="injected restore failure"):
        service.restore(backup.backup_id, specs=(spec,))

    assert failed["done"] is True
    assert spec.path.read_bytes() == mutated
    assert len(_backup_names(tmp_path)) == len(names_before) + 1
    assert not settings_db.exists()
