"""Read-only SQLite → PostgreSQL import for Documents (AP-029 PG01-E)."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .contracts import (
    DocumentArtifact,
    DocumentHeader,
    DocumentReadReceipt,
    DocumentType,
    DocumentVersionState,
    WorkflowCommentRecord,
)
from .postgres_connection import runtime_connection
from .postgres_repository import PostgresDocumentsRepository
from .repository import DocumentsRepository
from .sqlite_repository import SQLiteDocumentsRepository

SCHEMA_MAP_VERSION = 1
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_IN_PROGRESS = "in_progress"

# Explicit full Boolean allowlist (SQLite INTEGER 0/1 → PG-compatible Python bool).
_BOOL_PROFILE_COLUMNS = frozenset(
    {
        "is_active",
        "four_eyes_required",
        "requires_editors",
        "requires_reviewers",
        "requires_approvers",
        "allows_content_changes",
        "signature_required",
        "revoke_if_changed",
        "is_enabled",
        "allows_profile_override",
    }
)

# Fachliche integer fields that must remain int (never bool-coerced).
_INT_PROFILE_COLUMNS = frozenset(
    {
        "version_no",
        "transition_no",
        "active_version",
        "deadline_seconds",
    }
)

_MANIFEST_REQUIRED_KEYS = frozenset(
    {"schema_map_version", "module", "status", "source_fingerprints_before"}
)

_PROFILE_TABLES = (
    "workflow_profile_definitions",
    "workflow_profile_versions",
    "workflow_profile_transitions",
    "document_type_definitions",
    "workflow_profile_imports",
)


class SqlitePgImportError(RuntimeError):
    """Raised when documents SQLite→PostgreSQL import cannot proceed safely."""


@dataclass(frozen=True)
class ImportResult:
    status: str
    report_path: str
    inserted: int
    skipped_equal: int
    source_fingerprints: dict[str, str | None]
    content_digest: str


def import_sqlite_to_postgres(
    *,
    sqlite_path: Path | str,
    postgres_dsn: str | None = None,
    report_dir: Path | str,
    artifacts_root: Path | str | None = None,
    target_repository: DocumentsRepository | None = None,
) -> ImportResult:
    source = Path(sqlite_path)
    report_root = Path(report_dir)
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "documents_sqlite_pg_import_manifest.json"
    before = fingerprint_sqlite_bundle(source)
    _assert_resume_compatible(report_path, before)

    if target_repository is None:
        if not postgres_dsn or not str(postgres_dsn).strip():
            raise SqlitePgImportError("postgres_dsn or target_repository is required")
        target: DocumentsRepository = PostgresDocumentsRepository(str(postgres_dsn))
        dsn = str(postgres_dsn)
    else:
        target = target_repository
        dsn = postgres_dsn or getattr(target, "_dsn", None)

    manifest: dict[str, Any] = {
        "schema_map_version": SCHEMA_MAP_VERSION,
        "module": "documents",
        "status": STATUS_IN_PROGRESS,
        "source_path": str(source),
        "source_fingerprints_before": before,
        "inserted": 0,
        "skipped_equal": 0,
        "tables": {},
    }
    _write_manifest(report_path, manifest)

    src_conn: sqlite3.Connection | None = None
    try:
        src_conn = open_readonly_sqlite(source)
        src_conn.execute("BEGIN")
        headers, versions, artifacts, receipts, comments = _read_core(src_conn, helper_path=source)
        pdf_sessions = _read_pdf_sessions(src_conn)
        pdf_pages = _read_pdf_page_progress(src_conn)
        profile_tables = _read_workflow_profile_tables(src_conn)
        _preflight_workflow_profile_graph(profile_tables)
        profile_rows_present = any(
            bool(payload.get("rows")) for payload in profile_tables.values()
        )
        if profile_rows_present and (not dsn or not str(dsn).strip()):
            raise SqlitePgImportError(
                "workflow profile import requires a PostgreSQL target DSN"
            )
        if artifacts and artifacts_root is None:
            raise SqlitePgImportError(
                "artifacts_root required when document artifacts are present"
            )
        if artifacts_root is not None:
            _preflight_artifacts(artifacts, Path(artifacts_root))

        inserted = 0
        skipped = 0

        for header in headers:
            existing = target.get_header(header.document_id)
            if existing is None:
                target.upsert_header(header)
                inserted += 1
            elif _canonical(existing) == _canonical(header):
                skipped += 1
            else:
                raise SqlitePgImportError(f"header conflict document_id={header.document_id}")

        for state in versions:
            existing_s = target.get(state.document_id, state.version)
            if existing_s is None:
                target.upsert(state)
                inserted += 1
            elif _canonical(existing_s) == _canonical(state):
                skipped += 1
            else:
                raise SqlitePgImportError(
                    f"version conflict document_id={state.document_id} version={state.version}"
                )

        for artifact in artifacts:
            existing_a = target.get_artifact_by_id(artifact.artifact_id)
            if existing_a is None:
                target.add_artifact(artifact)
                inserted += 1
            elif _canonical(existing_a) == _canonical(artifact):
                skipped += 1
            else:
                raise SqlitePgImportError(f"artifact conflict artifact_id={artifact.artifact_id}")

        for receipt in receipts:
            existing_r = target.get_read_receipt(receipt.user_id, receipt.document_id, receipt.version)
            if existing_r is None:
                target.create_read_receipt(receipt)
                inserted += 1
            elif _canonical(existing_r) == _canonical(receipt):
                skipped += 1
            else:
                raise SqlitePgImportError(f"read receipt conflict receipt_id={receipt.receipt_id}")

        for comment in comments:
            existing_c = target.get_workflow_comment(comment.comment_id)
            if existing_c is None:
                target.upsert_workflow_comment(comment)
                inserted += 1
            elif _canonical(existing_c) == _canonical(comment):
                skipped += 1
            else:
                raise SqlitePgImportError(f"comment conflict comment_id={comment.comment_id}")

        pdf_stats = _apply_pdf_read_tables(pdf_sessions, pdf_pages, target=target, dsn=dsn)
        inserted += int(pdf_stats["inserted"])
        skipped += int(pdf_stats["skipped_equal"])

        profile_stats: dict[str, Any] = {"inserted": 0, "skipped_equal": 0, "tables": {}}
        if dsn:
            profile_stats = _apply_workflow_profiles(profile_tables, str(dsn))
            inserted += int(profile_stats["inserted"])
            skipped += int(profile_stats["skipped_equal"])

        after = fingerprint_sqlite_bundle(source)
        if after != before:
            raise SqlitePgImportError("sqlite_source_mutated")

        src_conn.execute("COMMIT")
        src_conn.close()
        src_conn = None

        digest = _core_digest(headers, versions, artifacts, receipts, comments)
        tables = dict(pdf_stats.get("tables") or {})
        tables.update(profile_stats.get("tables") or {})
        tables.update(
            {
                "document_headers": {
                    "count": len(headers),
                    "digest": _digest_strings([_canonical(h) for h in headers]),
                },
                "document_versions": {
                    "count": len(versions),
                    "digest": _digest_strings([_canonical(v) for v in versions]),
                },
                "document_artifacts": {
                    "count": len(artifacts),
                    "digest": _digest_strings([_canonical(a) for a in artifacts]),
                },
                "document_read_receipts": {
                    "count": len(receipts),
                    "digest": _digest_strings([_canonical(r) for r in receipts]),
                },
                "document_workflow_comments": {
                    "count": len(comments),
                    "digest": _digest_strings([_canonical(c) for c in comments]),
                },
            }
        )
        manifest.update(
            {
                "status": STATUS_COMPLETED,
                "source_fingerprints_after": after,
                "inserted": inserted,
                "skipped_equal": skipped,
                "header_count": len(headers),
                "version_count": len(versions),
                "artifact_count": len(artifacts),
                "receipt_count": len(receipts),
                "comment_count": len(comments),
                "workflow_profile_stats": profile_stats,
                "pdf_read_stats": pdf_stats,
                "tables": tables,
                "content_digest": digest,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        _write_manifest(report_path, manifest)
        return ImportResult(
            status=STATUS_COMPLETED,
            report_path=str(report_path),
            inserted=inserted,
            skipped_equal=skipped,
            source_fingerprints=before,
            content_digest=digest,
        )
    except Exception as exc:
        if src_conn is not None:
            try:
                if src_conn.in_transaction:
                    src_conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            try:
                src_conn.close()
            except sqlite3.Error:
                pass
            src_conn = None
        manifest["status"] = STATUS_FAILED
        manifest["error"] = str(exc)
        manifest["source_fingerprints_after"] = fingerprint_sqlite_bundle(source)
        _write_manifest(report_path, manifest)
        raise


def fingerprint_sqlite_bundle(path: Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for label, candidate in (
        ("db", path),
        ("wal", Path(str(path) + "-wal")),
        ("shm", Path(str(path) + "-shm")),
    ):
        out[label] = _file_sha256(candidate) if candidate.is_file() else None
    return out


def open_readonly_sqlite(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SqlitePgImportError(f"sqlite source missing: {path}")
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _read_core(
    conn: sqlite3.Connection,
    *,
    helper_path: Path,
) -> tuple[
    list[DocumentHeader],
    list[DocumentVersionState],
    list[DocumentArtifact],
    list[DocumentReadReceipt],
    list[WorkflowCommentRecord],
]:
    helper = SQLiteDocumentsRepository(helper_path)
    header_rows = conn.execute("SELECT * FROM document_headers ORDER BY document_id").fetchall()
    version_rows = conn.execute(
        "SELECT * FROM document_versions ORDER BY document_id, version"
    ).fetchall()
    artifact_rows = conn.execute(
        "SELECT * FROM document_artifacts ORDER BY artifact_id"
    ).fetchall()
    receipt_rows = conn.execute(
        "SELECT * FROM document_read_receipts ORDER BY receipt_id"
    ).fetchall()
    comment_rows = conn.execute(
        "SELECT * FROM document_workflow_comments ORDER BY comment_id"
    ).fetchall()

    headers = [SQLiteDocumentsRepository._row_to_header(r) for r in header_rows]
    versions = [helper._row_to_state(r) for r in version_rows]
    artifacts = [SQLiteDocumentsRepository._row_to_artifact(r) for r in artifact_rows]
    receipts = []
    for row in receipt_rows:
        receipts.append(
            DocumentReadReceipt(
                receipt_id=str(row["receipt_id"]),
                user_id=str(row["user_id"]),
                document_id=str(row["document_id"]),
                version=int(row["version"]),
                confirmed_at=datetime.fromisoformat(str(row["confirmed_at"])),
                source=str(row["source"]),
            )
        )
    comments = [helper._row_to_workflow_comment(r) for r in comment_rows]
    return headers, versions, artifacts, receipts, comments


def _resolve_under_root(root: Path, storage_key: str) -> Path:
    raw = str(storage_key)
    if not raw or raw.strip() != raw:
        raise SqlitePgImportError(f"invalid storage_key: {storage_key!r}")
    candidate_input = Path(raw)
    if candidate_input.is_absolute():
        raise SqlitePgImportError(f"absolute storage_key rejected: {storage_key}")
    root_res = root.resolve()
    candidate = (root_res / raw).resolve()
    try:
        candidate.relative_to(root_res)
    except ValueError as exc:
        raise SqlitePgImportError(f"storage_key escapes root: {storage_key}") from exc
    return candidate


def _preflight_workflow_profile_graph(profile_tables: dict[str, dict[str, Any]]) -> None:
    """Fail closed when SQLite carries profile rows without a complete type-binding graph."""
    defn_payload = profile_tables.get("workflow_profile_definitions")
    if defn_payload is None:
        return
    profile_rows = defn_payload.get("rows") or []
    if not profile_rows:
        return
    profile_codes = {str(row["profile_code"]) for row in profile_rows}
    dtype_payload = profile_tables.get("document_type_definitions")
    if dtype_payload is None:
        raise SqlitePgImportError(
            "workflow profile graph incomplete: document_type_definitions table missing"
        )
    bound_types = {str(row["document_type"]) for row in (dtype_payload.get("rows") or [])}
    missing_types = [doc_type.value for doc_type in DocumentType if doc_type.value not in bound_types]
    if missing_types:
        raise SqlitePgImportError(
            "workflow profile graph incomplete: missing document type bindings: "
            + ", ".join(missing_types)
        )
    for row in dtype_payload.get("rows") or []:
        profile_code = str(row["default_profile_code"])
        if profile_code not in profile_codes:
            raise SqlitePgImportError(
                "workflow profile graph inconsistent: document_type="
                f"{row['document_type']} references unknown profile_code={profile_code}"
            )


def _preflight_artifacts(artifacts: list[DocumentArtifact], root: Path) -> None:
    for artifact in artifacts:
        candidate = _resolve_under_root(root, artifact.storage_key)
        if not candidate.is_file():
            raise SqlitePgImportError(f"document artifact storage_key unavailable: {artifact.storage_key}")
        size = candidate.stat().st_size
        if size != int(artifact.size_bytes):
            raise SqlitePgImportError(
                f"document artifact size mismatch storage_key={artifact.storage_key}: "
                f"file={size} meta={artifact.size_bytes}"
            )
        digest = _file_sha256(candidate).lower()
        if digest != str(artifact.sha256).lower():
            raise SqlitePgImportError(
                f"document artifact sha256 mismatch storage_key={artifact.storage_key}"
            )


def _apply_pdf_read_tables(
    sessions: list[dict[str, Any]],
    pages: list[dict[str, Any]],
    *,
    target: DocumentsRepository,
    dsn: str | None,
) -> dict[str, Any]:
    inserted = 0
    skipped = 0
    session_inserted = 0
    session_skipped = 0
    page_inserted = 0
    page_skipped = 0

    backend = _resolve_write_backend(target, dsn)

    for session in sessions:
        existing = _fetch_pdf_session(backend, session["session_id"])
        if existing is None:
            _insert_pdf_session(backend, session)
            inserted += 1
            session_inserted += 1
        elif _pdf_session_canonical(existing) == _pdf_session_canonical(session):
            skipped += 1
            session_skipped += 1
        else:
            raise SqlitePgImportError(f"pdf session conflict session_id={session['session_id']}")

    for page in pages:
        existing_p = _fetch_pdf_page(backend, page["session_id"], int(page["page_number"]))
        if existing_p is None:
            _insert_pdf_page(backend, page)
            inserted += 1
            page_inserted += 1
        elif _pdf_page_canonical(existing_p) == _pdf_page_canonical(page):
            skipped += 1
            page_skipped += 1
        else:
            raise SqlitePgImportError(
                f"pdf page conflict session_id={page['session_id']} page={page['page_number']}"
            )

    return {
        "inserted": inserted,
        "skipped_equal": skipped,
        "tables": {
            "document_pdf_read_sessions": {
                "count": len(sessions),
                "digest": _digest_strings([_pdf_session_canonical(s) for s in sessions]),
                "inserted": session_inserted,
                "skipped_equal": session_skipped,
            },
            "document_pdf_read_page_progress": {
                "count": len(pages),
                "digest": _digest_strings([_pdf_page_canonical(p) for p in pages]),
                "inserted": page_inserted,
                "skipped_equal": page_skipped,
            },
        },
    }


def _resolve_write_backend(target: DocumentsRepository, dsn: str | None) -> tuple[str, Any]:
    if dsn and str(dsn).strip():
        return ("pg", str(dsn))
    target_dsn = getattr(target, "_dsn", None)
    if target_dsn and str(target_dsn).strip():
        return ("pg", str(target_dsn))
    db_path = getattr(target, "_db_path", None)
    if db_path is not None:
        return ("sqlite", Path(db_path))
    raise SqlitePgImportError(
        "pdf_read import requires postgres_dsn or a target repository with writable path/DSN"
    )


def _read_pdf_sessions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='document_pdf_read_sessions'"
    ).fetchone()
    if exists is None:
        return []
    rows = conn.execute(
        "SELECT * FROM document_pdf_read_sessions ORDER BY session_id"
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "session_id": str(row["session_id"]),
                "user_id": str(row["user_id"]),
                "document_id": str(row["document_id"]),
                "version": int(row["version"]),
                "artifact_id": str(row["artifact_id"]) if row["artifact_id"] else None,
                "total_pages": int(row["total_pages"]),
                "min_seconds_per_page": int(row["min_seconds_per_page"]),
                "source": str(row["source"]),
                "opened_at": str(row["opened_at"]),
                "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
                "completion_result": str(row["completion_result"]) if row["completion_result"] else None,
            }
        )
    return out


def _read_pdf_page_progress(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='document_pdf_read_page_progress'"
    ).fetchone()
    if exists is None:
        return []
    rows = conn.execute(
        "SELECT * FROM document_pdf_read_page_progress ORDER BY session_id, page_number"
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        reached = row["reached_threshold"]
        if isinstance(reached, bool):
            reached_b = reached
        else:
            reached_b = bool(int(reached))
        out.append(
            {
                "session_id": str(row["session_id"]),
                "page_number": int(row["page_number"]),
                "accumulated_seconds": int(row["accumulated_seconds"]),
                "reached_threshold": reached_b,
                "first_seen_at": str(row["first_seen_at"]) if row["first_seen_at"] else None,
                "last_seen_at": str(row["last_seen_at"]) if row["last_seen_at"] else None,
            }
        )
    return out


def _fetch_pdf_session(backend: tuple[str, Any], session_id: str) -> dict[str, Any] | None:
    kind, handle = backend
    if kind == "sqlite":
        with sqlite3.connect(handle) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM document_pdf_read_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {k: row[k] for k in row.keys()}
    with runtime_connection(handle) as conn:
        row = conn.execute(
            "SELECT * FROM documents.document_pdf_read_sessions WHERE session_id = %s",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def _fetch_pdf_page(
    backend: tuple[str, Any], session_id: str, page_number: int
) -> dict[str, Any] | None:
    kind, handle = backend
    if kind == "sqlite":
        with sqlite3.connect(handle) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM document_pdf_read_page_progress WHERE session_id = ? AND page_number = ?",
                (session_id, page_number),
            ).fetchone()
        if row is None:
            return None
        return {k: row[k] for k in row.keys()}
    with runtime_connection(handle) as conn:
        row = conn.execute(
            "SELECT * FROM documents.document_pdf_read_page_progress "
            "WHERE session_id = %s AND page_number = %s",
            (session_id, page_number),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def _insert_pdf_session(backend: tuple[str, Any], session: dict[str, Any]) -> None:
    cols = (
        "session_id",
        "user_id",
        "document_id",
        "version",
        "artifact_id",
        "total_pages",
        "min_seconds_per_page",
        "source",
        "opened_at",
        "completed_at",
        "completion_result",
    )
    values = tuple(session[c] for c in cols)
    kind, handle = backend
    if kind == "sqlite":
        placeholders = ", ".join("?" for _ in cols)
        with sqlite3.connect(handle) as conn:
            conn.execute(
                f"INSERT INTO document_pdf_read_sessions ({', '.join(cols)}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
        return
    placeholders = ", ".join("%s" for _ in cols)
    with runtime_connection(handle) as conn:
        conn.execute(
            f"INSERT INTO documents.document_pdf_read_sessions ({', '.join(cols)}) VALUES ({placeholders})",
            values,
        )
        conn.commit()


def _insert_pdf_page(backend: tuple[str, Any], page: dict[str, Any]) -> None:
    cols = (
        "session_id",
        "page_number",
        "accumulated_seconds",
        "reached_threshold",
        "first_seen_at",
        "last_seen_at",
    )
    kind, handle = backend
    if kind == "sqlite":
        values = (
            page["session_id"],
            page["page_number"],
            page["accumulated_seconds"],
            1 if page["reached_threshold"] else 0,
            page["first_seen_at"],
            page["last_seen_at"],
        )
        with sqlite3.connect(handle) as conn:
            conn.execute(
                f"INSERT INTO document_pdf_read_page_progress ({', '.join(cols)}) VALUES (?, ?, ?, ?, ?, ?)",
                values,
            )
            conn.commit()
        return
    values = (
        page["session_id"],
        page["page_number"],
        page["accumulated_seconds"],
        bool(page["reached_threshold"]),
        page["first_seen_at"],
        page["last_seen_at"],
    )
    with runtime_connection(handle) as conn:
        conn.execute(
            f"INSERT INTO documents.document_pdf_read_page_progress ({', '.join(cols)}) "
            f"VALUES (%s, %s, %s, %s, %s, %s)",
            values,
        )
        conn.commit()


def _pdf_session_canonical(row: dict[str, Any]) -> str:
    payload = {
        "session_id": str(row["session_id"]),
        "user_id": str(row["user_id"]),
        "document_id": str(row["document_id"]),
        "version": int(row["version"]),
        "artifact_id": str(row["artifact_id"]) if row.get("artifact_id") else None,
        "total_pages": int(row["total_pages"]),
        "min_seconds_per_page": int(row["min_seconds_per_page"]),
        "source": str(row["source"]),
        "opened_at": _norm_ts(row.get("opened_at")),
        "completed_at": _norm_ts(row.get("completed_at")),
        "completion_result": str(row["completion_result"]) if row.get("completion_result") else None,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _pdf_page_canonical(row: dict[str, Any]) -> str:
    reached = row["reached_threshold"]
    if not isinstance(reached, bool):
        reached = bool(int(reached))
    payload = {
        "session_id": str(row["session_id"]),
        "page_number": int(row["page_number"]),
        "accumulated_seconds": int(row["accumulated_seconds"]),
        "reached_threshold": reached,
        "first_seen_at": _norm_ts(row.get("first_seen_at")),
        "last_seen_at": _norm_ts(row.get("last_seen_at")),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _norm_ts(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _read_workflow_profile_tables(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    captured: dict[str, dict[str, Any]] = {}
    for table in _PROFILE_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists is None:
            continue
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        columns = [k for k in rows[0].keys()] if rows else []
        captured[table] = {
            "columns": columns,
            "rows": [{column: row[column] for column in (columns or list(row.keys()))} for row in rows],
        }
    return captured


def _apply_workflow_profiles(captured: dict[str, dict[str, Any]], dsn: str) -> dict[str, Any]:
    """Copy captured workflow profile tables with bool coercion; equal-skip / diverge-fail."""
    inserted = 0
    skipped = 0
    table_meta: dict[str, Any] = {}
    with runtime_connection(dsn) as conn:
        for table in _PROFILE_TABLES:
            payload = captured.get(table)
            if payload is None:
                continue
            rows = payload["rows"]
            columns = list(payload["columns"])
            digests: list[str] = []
            table_inserted = 0
            table_skipped = 0
            if rows:
                if not columns:
                    columns = list(rows[0].keys())
                pk = _guess_pk(table, columns)
                for row in rows:
                    values = [_coerce_profile_value(col, row[col]) for col in columns]
                    digests.append(
                        _row_payload({c: _coerce_profile_value(c, row[c]) for c in columns}, columns)
                    )
                    where = " AND ".join(f"{c} = %s" for c in pk)
                    pk_vals = [_coerce_profile_value(c, row[c]) for c in pk]
                    existing = conn.execute(
                        f"SELECT * FROM documents.{table} WHERE {where}",
                        tuple(pk_vals),
                    ).fetchone()
                    if existing is None:
                        placeholders = ", ".join(["%s"] * len(columns))
                        col_list = ", ".join(columns)
                        conn.execute(
                            f"INSERT INTO documents.{table} ({col_list}) VALUES ({placeholders})",
                            tuple(values),
                        )
                        inserted += 1
                        table_inserted += 1
                    else:
                        if _row_payload(existing, columns) != _row_payload(
                            {c: _coerce_profile_value(c, row[c]) for c in columns}, columns
                        ):
                            raise SqlitePgImportError(f"workflow profile conflict in {table}")
                        skipped += 1
                        table_skipped += 1
            table_meta[table] = {
                "count": len(rows),
                "digest": _digest_strings(digests),
                "inserted": table_inserted,
                "skipped_equal": table_skipped,
            }
        conn.commit()
    return {"inserted": inserted, "skipped_equal": skipped, "tables": table_meta}


def _guess_pk(table: str, columns: list[str]) -> list[str]:
    if table == "workflow_profile_definitions" and "profile_code" in columns:
        return ["profile_code"]
    if table == "workflow_profile_versions" and "profile_code" in columns and "version_no" in columns:
        return ["profile_code", "version_no"]
    if table == "workflow_profile_transitions" and "profile_transition_id" in columns:
        return ["profile_transition_id"]
    if table == "workflow_profile_transitions" and "transition_id" in columns:
        return ["transition_id"]
    if "id" in columns:
        return ["id"]
    return [columns[0]]


def _coerce_profile_value(column: str, value: object) -> object:
    if column in _INT_PROFILE_COLUMNS:
        if value is None:
            return None
        if isinstance(value, bool):
            raise SqlitePgImportError(f"integer profile column {column} must not be bool")
        return int(value)
    if column in _BOOL_PROFILE_COLUMNS:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return bool(int(value))
    return value


def _row_payload(row: dict[str, object] | Any, columns: list[str]) -> str:
    if hasattr(row, "keys") and not isinstance(row, dict):
        data = {c: row[c] for c in columns}
    else:
        data = {c: row[c] for c in columns}  # type: ignore[index]
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.astimezone(timezone.utc).isoformat()
        elif isinstance(value, memoryview):
            data[key] = bytes(value).hex()
        elif key in _BOOL_PROFILE_COLUMNS and value is not None and not isinstance(value, bool):
            data[key] = bool(int(value))
    return json.dumps(data, sort_keys=True, ensure_ascii=True, default=str)


def _normalize_canonical_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _norm_ts(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, frozenset):
        return sorted(_normalize_canonical_value(item) for item in value)
    if isinstance(value, tuple):
        return [_normalize_canonical_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _normalize_canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dataclass_fields__"):
        return _normalize_canonical_value(asdict(value))  # type: ignore[arg-type]
    return value


def _canonical(obj: object) -> str:
    if hasattr(obj, "__dataclass_fields__"):
        payload = asdict(obj)  # type: ignore[arg-type]
    else:
        payload = dict(obj)  # type: ignore[arg-type]
    # Repository upserts rewrite updated_at; equal-skip compares fachliche payload only.
    payload.pop("updated_at", None)
    payload.pop("available_actions", None)
    normalized = {str(key): _normalize_canonical_value(val) for key, val in payload.items()}
    return json.dumps(normalized, sort_keys=True, ensure_ascii=True)


def _core_digest(
    headers: list[DocumentHeader],
    versions: list[DocumentVersionState],
    artifacts: list[DocumentArtifact],
    receipts: list[DocumentReadReceipt],
    comments: list[WorkflowCommentRecord],
) -> str:
    parts = (
        [_canonical(h) for h in headers]
        + [_canonical(v) for v in versions]
        + [_canonical(a) for a in artifacts]
        + [_canonical(r) for r in receipts]
        + [_canonical(c) for c in comments]
    )
    return _digest_strings(parts)


def _digest_strings(parts: list[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest().upper()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().upper()


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _assert_resume_compatible(report_path: Path, fingerprints: dict[str, str | None]) -> None:
    if not report_path.is_file():
        return
    try:
        prior = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SqlitePgImportError("run-manifest corrupt or unreadable") from exc
    if not isinstance(prior, dict):
        raise SqlitePgImportError("run-manifest incomplete")
    missing = sorted(_MANIFEST_REQUIRED_KEYS - set(prior.keys()))
    if missing:
        raise SqlitePgImportError(f"run-manifest incomplete; missing keys: {', '.join(missing)}")
    prior_fp = prior.get("source_fingerprints_before")
    if prior_fp != fingerprints:
        raise SqlitePgImportError(
            "existing run-manifest source fingerprints do not match current SQLite snapshot"
        )
