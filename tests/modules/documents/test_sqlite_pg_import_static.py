"""Static tests for AP-029 PG01-E documents SQLite→PG import."""
from __future__ import annotations
import threading
import modules.documents.sqlite_pg_import as documents_import

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from modules.documents import api as documents_api
from modules.documents.contracts import (
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
    ArtifactSourceType,
    ArtifactType,
)
from modules.documents.sqlite_pg_import import (
    SqlitePgImportError,
    _BOOL_PROFILE_COLUMNS,
    _canonical,
    _coerce_profile_value,
    fingerprint_sqlite_bundle,
    import_sqlite_to_postgres,
)
from modules.documents.sqlite_repository import SQLiteDocumentsRepository

_MIG1 = Path(__file__).resolve().parents[3] / "modules" / "documents" / "migrations" / "0001_initial.sql"
_MIG2 = Path(__file__).resolve().parents[3] / "modules" / "documents" / "migrations" / "0002_workflow_profiles.sql"


def _init_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(_MIG1.read_text(encoding="utf-8"))
        conn.executescript(_MIG2.read_text(encoding="utf-8"))


def _header() -> DocumentHeader:
    moment = datetime(2024, 6, 1, tzinfo=timezone.utc)
    return DocumentHeader(
        document_id="DOC-1",
        doc_type=DocumentType.VA,
        control_class=ControlClass.CONTROLLED,
        workflow_profile_id="long_release",
        created_at=moment,
        updated_at=moment,
    )


def _version() -> DocumentVersionState:
    moment = datetime(2024, 6, 1, tzinfo=timezone.utc)
    return DocumentVersionState(
        document_id="DOC-1",
        version=1,
        title="T",
        description=None,
        doc_type=DocumentType.VA,
        control_class=ControlClass.CONTROLLED,
        workflow_profile_id="long_release",
        owner_user_id="u1",
        status=DocumentStatus.IN_PROGRESS,
        workflow_active=True,
        created_at=moment,
        created_by="u1",
        last_event_id="evt-1",
        last_event_at=moment,
        last_actor_user_id="u1",
    )


def test_canonical_equal_instant_across_utc_offsets() -> None:
    utc = datetime(2024, 6, 1, tzinfo=timezone.utc)
    plus2 = utc.astimezone(timezone(timedelta(hours=2)))
    base = dict(
        document_id="DOC-L",
        doc_type=DocumentType.VA,
        control_class=ControlClass.CONTROLLED,
        workflow_profile_id="long_release",
    )
    h_utc = DocumentHeader(**base, created_at=utc, updated_at=utc)
    h_plus2 = DocumentHeader(**base, created_at=plus2, updated_at=plus2)
    assert _canonical(h_utc) == _canonical(h_plus2)


def test_canonical_diverges_for_different_instants() -> None:
    utc = datetime(2024, 6, 1, tzinfo=timezone.utc)
    later = datetime(2024, 6, 2, tzinfo=timezone.utc)
    base = dict(
        document_id="DOC-L",
        doc_type=DocumentType.VA,
        control_class=ControlClass.CONTROLLED,
        workflow_profile_id="long_release",
    )
    assert _canonical(
        DocumentHeader(**base, created_at=utc, updated_at=utc)
    ) != _canonical(
        DocumentHeader(**base, created_at=later, updated_at=later)
    )


def test_canonical_d1_created_at_offset_case() -> None:
    """Reproduce D1: same instant as UTC +00:00 vs Europe/Berlin +02:00 representation."""
    utc = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    berlin = datetime(2024, 6, 1, 2, 0, tzinfo=timezone(timedelta(hours=2)))
    base = dict(
        document_id="DOC-L",
        doc_type=DocumentType.VA,
        control_class=ControlClass.CONTROLLED,
        workflow_profile_id="long_release",
    )
    source = DocumentHeader(**base, created_at=utc, updated_at=utc)
    pg_like = DocumentHeader(**base, created_at=berlin, updated_at=berlin)
    assert _canonical(source) == _canonical(pg_like)


def test_canonical_version_and_receipt_datetime_fields() -> None:
    utc = datetime(2024, 6, 1, tzinfo=timezone.utc)
    plus2 = utc.astimezone(timezone(timedelta(hours=2)))
    v1 = _version()
    v2 = replace(v1, created_at=plus2, last_event_at=plus2)
    assert _canonical(v1) == _canonical(v2)


def test_workflow_profile_graph_preflight_rejects_partial_graph(tmp_path: Path) -> None:
    source = tmp_path / "partial.db"
    target = tmp_path / "tgt.db"
    _init_db(source)
    _init_db(target)
    SQLiteDocumentsRepository(source).upsert_header(_header())
    with sqlite3.connect(source) as conn:
        conn.execute(
            """
            INSERT INTO workflow_profile_definitions
            (profile_code, label, control_class, is_active, active_version, created_at, created_by, updated_at, updated_by)
            VALUES ('p1', 'L', 'CONTROLLED', 1, 1, '2024-01-01T00:00:00+00:00', 'u', '2024-01-01T00:00:00+00:00', 'u')
            """
        )
        conn.commit()
    with pytest.raises(SqlitePgImportError, match="missing document type bindings"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "partial",
            target_repository=SQLiteDocumentsRepository(target),
        )
    assert SQLiteDocumentsRepository(target).get_header("DOC-1") is None
    manifest = json.loads((tmp_path / "partial" / "documents_sqlite_pg_import_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"


def test_workflow_profile_rows_require_postgres_dsn_before_target_write(
    tmp_path: Path,
) -> None:
    source = tmp_path / "profiles.db"
    target = tmp_path / "target.db"
    _init_db(source)
    _init_db(target)
    with sqlite3.connect(source) as conn:
        conn.execute(
            """
            INSERT INTO workflow_profile_definitions
            (profile_code, label, control_class, is_active, active_version,
             created_at, created_by, updated_at, updated_by)
            VALUES ('p1', 'Profile', 'CONTROLLED', 1, 1,
                    '2024-01-01T00:00:00+00:00', 'u1',
                    '2024-01-01T00:00:00+00:00', 'u1')
            """
        )
        conn.executemany(
            """
            INSERT INTO document_type_definitions
            (document_type, control_class, default_profile_code,
             allows_profile_override, binding_source, created_at, updated_at)
            VALUES (?, 'CONTROLLED', 'p1', 0, 'IMPORT',
                    '2024-01-01T00:00:00+00:00',
                    '2024-01-01T00:00:00+00:00')
            """,
            [(doc_type.value,) for doc_type in DocumentType],
        )
        conn.commit()

    with pytest.raises(SqlitePgImportError, match="PostgreSQL target DSN"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "profiles-report",
            target_repository=SQLiteDocumentsRepository(target),
        )
    with sqlite3.connect(target) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM workflow_profile_definitions"
        ).fetchone()[0] == 0


def test_document_artifacts_require_root_before_target_write(tmp_path: Path) -> None:
    source = tmp_path / "artifacts.db"
    target = tmp_path / "target.db"
    _init_db(source)
    _init_db(target)
    src = SQLiteDocumentsRepository(source)
    src.upsert_header(_header())
    src.upsert(_version())
    src.add_artifact(
        DocumentArtifact(
            artifact_id="art-required-root",
            document_id="DOC-1",
            version=1,
            artifact_type=ArtifactType.SOURCE_PDF,
            source_type=ArtifactSourceType.IMPORT_PDF,
            storage_key="DOC-1/1/source.pdf",
            original_filename="source.pdf",
            mime_type="application/pdf",
            sha256=hashlib.sha256(b"pdf").hexdigest(),
            size_bytes=3,
            is_current=True,
            metadata={},
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
    )

    with pytest.raises(SqlitePgImportError, match="artifacts_root required"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "artifact-report",
            target_repository=SQLiteDocumentsRepository(target),
        )
    assert SQLiteDocumentsRepository(target).get_header("DOC-1") is None


def test_documents_import_idempotent_and_artifact_preflight(tmp_path: Path) -> None:
    source = tmp_path / "docs.db"
    target = tmp_path / "tgt.db"
    _init_db(source)
    _init_db(target)
    src = SQLiteDocumentsRepository(source)
    src.upsert_header(_header())
    src.upsert(_version())
    art_root = tmp_path / "blob"
    key_rel = "DOC-1/1/file.bin"
    blob = art_root / key_rel
    blob.parent.mkdir(parents=True)
    payload = b"abc"
    blob.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    src.add_artifact(
        DocumentArtifact(
            artifact_id="art-1",
            document_id="DOC-1",
            version=1,
            artifact_type=ArtifactType.SOURCE_PDF,
            source_type=ArtifactSourceType.IMPORT_PDF,
            storage_key=key_rel,
            original_filename="file.bin",
            mime_type="application/octet-stream",
            sha256=digest,
            size_bytes=len(payload),
            is_current=True,
            metadata={},
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
    )
    assert fingerprint_sqlite_bundle(source)["db"]

    with pytest.raises(SqlitePgImportError, match="unavailable"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "bad",
            artifacts_root=tmp_path / "nope",
            target_repository=SQLiteDocumentsRepository(target),
        )

    first = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=tmp_path / "r1",
        artifacts_root=art_root,
        target_repository=SQLiteDocumentsRepository(target),
    )
    assert first.inserted >= 3
    second = documents_api.import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=None,
        report_dir=tmp_path / "r2",
        artifacts_root=art_root,
        target_repository=SQLiteDocumentsRepository(target),
    )
    assert second.skipped_equal >= 3
    loaded = SQLiteDocumentsRepository(target).get("DOC-1", 1)
    assert loaded is not None
    assert loaded.last_event_id == "evt-1"


def test_documents_storage_rejects_traversal_and_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "docs.db"
    target = tmp_path / "tgt.db"
    _init_db(source)
    _init_db(target)
    src = SQLiteDocumentsRepository(source)
    src.upsert_header(_header())
    src.upsert(_version())
    art_root = tmp_path / "blob"
    art_root.mkdir()
    src.add_artifact(
        DocumentArtifact(
            artifact_id="art-1",
            document_id="DOC-1",
            version=1,
            artifact_type=ArtifactType.SOURCE_PDF,
            source_type=ArtifactSourceType.IMPORT_PDF,
            storage_key="../escape.bin",
            original_filename="file.bin",
            mime_type="application/octet-stream",
            sha256="00",
            size_bytes=1,
            is_current=True,
            metadata={},
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
    )
    with pytest.raises(SqlitePgImportError, match="escapes root|absolute"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "trav",
            artifacts_root=art_root,
            target_repository=SQLiteDocumentsRepository(target),
        )


def test_pdf_read_tables_import_equal_skip_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "docs.db"
    target = tmp_path / "tgt.db"
    _init_db(source)
    _init_db(target)
    src = SQLiteDocumentsRepository(source)
    src.upsert_header(_header())
    src.upsert(_version())
    opened = "2024-06-01T10:00:00+00:00"
    completed = "2024-06-01T11:00:00+00:00"
    first_seen = "2024-06-01T10:05:00+00:00"
    last_seen = "2024-06-01T10:06:00+00:00"
    with sqlite3.connect(source) as conn:
        conn.execute(
            """
            INSERT INTO document_pdf_read_sessions
            (session_id, user_id, document_id, version, artifact_id, total_pages,
             min_seconds_per_page, source, opened_at, completed_at, completion_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sess-1", "u1", "DOC-1", 1, None, 2, 3, "web", opened, completed, "complete"),
        )
        conn.execute(
            """
            INSERT INTO document_pdf_read_page_progress
            (session_id, page_number, accumulated_seconds, reached_threshold, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("sess-1", 1, 5, 1, first_seen, last_seen),
        )
        conn.commit()

    first = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=tmp_path / "pdf1",
        target_repository=SQLiteDocumentsRepository(target),
    )
    manifest = json.loads(Path(first.report_path).read_text(encoding="utf-8"))
    assert manifest["tables"]["document_pdf_read_sessions"]["count"] == 1
    assert manifest["tables"]["document_pdf_read_page_progress"]["count"] == 1
    assert manifest["tables"]["document_pdf_read_sessions"]["digest"]
    with sqlite3.connect(target) as conn:
        sess = conn.execute(
            "SELECT completion_result, completed_at FROM document_pdf_read_sessions WHERE session_id='sess-1'"
        ).fetchone()
        page = conn.execute(
            "SELECT accumulated_seconds, reached_threshold, first_seen_at, last_seen_at "
            "FROM document_pdf_read_page_progress WHERE session_id='sess-1'"
        ).fetchone()
    assert sess[0] == "complete"
    assert sess[1] == completed
    assert page[0] == 5
    assert int(page[1]) == 1
    assert page[2] == first_seen
    assert page[3] == last_seen

    second = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=tmp_path / "pdf2",
        target_repository=SQLiteDocumentsRepository(target),
    )
    assert second.skipped_equal >= 2


def test_workflow_boolean_allowlist_from_sqlite_integers(tmp_path: Path) -> None:
    assert "is_active" in _BOOL_PROFILE_COLUMNS
    assert "allows_profile_override" in _BOOL_PROFILE_COLUMNS
    assert _coerce_profile_value("is_active", 1) is True
    assert _coerce_profile_value("four_eyes_required", 0) is False
    assert _coerce_profile_value("signature_required", 1) is True
    assert _coerce_profile_value("allows_content_changes", 0) is False
    assert isinstance(_coerce_profile_value("version_no", 3), int)
    assert _coerce_profile_value("version_no", 3) == 3
    assert _coerce_profile_value("transition_no", 2) == 2
    assert _coerce_profile_value("active_version", 1) == 1
    assert _coerce_profile_value("deadline_seconds", 60) == 60
    # Non-allowlist column stays raw (no silent bool coercion via prefix).
    assert _coerce_profile_value("requires_comment", 1) == 1

    db = tmp_path / "wf.db"
    _init_db(db)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            INSERT INTO workflow_profile_definitions
            (profile_code, label, control_class, is_active, active_version, created_at, created_by, updated_at, updated_by)
            VALUES ('p1', 'L', 'CONTROLLED', 1, 2, '2024-01-01T00:00:00+00:00', 'u', '2024-01-01T00:00:00+00:00', 'u')
            """
        )
        conn.execute(
            """
            INSERT INTO document_type_definitions
            (document_type, control_class, default_profile_code, allows_profile_override, binding_source, created_at, updated_at)
            VALUES ('VA', 'CONTROLLED', 'p1', 0, 'SEED', '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00')
            """
        )
        conn.commit()
        defn = conn.execute("SELECT is_active, active_version FROM workflow_profile_definitions").fetchone()
        dtype = conn.execute("SELECT allows_profile_override FROM document_type_definitions").fetchone()
    assert isinstance(defn["is_active"], int)
    assert isinstance(defn["active_version"], int)
    assert _coerce_profile_value("is_active", defn["is_active"]) is True
    assert _coerce_profile_value("active_version", defn["active_version"]) == 2
    assert isinstance(dtype["allows_profile_override"], int)
    assert _coerce_profile_value("allows_profile_override", dtype["allows_profile_override"]) is False


def test_resume_rejects_changed_snapshot_after_failed(tmp_path: Path) -> None:
    source = tmp_path / "docs.db"
    target = tmp_path / "tgt.db"
    _init_db(source)
    _init_db(target)
    src = SQLiteDocumentsRepository(source)
    src.upsert_header(_header())
    src.upsert(_version())
    report_dir = tmp_path / "resume"
    first = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=report_dir,
        target_repository=SQLiteDocumentsRepository(target),
    )
    # Force FAILED status while keeping fingerprints, then mutate source.
    manifest_path = Path(first.report_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["status"] = "failed"
    payload["error"] = "simulated"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with sqlite3.connect(source) as conn:
        conn.execute("UPDATE document_headers SET workflow_profile_id='other' WHERE document_id='DOC-1'")
        conn.commit()
    with pytest.raises(SqlitePgImportError, match="fingerprints do not match"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=report_dir,
            target_repository=SQLiteDocumentsRepository(target),
        )


def test_corrupt_manifest_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "docs.db"
    target = tmp_path / "tgt.db"
    _init_db(source)
    _init_db(target)
    SQLiteDocumentsRepository(source).upsert_header(_header())
    report_dir = tmp_path / "badman"
    report_dir.mkdir()
    (report_dir / "documents_sqlite_pg_import_manifest.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(SqlitePgImportError, match="corrupt|incomplete"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=report_dir,
            target_repository=SQLiteDocumentsRepository(target),
        )


def test_live_contract_r2_source_requires_subprocess_restart_and_cas() -> None:
    """Static guard: live documents tests must prove process restart + exact CAS."""
    live = Path(__file__).with_name("test_sqlite_pg_import_live.py").read_text(encoding="utf-8")
    assert "subprocess" in live
    assert "_subprocess_read_document_snapshot" in live
    assert "len(winners) == 1" in live
    assert "len(conflicts) == 1" in live
    assert "mutate_version_if_current" in live
    assert "DocumentConflictError" in live
    assert "threading.Barrier(2)" in live
    assert "barrier.wait" in live
    assert "futures = [pool.submit(_race), pool.submit(_race)]" in live
    # Forbid sequential submit(...).result() race pattern.
    assert "pool.submit(_race).result(), pool.submit(_race).result()" not in live
    assert "[pool.submit(_race).result(), pool.submit(_race).result()]" not in live

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


class _TargetProbe(SQLiteDocumentsRepository):
    def __init__(self, db_path: Path, log: _SqlLog) -> None:
        super().__init__(db_path)
        self._log = log

    def _mark(self) -> None:
        self._log.target_ops += 1

    def get_header(self, document_id: str):
        self._mark()
        return super().get_header(document_id)

    def upsert_header(self, header):
        self._mark()
        return super().upsert_header(header)

    def get(self, document_id: str, version: int):
        self._mark()
        return super().get(document_id, version)

    def upsert(self, state):
        self._mark()
        return super().upsert(state)

    def get_artifact_by_id(self, artifact_id: str):
        self._mark()
        return super().get_artifact_by_id(artifact_id)

    def add_artifact(self, artifact):
        self._mark()
        return super().add_artifact(artifact)

    def get_read_receipt(self, user_id: str, document_id: str, version: int):
        self._mark()
        return super().get_read_receipt(user_id, document_id, version)

    def create_read_receipt(self, receipt):
        self._mark()
        return super().create_read_receipt(receipt)

    def get_workflow_comment(self, comment_id: str):
        self._mark()
        return super().get_workflow_comment(comment_id)

    def upsert_workflow_comment(self, comment):
        self._mark()
        return super().upsert_workflow_comment(comment)


def _is_ro_source(database: object, source: Path) -> bool:
    text = str(database).replace("\\", "/")
    uri = source.resolve().as_uri()
    return uri in text and "mode=ro" in text.lower()


def _install_source_tracker(monkeypatch, source: Path, log: _SqlLog, barrier: threading.Barrier | None = None) -> None:
    orig = documents_import.sqlite3.connect

    def connect(*args, **kwargs):
        conn = orig(*args, **kwargs)
        database = args[0] if args else kwargs.get("database", "")
        if _is_ro_source(database, source):
            log.connections += 1
            return _TrackingConnection(conn, log, barrier)
        return conn

    monkeypatch.setattr(documents_import.sqlite3, "connect", connect)


def _enable_wal(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        assert str(mode[0]).lower() == "wal"
        conn.commit()
    finally:
        conn.close()


def _insert_pdf_session_row(path: Path, session_id: str, document_id: str = "DOC-1") -> None:
    opened = "2024-06-01T10:00:00+00:00"
    completed = "2024-06-01T11:00:00+00:00"
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            INSERT INTO document_pdf_read_sessions
            (session_id, user_id, document_id, version, artifact_id, total_pages,
             min_seconds_per_page, source, opened_at, completed_at, completion_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, "u1", document_id, 1, None, 2, 3, "web", opened, completed, "complete"),
        )
        conn.commit()
    finally:
        conn.close()


def test_documents_source_connection_owned_until_success_or_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "docs.db"
    target_ok = tmp_path / "tgt-ok.db"
    target_fail = tmp_path / "tgt-fail.db"
    _init_db(source)
    _init_db(target_ok)
    _init_db(target_fail)
    SQLiteDocumentsRepository(source).upsert_header(_header())
    SQLiteDocumentsRepository(source).upsert(_version())

    success_log = _SqlLog()
    _install_source_tracker(monkeypatch, source, success_log)
    result = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=tmp_path / "ok",
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

    SQLiteDocumentsRepository(target_fail).upsert_header(
        replace(_header(), workflow_profile_id="other")
    )
    fail_log = _SqlLog()
    _install_source_tracker(monkeypatch, source, fail_log)
    with pytest.raises(SqlitePgImportError, match="conflict"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "fail",
            target_repository=_TargetProbe(target_fail, fail_log),
        )
    assert fail_log.connections == 1
    assert fail_log.begins == 1
    assert fail_log.commits == 0
    assert fail_log.rollbacks == 1
    assert fail_log.closes == 1
    assert fail_log.source_selects_after_target == 0


def test_documents_wal_mixed_snapshot_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "docs.db"
    target = tmp_path / "tgt.db"
    _init_db(source)
    _init_db(target)
    _enable_wal(source)
    SQLiteDocumentsRepository(source).upsert_header(_header())
    SQLiteDocumentsRepository(source).upsert(_version())
    _insert_pdf_session_row(source, "sess-old")

    log = _SqlLog()
    barrier = threading.Barrier(2, timeout=30)
    _install_source_tracker(monkeypatch, source, log, barrier=barrier)

    def _mutate() -> None:
        barrier.wait()
        _insert_pdf_session_row(source, "sess-new")
        barrier.wait()

    worker = threading.Thread(target=_mutate, name="docs-wal-writer", daemon=True)
    worker.start()
    try:
        with pytest.raises(SqlitePgImportError, match="sqlite_source_mutated"):
            import_sqlite_to_postgres(
                sqlite_path=source,
                report_dir=tmp_path / "mix",
                target_repository=_TargetProbe(target, log),
            )
    finally:
        worker.join(timeout=30)
    assert not worker.is_alive()
    assert log.connections == 1
    assert log.begins == 1
    assert log.rollbacks == 1
    assert log.closes == 1
    assert log.source_selects_after_target == 0
    with sqlite3.connect(target) as conn:
        ids = {
            str(row[0])
            for row in conn.execute("SELECT session_id FROM document_pdf_read_sessions").fetchall()
        }
    assert "sess-new" not in ids
    manifest = json.loads((tmp_path / "mix" / "documents_sqlite_pg_import_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert "sqlite_source_mutated" in str(manifest.get("error", ""))
