"""Live PostgreSQL import tests for AP-029 PG01-E documents (collect-only unless Slot 2)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

from modules.documents import postgres_schema as documents_schema
from modules.documents.contracts import (
    ArtifactSourceType,
    ArtifactType,
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
    control_class_for,
)
from modules.documents.postgres_repository import PostgresDocumentsRepository
from modules.documents.sqlite_pg_import import SqlitePgImportError, fingerprint_sqlite_bundle, import_sqlite_to_postgres
from modules.documents.sqlite_repository import SQLiteDocumentsRepository
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres
_MIG1 = Path(__file__).resolve().parents[3] / "modules" / "documents" / "migrations" / "0001_initial.sql"
_MIG2 = Path(__file__).resolve().parents[3] / "modules" / "documents" / "migrations" / "0002_workflow_profiles.sql"


@pytest.fixture
def live_documents(live_postgres_env: LivePostgresEnv):
    documents_schema.provision_documents_schema(live_postgres_env.admin_dsn)
    documents_schema.migrate_documents_schema(live_postgres_env.migrator_dsn)
    yield live_postgres_env
    with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS documents CASCADE")


def _seed_core(source: Path, *, with_artifact: bool = False, art_root: Path | None = None) -> None:
    with sqlite3.connect(source) as conn:
        conn.executescript(_MIG1.read_text(encoding="utf-8"))
        conn.executescript(_MIG2.read_text(encoding="utf-8"))
    moment = datetime(2024, 6, 1, tzinfo=timezone.utc)
    repo = SQLiteDocumentsRepository(source)
    repo.upsert_header(
        DocumentHeader(
            document_id="DOC-L",
            doc_type=DocumentType.VA,
            control_class=ControlClass.CONTROLLED,
            workflow_profile_id="long_release",
            created_at=moment,
            updated_at=moment,
        )
    )
    repo.upsert(
        DocumentVersionState(
            document_id="DOC-L",
            version=1,
            title="Live",
            description=None,
            doc_type=DocumentType.VA,
            control_class=ControlClass.CONTROLLED,
            workflow_profile_id="long_release",
            owner_user_id="u1",
            status=DocumentStatus.IN_PROGRESS,
            workflow_active=True,
            created_at=moment,
            created_by="u1",
            last_event_id="evt-preserve",
            last_event_at=moment,
            last_actor_user_id="u1",
        )
    )
    if with_artifact and art_root is not None:
        key = "DOC-L/1/body.pdf"
        path = art_root / key
        path.parent.mkdir(parents=True)
        payload = b"%PDF-1.4 live"
        path.write_bytes(payload)
        repo.add_artifact(
            DocumentArtifact(
                artifact_id="art-l",
                document_id="DOC-L",
                version=1,
                artifact_type=ArtifactType.SOURCE_PDF,
                source_type=ArtifactSourceType.IMPORT_PDF,
                storage_key=key,
                original_filename="body.pdf",
                mime_type="application/pdf",
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                is_current=True,
                metadata={},
                created_at=moment,
            )
        )
    with sqlite3.connect(source) as conn:
        conn.execute(
            """
            INSERT INTO document_pdf_read_sessions
            (session_id, user_id, document_id, version, artifact_id, total_pages,
             min_seconds_per_page, source, opened_at, completed_at, completion_result)
            VALUES ('sess-l', 'u1', 'DOC-L', 1, NULL, 1, 2, 'web',
                    '2024-06-01T10:00:00+00:00', '2024-06-01T10:10:00+00:00', 'complete')
            """
        )
        conn.execute(
            """
            INSERT INTO document_pdf_read_page_progress
            (session_id, page_number, accumulated_seconds, reached_threshold, first_seen_at, last_seen_at)
            VALUES ('sess-l', 1, 4, 1, '2024-06-01T10:01:00+00:00', '2024-06-01T10:02:00+00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO workflow_profile_definitions
            (profile_code, label, control_class, is_active, active_version, created_at, created_by, updated_at, updated_by)
            VALUES ('live_prof', 'Live', 'CONTROLLED', 1, 1,
                    '2024-06-01T00:00:00+00:00', 'u1', '2024-06-01T00:00:00+00:00', 'u1')
            """
        )
        conn.execute(
            """
            INSERT INTO workflow_profile_versions
            (profile_version_id, profile_code, version_no, source_kind, change_reason, definition_hash,
             effective_from, release_evidence_mode, four_eyes_required, requires_editors,
             requires_reviewers, requires_approvers, allows_content_changes, created_at, created_by)
            VALUES ('pv1', 'live_prof', 1, 'SEED', 'init', 'hash',
                    '2024-06-01T00:00:00+00:00', 'WORKFLOW', 1, 1, 1, 1, 0,
                    '2024-06-01T00:00:00+00:00', 'u1')
            """
        )
        conn.execute(
            """
            INSERT INTO workflow_profile_transitions
            (profile_transition_id, profile_version_id, transition_no, from_status, to_status,
             required_role, decision_policy, signature_required, four_eyes_required,
             revoke_if_changed, deadline_seconds, is_enabled)
            VALUES ('pt1', 'pv1', 1, 'DRAFT', 'IN_REVIEW', 'EDITOR', 'ONE_OF_POOL',
                    1, 0, 0, 3600, 1)
            """
        )
        ts = "2024-06-01T00:00:00+00:00"
        for doc_type in DocumentType:
            conn.execute(
                """
                INSERT INTO document_type_definitions
                (document_type, control_class, default_profile_code, allows_profile_override,
                 binding_source, created_at, updated_at)
                VALUES (?, ?, 'live_prof', ?, 'TEST_SEED', ?, ?)
                """,
                (
                    doc_type.value,
                    control_class_for(doc_type).value,
                    1 if doc_type == DocumentType.OTHER else 0,
                    ts,
                    ts,
                ),
            )
        conn.commit()


def test_live_documents_full_import_pdf_read_and_booleans(
    live_documents: LivePostgresEnv, tmp_path: Path
) -> None:
    source = tmp_path / "docs.db"
    art_root = tmp_path / "blob"
    _seed_core(source, with_artifact=True, art_root=art_root)
    before = fingerprint_sqlite_bundle(source)
    result = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_documents.runtime_dsn,
        report_dir=tmp_path / "r",
        artifacts_root=art_root,
    )
    assert result.inserted >= 2
    assert fingerprint_sqlite_bundle(source) == before
    loaded = PostgresDocumentsRepository(live_documents.runtime_dsn).get("DOC-L", 1)
    assert loaded is not None
    assert loaded.last_event_id == "evt-preserve"
    manifest = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    assert manifest["tables"]["document_pdf_read_sessions"]["count"] == 1
    assert manifest["tables"]["document_pdf_read_page_progress"]["count"] == 1
    with psycopg.connect(live_documents.runtime_dsn) as conn:
        row = conn.execute(
            "SELECT is_active FROM documents.workflow_profile_definitions WHERE profile_code='live_prof'"
        ).fetchone()
        tr = conn.execute(
            "SELECT signature_required, deadline_seconds FROM documents.workflow_profile_transitions "
            "WHERE profile_transition_id='pt1'"
        ).fetchone()
    assert row[0] is True
    assert tr[0] is True
    assert tr[1] == 3600


def test_live_documents_identical_second_import(live_documents: LivePostgresEnv, tmp_path: Path) -> None:
    source = tmp_path / "docs.db"
    _seed_core(source)
    first = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_documents.runtime_dsn,
        report_dir=tmp_path / "r1",
    )
    second = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_documents.runtime_dsn,
        report_dir=tmp_path / "r2",
    )
    assert first.inserted >= 2
    assert second.skipped_equal >= first.inserted
    assert second.inserted == 0 or second.skipped_equal > 0


def test_live_documents_abort_resume_same_snapshot(live_documents: LivePostgresEnv, tmp_path: Path) -> None:
    source = tmp_path / "docs.db"
    _seed_core(source)
    report = tmp_path / "resume"
    result = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_documents.runtime_dsn,
        report_dir=report,
    )
    payload = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    payload["status"] = "failed"
    payload["error"] = "simulated-abort"
    Path(result.report_path).write_text(json.dumps(payload) + "\n", encoding="utf-8")
    resumed = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_documents.runtime_dsn,
        report_dir=report,
    )
    assert resumed.status == "completed"


def test_live_documents_changed_snapshot_after_failed_rejected(
    live_documents: LivePostgresEnv, tmp_path: Path
) -> None:
    source = tmp_path / "docs.db"
    _seed_core(source)
    report = tmp_path / "resume-bad"
    result = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_documents.runtime_dsn,
        report_dir=report,
    )
    payload = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    payload["status"] = "failed"
    Path(result.report_path).write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with sqlite3.connect(source) as conn:
        conn.execute("UPDATE document_headers SET workflow_profile_id='other' WHERE document_id='DOC-L'")
        conn.commit()
    with pytest.raises(SqlitePgImportError, match="fingerprints do not match"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            postgres_dsn=live_documents.runtime_dsn,
            report_dir=report,
        )


def test_live_documents_storage_negative_paths(live_documents: LivePostgresEnv, tmp_path: Path) -> None:
    source = tmp_path / "docs.db"
    art_root = tmp_path / "blob"
    art_root.mkdir()
    _seed_core(source, with_artifact=True, art_root=art_root)
    with pytest.raises(SqlitePgImportError):
        import_sqlite_to_postgres(
            sqlite_path=source,
            postgres_dsn=live_documents.runtime_dsn,
            report_dir=tmp_path / "neg",
            artifacts_root=tmp_path / "missing",
        )


def _subprocess_read_document_snapshot(dsn: str) -> dict[str, object]:
    """Start a fresh Python process, read via PG repository, then exit completely."""
    import subprocess
    import sys

    script = r"""
import json, sys
from modules.documents.postgres_repository import PostgresDocumentsRepository
dsn = sys.argv[1]
doc_id = sys.argv[2]
version = int(sys.argv[3])
state = PostgresDocumentsRepository(dsn).get(doc_id, version)
if state is None:
    print(json.dumps({"missing": True}))
    raise SystemExit(2)
print(json.dumps({
    "document_id": state.document_id,
    "version": state.version,
    "status": state.status.value if hasattr(state.status, "value") else str(state.status),
    "last_event_id": state.last_event_id,
    "title": state.title,
}))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script, dsn, "DOC-L", "1"],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[3]),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip())


def test_live_documents_restart_preserves_ids_etags(
    live_documents: LivePostgresEnv, tmp_path: Path
) -> None:
    source = tmp_path / "docs.db"
    _seed_core(source)
    import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_documents.runtime_dsn,
        report_dir=tmp_path / "r1",
    )
    first = _subprocess_read_document_snapshot(live_documents.runtime_dsn)
    # Process fully terminated before the second start (new subprocess.run).
    second = _subprocess_read_document_snapshot(live_documents.runtime_dsn)
    assert first == second
    assert first["document_id"] == "DOC-L"
    assert first["last_event_id"] == "evt-preserve"
    assert first["status"] == DocumentStatus.IN_PROGRESS.value


def test_live_documents_cas_exactly_one_winner(live_documents: LivePostgresEnv, tmp_path: Path) -> None:
    """Two independent services/repos race the same CAS precondition concurrently."""
    from concurrent.futures import ThreadPoolExecutor
    import threading

    from modules.documents.errors import DocumentConflictError
    from modules.documents.service import DocumentsService
    from modules.documents.bootstrap_provenance import DocumentsBootstrapProvenance
    from modules.documents.workflow_profile_seed_reader import WorkflowProfileSeedReader
    from modules.documents.workflow_profile_store import WorkflowProfileRelationalStore
    from qm_platform.events.event_bus import EventBus

    source = tmp_path / "docs.db"
    _seed_core(source)
    import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_documents.runtime_dsn,
        report_dir=tmp_path / "r-cas",
    )
    seed = Path(__file__).resolve().parents[3] / "modules" / "documents" / "workflow_profiles.json"
    expected = PostgresDocumentsRepository(live_documents.runtime_dsn).get("DOC-L", 1)
    assert expected is not None
    expected_last_event_id = expected.last_event_id
    barrier = threading.Barrier(2)

    def _make_service() -> DocumentsService:
        repo = PostgresDocumentsRepository(live_documents.runtime_dsn)
        store = WorkflowProfileRelationalStore(
            repo,
            bundled_seed_path=seed,
            legacy_profiles_path=tmp_path / f"legacy_profiles_{threading.get_ident()}.json",
            bootstrap_provenance=DocumentsBootstrapProvenance.FRESH_INSTALL,
        )
        store.ensure_seeded(WorkflowProfileSeedReader())
        return DocumentsService(
            event_bus=EventBus(),
            repository=repo,
            profile_store=store,
            signature_api=None,
        )

    def _race() -> object:
        service = _make_service()
        try:
            barrier.wait(timeout=30)
            return service.mutate_version_if_current(
                "DOC-L",
                1,
                expected_last_event_id,
                lambda current: service.assign_workflow_roles(
                    current,
                    editors={"editor-cas"},
                    reviewers={"reviewer-cas"},
                    approvers={"approver-cas"},
                ),
            )
        except DocumentConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_race), pool.submit(_race)]
        outcomes = [futures[0].result(), futures[1].result()]

    winners = [item for item in outcomes if not isinstance(item, DocumentConflictError)]
    conflicts = [item for item in outcomes if isinstance(item, DocumentConflictError)]
    assert len(winners) == 1
    assert len(conflicts) == 1
    final = PostgresDocumentsRepository(live_documents.runtime_dsn).get("DOC-L", 1)
    assert final is not None
    assert final.last_event_id == winners[0].last_event_id
    assert final.last_event_id != expected_last_event_id
    assert conflicts[0].current_state.last_event_id == final.last_event_id

def test_live_documents_mixed_snapshot_fail_closed(
    live_documents: LivePostgresEnv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    import modules.documents.sqlite_pg_import as documents_import

    source = tmp_path / "docs.db"
    art_root = tmp_path / "blob"
    _seed_core(source, with_artifact=True, art_root=art_root)
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
    orig = documents_import.sqlite3.connect
    source_uri = source.resolve().as_uri()

    def connect(*args, **kwargs):
        conn = orig(*args, **kwargs)
        database = str(args[0] if args else kwargs.get("database", "")).replace("\\", "/")
        if source_uri in database and "mode=ro" in database.lower():
            _Log.connections += 1
            return _TrackingConnection(conn, barrier)
        return conn

    monkeypatch.setattr(documents_import.sqlite3, "connect", connect)

    def _mutate() -> None:
        barrier.wait()
        writer = sqlite3.connect(source)
        try:
            writer.execute(
                """
                INSERT INTO document_pdf_read_sessions
                (session_id, user_id, document_id, version, artifact_id, total_pages,
                 min_seconds_per_page, source, opened_at, completed_at, completion_result)
                VALUES ('sess-new', 'u1', 'DOC-L', 1, NULL, 1, 2, 'web',
                        '2024-06-01T12:00:00+00:00', '2024-06-01T12:10:00+00:00', 'complete')
                """
            )
            writer.commit()
        finally:
            writer.close()
        barrier.wait()

    worker = threading.Thread(target=_mutate, name="live-docs-wal-writer", daemon=True)
    worker.start()
    try:
        with pytest.raises(SqlitePgImportError, match="sqlite_source_mutated"):
            import_sqlite_to_postgres(
                sqlite_path=source,
                postgres_dsn=live_documents.runtime_dsn,
                report_dir=tmp_path / "mix",
                artifacts_root=art_root,
            )
    finally:
        worker.join(timeout=30)
    assert not worker.is_alive()
    assert _Log.connections == 1
    assert _Log.begins == 1
    with psycopg.connect(live_documents.runtime_dsn) as pg:
        row = pg.execute(
            "SELECT 1 FROM documents.document_pdf_read_sessions WHERE session_id = %s",
            ("sess-new",),
        ).fetchone()
    assert row is None
