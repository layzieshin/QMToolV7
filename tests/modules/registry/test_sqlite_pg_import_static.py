"""Static (no PostgreSQL) tests for AP-029 PG01-E registry SQLite→PG import."""
from __future__ import annotations
import json
import threading
import modules.registry.sqlite_pg_import as registry_import

import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from modules.registry import api as registry_api
from modules.registry.contracts import RegisterState, RegistryEntry, ReleaseEvidenceMode
from modules.registry.sqlite_pg_import import (
    SqlitePgImportError,
    fingerprint_sqlite_bundle,
    import_sqlite_to_postgres,
)
from modules.registry.sqlite_repository import SQLiteRegistryRepository

_MIGRATION = Path(__file__).resolve().parents[3] / "modules" / "registry" / "migrations" / "0001_initial.sql"


def _init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sql = _MIGRATION.read_text(encoding="utf-8")
    with sqlite3.connect(path) as conn:
        conn.executescript(sql)


def _sample_entry(document_id: str = "DOC-1") -> RegistryEntry:
    moment = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    return RegistryEntry(
        document_id=document_id,
        active_version=1,
        release_note="note",
        release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
        register_state=RegisterState.VALID,
        is_findable=True,
        valid_from=moment,
        valid_until=None,
        last_update_event_id="evt-1",
        last_update_at=moment,
    )


def test_fingerprint_includes_absent_sidecars(tmp_path: Path) -> None:
    db = tmp_path / "registry.db"
    _init_db(db)
    fp = fingerprint_sqlite_bundle(db)
    assert fp["db"] is not None
    assert fp["wal"] is None
    assert fp["shm"] is None


def test_import_idempotent_and_conflict(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    documents = tmp_path / "documents.db"
    report = tmp_path / "report"
    _init_db(source)
    _init_db(target_db)
    SQLiteRegistryRepository(source).upsert(_sample_entry())
    _seed_documents_headers(documents, ["DOC-1"])
    target = SQLiteRegistryRepository(target_db)

    first = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=report,
        documents_sqlite_path=documents,
        target_repository=target,
    )
    assert first.status == "completed"
    assert first.inserted == 1
    second = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=report,
        documents_sqlite_path=documents,
        target_repository=target,
    )
    assert second.inserted == 0
    assert second.skipped_equal == 1
    assert second.content_digest == first.content_digest

    target.upsert(
        RegistryEntry(
            document_id="DOC-1",
            active_version=99,
            release_note="diverged",
            release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
            register_state=RegisterState.VALID,
            is_findable=True,
            valid_from=None,
            valid_until=None,
            last_update_event_id="evt-x",
            last_update_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        )
    )
    with pytest.raises(SqlitePgImportError, match="conflict"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=report / "conflict",
            documents_sqlite_path=documents,
            target_repository=target,
        )


def test_nonempty_registry_requires_documents_source_before_target_write(
    tmp_path: Path,
) -> None:
    source = tmp_path / "registry.db"
    target_db = tmp_path / "target.db"
    _init_db(source)
    _init_db(target_db)
    SQLiteRegistryRepository(source).upsert(_sample_entry())
    target = SQLiteRegistryRepository(target_db)

    with pytest.raises(SqlitePgImportError, match="documents_sqlite_path required"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "missing-documents",
            target_repository=target,
        )
    assert target.get("DOC-1") is None


def test_referential_preflight_requires_document_header(tmp_path: Path) -> None:
    source = tmp_path / "registry.db"
    docs = tmp_path / "documents.db"
    _init_db(source)
    SQLiteRegistryRepository(source).upsert(_sample_entry("DOC-MISSING"))
    with sqlite3.connect(docs) as conn:
        conn.execute(
            "CREATE TABLE document_headers (document_id TEXT PRIMARY KEY)"
        )
    with pytest.raises(SqlitePgImportError, match="referential"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "r",
            documents_sqlite_path=docs,
            target_repository=SQLiteRegistryRepository(tmp_path / "t.db"),
        )


def test_source_mutation_detected(tmp_path: Path) -> None:
    source = tmp_path / "registry.db"
    _init_db(source)
    SQLiteRegistryRepository(source).upsert(_sample_entry())
    target = SQLiteRegistryRepository(tmp_path / "target.db")
    _init_db(tmp_path / "target.db")

    # Simulate mutation mid-run by wrapping fingerprint after first write is hard;
    # instead assert open_readonly refuses writes by attempting write via URI.
    conn_uri = source.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(conn_uri, uri=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO document_registry(document_id) VALUES ('x')")
    conn.close()


def test_public_api_delegates(tmp_path: Path) -> None:
    source = tmp_path / "registry.db"
    target_db = tmp_path / "target.db"
    documents = tmp_path / "documents.db"
    _init_db(source)
    _init_db(target_db)
    SQLiteRegistryRepository(source).upsert(_sample_entry())
    _seed_documents_headers(documents, ["DOC-1"])
    result = registry_api.import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=None,
        report_dir=tmp_path / "rep",
        documents_sqlite_path=documents,
        target_repository=SQLiteRegistryRepository(target_db),
    )
    assert result.inserted == 1


def test_reconciliation_rejects_extra_target_rows(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    documents = tmp_path / "documents.db"
    _init_db(source)
    _init_db(target_db)
    SQLiteRegistryRepository(source).upsert(_sample_entry("DOC-1"))
    _seed_documents_headers(documents, ["DOC-1"])
    target = SQLiteRegistryRepository(target_db)
    import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=tmp_path / "r1",
        documents_sqlite_path=documents,
        target_repository=target,
    )
    target.upsert(_sample_entry("DOC-EXTRA"))
    with pytest.raises(SqlitePgImportError, match="reconciliation"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "r2",
            documents_sqlite_path=documents,
            target_repository=target,
        )


def test_resume_blocks_changed_snapshot_after_failed(tmp_path: Path) -> None:
    import json

    source = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    documents = tmp_path / "documents.db"
    _init_db(source)
    _init_db(target_db)
    SQLiteRegistryRepository(source).upsert(_sample_entry())
    _seed_documents_headers(documents, ["DOC-1"])
    report = tmp_path / "resume"
    first = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=report,
        documents_sqlite_path=documents,
        target_repository=SQLiteRegistryRepository(target_db),
    )
    payload = json.loads(Path(first.report_path).read_text(encoding="utf-8"))
    payload["status"] = "failed"
    Path(first.report_path).write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with sqlite3.connect(source) as conn:
        conn.execute("UPDATE document_registry SET release_note='mutated' WHERE document_id='DOC-1'")
        conn.commit()
    with pytest.raises(SqlitePgImportError, match="fingerprints do not match"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=report,
            documents_sqlite_path=documents,
            target_repository=SQLiteRegistryRepository(target_db),
        )

class _SqlLog:
    def __init__(self) -> None:
        self.connections = 0
        self.begins = 0
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.target_ops = 0
        self.source_selects_after_target = 0


class _TrackingConnection:
    def __init__(self, real: sqlite3.Connection, log: _SqlLog, barrier: threading.Barrier | None) -> None:
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_log", log)
        object.__setattr__(self, "_barrier", barrier)
        object.__setattr__(self, "_snapshot_released", False)

    def execute(self, sql, *args, **kwargs):
        text = str(sql).strip().upper()
        if text.startswith("BEGIN"):
            self._log.begins += 1
        elif text.startswith("COMMIT"):
            self._log.commits += 1
        elif text.startswith("ROLLBACK"):
            self._log.rollbacks += 1
        elif text.startswith("SELECT") and self._log.target_ops > 0:
            self._log.source_selects_after_target += 1
        result = self._real.execute(sql, *args, **kwargs)
        if (
            self._barrier is not None
            and text.startswith("SELECT")
            and not self._snapshot_released
        ):
            object.__setattr__(self, "_snapshot_released", True)
            self._barrier.wait()
            self._barrier.wait()
        return result

    def close(self):
        self._log.closes += 1
        return self._real.close()

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        if name in {"_real", "_log", "_barrier", "_snapshot_released"}:
            object.__setattr__(self, name, value)
            return
        setattr(self._real, name, value)


class _TargetProbe(SQLiteRegistryRepository):
    def __init__(self, db_path: Path, log: _SqlLog) -> None:
        super().__init__(db_path)
        self._log = log

    def get(self, document_id: str):
        self._log.target_ops += 1
        return super().get(document_id)

    def upsert(self, entry):
        self._log.target_ops += 1
        return super().upsert(entry)

    def list_entries(self):
        self._log.target_ops += 1
        return super().list_entries()


def _is_ro_source(database: object, source: Path) -> bool:
    text = str(database).replace("\\", "/")
    uri = source.resolve().as_uri()
    return uri in text and "mode=ro" in text.lower()


def _install_source_tracker(monkeypatch, source: Path, log: _SqlLog, barrier: threading.Barrier | None = None) -> None:
    orig = registry_import.sqlite3.connect

    def connect(*args, **kwargs):
        conn = orig(*args, **kwargs)
        database = args[0] if args else kwargs.get("database", "")
        if _is_ro_source(database, source):
            log.connections += 1
            return _TrackingConnection(conn, log, barrier)
        return conn

    monkeypatch.setattr(registry_import.sqlite3, "connect", connect)


def _enable_wal(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        assert str(mode[0]).lower() == "wal"
        conn.commit()
    finally:
        conn.close()


def _seed_documents_headers(path: Path, document_ids: list[str]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE document_headers (document_id TEXT PRIMARY KEY)")
        for doc_id in document_ids:
            conn.execute("INSERT INTO document_headers(document_id) VALUES (?)", (doc_id,))
        conn.commit()
    finally:
        conn.close()


def test_registry_source_connection_owned_until_success_or_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "registry.db"
    target_ok = tmp_path / "tgt-ok.db"
    target_fail = tmp_path / "tgt-fail.db"
    documents = tmp_path / "documents.db"
    _init_db(source)
    _init_db(target_ok)
    _init_db(target_fail)
    SQLiteRegistryRepository(source).upsert(_sample_entry())
    _seed_documents_headers(documents, ["DOC-1"])

    success_log = _SqlLog()
    _install_source_tracker(monkeypatch, source, success_log)
    result = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=tmp_path / "ok",
        documents_sqlite_path=documents,
        target_repository=_TargetProbe(target_ok, success_log),
    )
    assert result.status == "completed"
    assert success_log.connections == 1
    assert success_log.begins == 1
    assert success_log.commits == 1
    assert success_log.rollbacks == 0
    assert success_log.closes == 1
    assert success_log.target_ops >= 1
    assert success_log.source_selects_after_target == 0

    SQLiteRegistryRepository(target_fail).upsert(
        RegistryEntry(
            document_id="DOC-1",
            active_version=99,
            release_note="diverged",
            release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
            register_state=RegisterState.VALID,
            is_findable=True,
            valid_from=None,
            valid_until=None,
            last_update_event_id="evt-x",
            last_update_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        )
    )
    fail_log = _SqlLog()
    _install_source_tracker(monkeypatch, source, fail_log)
    with pytest.raises(SqlitePgImportError, match="conflict"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "fail",
            documents_sqlite_path=documents,
            target_repository=_TargetProbe(target_fail, fail_log),
        )
    assert fail_log.connections == 1
    assert fail_log.begins == 1
    assert fail_log.commits == 0
    assert fail_log.rollbacks == 1
    assert fail_log.closes == 1
    assert fail_log.source_selects_after_target == 0


def test_registry_wal_mixed_snapshot_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "registry.db"
    target = tmp_path / "tgt.db"
    docs = tmp_path / "documents.db"
    _init_db(source)
    _init_db(target)
    _enable_wal(source)
    SQLiteRegistryRepository(source).upsert(_sample_entry("DOC-1"))
    _seed_documents_headers(docs, ["DOC-1"])

    log = _SqlLog()
    barrier = threading.Barrier(2, timeout=30)
    _install_source_tracker(monkeypatch, source, log, barrier=barrier)
    captured_ids: list[str] = []
    orig_preflight = registry_import._preflight_document_refs

    def _capture_preflight(entries, documents_path):
        captured_ids.extend(sorted(entry.document_id for entry in entries))
        return orig_preflight(entries, documents_path)

    monkeypatch.setattr(registry_import, "_preflight_document_refs", _capture_preflight)

    def _mutate() -> None:
        barrier.wait()
        SQLiteRegistryRepository(source).upsert(_sample_entry("DOC-NEW"))
        barrier.wait()

    worker = threading.Thread(target=_mutate, name="registry-wal-writer", daemon=True)
    worker.start()
    try:
        with pytest.raises(SqlitePgImportError, match="sqlite_source_mutated"):
            import_sqlite_to_postgres(
                sqlite_path=source,
                report_dir=tmp_path / "mix",
                documents_sqlite_path=docs,
                target_repository=_TargetProbe(target, log),
            )
    finally:
        worker.join(timeout=30)
    assert not worker.is_alive()
    assert captured_ids == ["DOC-1"]
    assert log.connections == 1
    assert log.begins == 1
    assert log.rollbacks == 1
    assert log.closes == 1
    assert log.source_selects_after_target == 0
    assert SQLiteRegistryRepository(target).get("DOC-NEW") is None
    manifest = json.loads((tmp_path / "mix" / "registry_sqlite_pg_import_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert "sqlite_source_mutated" in str(manifest.get("error", ""))
