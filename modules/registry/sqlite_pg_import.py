"""Read-only SQLite → PostgreSQL import for Registry (AP-029 PG01-E)."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import RegistryEntry, RegisterState, ReleaseEvidenceMode
from .postgres_repository import PostgresRegistryRepository
from .repository import RegistryRepository
from .sqlite_repository import SQLiteRegistryRepository

SCHEMA_MAP_VERSION = 1
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_IN_PROGRESS = "in_progress"

_MANIFEST_REQUIRED_KEYS = frozenset(
    {"schema_map_version", "module", "status", "source_fingerprints_before"}
)


class SqlitePgImportError(RuntimeError):
    """Raised when registry SQLite→PostgreSQL import cannot proceed safely."""


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
    documents_sqlite_path: Path | str | None = None,
    target_repository: RegistryRepository | None = None,
) -> ImportResult:
    """Import registry rows from a read-only SQLite source into PostgreSQL.

    ``documents_sqlite_path`` enables referential preflight (every document_id exists).
    """
    source = Path(sqlite_path)
    report_root = Path(report_dir)
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "registry_sqlite_pg_import_manifest.json"

    before = fingerprint_sqlite_bundle(source)
    _assert_resume_compatible(report_path, before)

    if target_repository is None:
        if not postgres_dsn or not str(postgres_dsn).strip():
            raise SqlitePgImportError("postgres_dsn or target_repository is required")
        target: RegistryRepository = PostgresRegistryRepository(str(postgres_dsn))
    else:
        target = target_repository

    manifest: dict[str, Any] = {
        "schema_map_version": SCHEMA_MAP_VERSION,
        "module": "registry",
        "status": STATUS_IN_PROGRESS,
        "source_path": str(source),
        "source_fingerprints_before": before,
        "inserted": 0,
        "skipped_equal": 0,
        "conflicts": [],
    }
    _write_manifest(report_path, manifest)

    src_conn: sqlite3.Connection | None = None
    try:
        src_conn = open_readonly_sqlite(source)
        src_conn.execute("BEGIN")
        entries = _read_source_entries(src_conn)
        if entries and documents_sqlite_path is None:
            raise SqlitePgImportError(
                "documents_sqlite_path required for registry referential preflight"
            )
        if documents_sqlite_path is not None:
            _preflight_document_refs(entries, Path(documents_sqlite_path))

        inserted = 0
        skipped = 0
        for entry in entries:
            existing = target.get(entry.document_id)
            if existing is None:
                target.upsert(entry)
                inserted += 1
                continue
            if _canonical(existing) == _canonical(entry):
                skipped += 1
                continue
            raise SqlitePgImportError(
                f"registry conflict for document_id={entry.document_id}: "
                "target row differs from source (refusing silent overwrite)"
            )

        reconciliation = _reconcile_target(entries, target)

        after = fingerprint_sqlite_bundle(source)
        if after != before:
            raise SqlitePgImportError("sqlite_source_mutated")

        src_conn.execute("COMMIT")
        src_conn.close()
        src_conn = None

        digest = _entries_digest(entries)
        manifest.update(
            {
                "status": STATUS_COMPLETED,
                "source_fingerprints_after": after,
                "inserted": inserted,
                "skipped_equal": skipped,
                "row_count": len(entries),
                "content_digest": digest,
                "reconciliation": reconciliation,
                "tables": {
                    "document_registry": {
                        "count": len(entries),
                        "digest": digest,
                        "source_keyset": reconciliation["source_keyset"],
                        "target_keyset": reconciliation["target_keyset"],
                    }
                },
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
    """SHA256 of the DB file and WAL/SHM sidecars when present."""
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


def _read_source_entries(conn: sqlite3.Connection) -> list[RegistryEntry]:
    rows = conn.execute(
        "SELECT * FROM document_registry ORDER BY document_id ASC"
    ).fetchall()
    return [SQLiteRegistryRepository._row_to_entry(row) for row in rows]


def _preflight_document_refs(entries: list[RegistryEntry], documents_path: Path) -> None:
    doc_ids = {str(entry.document_id) for entry in entries}

    if not doc_ids:
        return
    if not documents_path.is_file():
        raise SqlitePgImportError("documents_sqlite_path required for registry referential preflight")

    doc_conn = open_readonly_sqlite(documents_path)
    try:
        doc_conn.execute("BEGIN")
        present = {
            str(r["document_id"])
            for r in doc_conn.execute("SELECT document_id FROM document_headers").fetchall()
        }
        doc_conn.execute("COMMIT")
    finally:
        doc_conn.close()

    missing = sorted(doc_ids - present)
    if missing:
        raise SqlitePgImportError(
            "registry referential preflight failed; missing document_ids in documents source: "
            + ", ".join(missing[:20])
        )


def _reconcile_target(entries: list[RegistryEntry], target: RegistryRepository) -> dict[str, Any]:
    source_by_id = {e.document_id: e for e in entries}
    target_entries = target.list_entries()
    target_by_id = {e.document_id: e for e in target_entries}

    source_keys = sorted(source_by_id)
    target_keys = sorted(target_by_id)
    missing = sorted(set(source_keys) - set(target_keys))
    extra = sorted(set(target_keys) - set(source_keys))
    diverged: list[str] = []
    for doc_id in source_keys:
        if doc_id not in target_by_id:
            continue
        src = source_by_id[doc_id]
        tgt = target_by_id[doc_id]
        if src.last_update_event_id != tgt.last_update_event_id:
            diverged.append(doc_id)
            continue
        if _canonical(src) != _canonical(tgt):
            diverged.append(doc_id)

    if missing or extra or diverged:
        raise SqlitePgImportError(
            "registry reconciliation failed; "
            f"missing={missing[:10]} extra={extra[:10]} diverged={diverged[:10]}"
        )

    return {
        "source_keyset": source_keys,
        "target_keyset": target_keys,
        "source_count": len(source_keys),
        "target_count": len(target_keys),
        "content_digest": _entries_digest(entries),
        "last_update_event_ids": {
            doc_id: source_by_id[doc_id].last_update_event_id for doc_id in source_keys
        },
    }


def _canonical(entry: RegistryEntry) -> str:
    payload = asdict(entry)
    for key in ("valid_from", "valid_until", "last_update_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            payload[key] = value.astimezone(timezone.utc).isoformat()
    if payload.get("release_evidence_mode") is not None:
        payload["release_evidence_mode"] = entry.release_evidence_mode.value
    if payload.get("register_state") is not None:
        payload["register_state"] = entry.register_state.value
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _entries_digest(entries: list[RegistryEntry]) -> str:
    blob = "\n".join(_canonical(e) for e in entries).encode("utf-8")
    return hashlib.sha256(blob).hexdigest().upper()


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
