"""Live PostgreSQL import tests for AP-029 PG01-E registry (collect-only unless Slot 2)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

from modules.registry import postgres_schema as registry_schema
from modules.registry.contracts import RegisterState, RegistryEntry, ReleaseEvidenceMode
from modules.registry.postgres_repository import PostgresRegistryRepository
from modules.registry.sqlite_pg_import import SqlitePgImportError, fingerprint_sqlite_bundle, import_sqlite_to_postgres
from modules.registry.sqlite_repository import SQLiteRegistryRepository
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres

_MIGRATION = Path(__file__).resolve().parents[3] / "modules" / "registry" / "migrations" / "0001_initial.sql"


def _init_sqlite(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(_MIGRATION.read_text(encoding="utf-8"))


def _seed_documents_headers(path: Path, document_ids: list[str]) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE document_headers (document_id TEXT PRIMARY KEY)")
        conn.executemany(
            "INSERT INTO document_headers(document_id) VALUES (?)",
            [(document_id,) for document_id in document_ids],
        )
        conn.commit()


def _entry(document_id: str = "DOC-LIVE") -> RegistryEntry:
    moment = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    return RegistryEntry(
        document_id=document_id,
        active_version=2,
        release_note="live",
        release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
        register_state=RegisterState.VALID,
        is_findable=True,
        valid_from=moment,
        valid_until=None,
        last_update_event_id="evt-live",
        last_update_at=moment,
    )


@pytest.fixture
def live_registry(live_postgres_env: LivePostgresEnv):
    registry_schema.provision_registry_schema(live_postgres_env.admin_dsn)
    registry_schema.migrate_registry_schema(live_postgres_env.migrator_dsn)
    yield live_postgres_env
    with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS registry CASCADE")


def test_live_registry_import_roundtrip_and_idempotent(live_registry: LivePostgresEnv, tmp_path: Path) -> None:
    source = tmp_path / "registry.db"
    documents = tmp_path / "documents.db"
    _init_sqlite(source)
    before = fingerprint_sqlite_bundle(source)
    SQLiteRegistryRepository(source).upsert(_entry())
    _seed_documents_headers(documents, ["DOC-LIVE"])
    before = fingerprint_sqlite_bundle(source)
    first = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_registry.runtime_dsn,
        report_dir=tmp_path / "r1",
        documents_sqlite_path=documents,
    )
    assert first.inserted == 1
    assert fingerprint_sqlite_bundle(source) == before
    loaded = PostgresRegistryRepository(live_registry.runtime_dsn).get("DOC-LIVE")
    assert loaded is not None
    assert loaded.last_update_event_id == "evt-live"
    second = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_registry.runtime_dsn,
        report_dir=tmp_path / "r2",
        documents_sqlite_path=documents,
    )
    assert second.skipped_equal == 1
    assert second.inserted == 0
    manifest = json.loads(Path(second.report_path).read_text(encoding="utf-8"))
    assert manifest["reconciliation"]["source_keyset"] == ["DOC-LIVE"]
    assert manifest["reconciliation"]["target_keyset"] == ["DOC-LIVE"]


def test_live_registry_reconciliation_rejects_extra(live_registry: LivePostgresEnv, tmp_path: Path) -> None:
    source = tmp_path / "registry.db"
    documents = tmp_path / "documents.db"
    _init_sqlite(source)
    SQLiteRegistryRepository(source).upsert(_entry("DOC-A"))
    _seed_documents_headers(documents, ["DOC-A"])
    target = PostgresRegistryRepository(live_registry.runtime_dsn)
    import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_registry.runtime_dsn,
        report_dir=tmp_path / "r1",
        documents_sqlite_path=documents,
    )
    target.upsert(_entry("DOC-EXTRA"))
    with pytest.raises(SqlitePgImportError, match="reconciliation"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            postgres_dsn=live_registry.runtime_dsn,
            report_dir=tmp_path / "r2",
            documents_sqlite_path=documents,
        )


def test_live_registry_changed_snapshot_after_failed(live_registry: LivePostgresEnv, tmp_path: Path) -> None:
    source = tmp_path / "registry.db"
    documents = tmp_path / "documents.db"
    _init_sqlite(source)
    SQLiteRegistryRepository(source).upsert(_entry())
    _seed_documents_headers(documents, ["DOC-LIVE"])
    report = tmp_path / "resume"
    result = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_registry.runtime_dsn,
        report_dir=report,
        documents_sqlite_path=documents,
    )
    payload = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    payload["status"] = "failed"
    Path(result.report_path).write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with sqlite3.connect(source) as conn:
        conn.execute("UPDATE document_registry SET release_note='x' WHERE document_id='DOC-LIVE'")
        conn.commit()
    with pytest.raises(SqlitePgImportError, match="fingerprints do not match"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            postgres_dsn=live_registry.runtime_dsn,
            report_dir=report,
            documents_sqlite_path=documents,
        )

def test_live_registry_mixed_snapshot_fail_closed(
    live_registry: LivePostgresEnv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    import modules.registry.sqlite_pg_import as registry_import

    source = tmp_path / "registry.db"
    docs = tmp_path / "documents.db"
    _init_sqlite(source)
    SQLiteRegistryRepository(source).upsert(_entry("DOC-LIVE"))
    with sqlite3.connect(docs) as headers:
        headers.execute("CREATE TABLE document_headers (document_id TEXT PRIMARY KEY)")
        headers.execute("INSERT INTO document_headers(document_id) VALUES ('DOC-LIVE')")
        headers.commit()
    conn = sqlite3.connect(source)
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        assert str(mode[0]).lower() == "wal"
        conn.commit()
    finally:
        conn.close()

    class _Log:
        connections = 0
        begins = 0
        snapshot_released = False

    class _TrackingConnection:
        def __init__(self, real: sqlite3.Connection, barrier: threading.Barrier) -> None:
            object.__setattr__(self, "_real", real)
            object.__setattr__(self, "_barrier", barrier)

        def execute(self, sql, *args, **kwargs):
            text = str(sql).strip().upper()
            if text.startswith("BEGIN"):
                _Log.begins += 1
            result = self._real.execute(sql, *args, **kwargs)
            if text.startswith("SELECT") and not _Log.snapshot_released:
                _Log.snapshot_released = True
                self._barrier.wait()
                self._barrier.wait()
            return result

        def __getattr__(self, name):
            return getattr(self._real, name)

        def __setattr__(self, name, value):
            if name in {"_real", "_barrier"}:
                object.__setattr__(self, name, value)
                return
            setattr(self._real, name, value)

    barrier = threading.Barrier(2, timeout=30)
    orig = registry_import.sqlite3.connect
    source_uri = source.resolve().as_uri()
    captured_ids: list[str] = []
    orig_preflight = registry_import._preflight_document_refs

    def _capture_preflight(entries, documents_path):
        captured_ids.extend(sorted(entry.document_id for entry in entries))
        return orig_preflight(entries, documents_path)

    monkeypatch.setattr(registry_import, "_preflight_document_refs", _capture_preflight)

    def connect(*args, **kwargs):
        conn = orig(*args, **kwargs)
        database = str(args[0] if args else kwargs.get("database", "")).replace("\\", "/")
        if source_uri in database and "mode=ro" in database.lower():
            _Log.connections += 1
            return _TrackingConnection(conn, barrier)
        return conn

    monkeypatch.setattr(registry_import.sqlite3, "connect", connect)

    def _mutate() -> None:
        barrier.wait()
        SQLiteRegistryRepository(source).upsert(_entry("DOC-NEW"))
        barrier.wait()

    worker = threading.Thread(target=_mutate, name="live-registry-wal-writer", daemon=True)
    worker.start()
    try:
        with pytest.raises(SqlitePgImportError, match="sqlite_source_mutated"):
            import_sqlite_to_postgres(
                sqlite_path=source,
                postgres_dsn=live_registry.runtime_dsn,
                report_dir=tmp_path / "mix",
                documents_sqlite_path=docs,
            )
    finally:
        worker.join(timeout=30)
    assert not worker.is_alive()
    assert captured_ids == ["DOC-LIVE"]
    assert _Log.connections == 1
    assert _Log.begins == 1
    loaded = PostgresRegistryRepository(live_registry.runtime_dsn).get("DOC-NEW")
    assert loaded is None
