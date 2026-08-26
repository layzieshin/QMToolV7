"""Read-only SQLite → PostgreSQL import for Signature metadata (AP-029 PG01-E)."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .contracts import SignatureAsset, UserSignatureTemplate
from .postgres_repository import PostgresSignatureRepository
from .repository import SignatureRepository
from .secure_store import EncryptedSignatureBlobStore
from .sqlite_repository import SQLiteSignatureRepository

SCHEMA_MAP_VERSION = 1
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_IN_PROGRESS = "in_progress"

_MANIFEST_REQUIRED_KEYS = frozenset(
    {"schema_map_version", "module", "status", "source_fingerprints_before"}
)


class SqlitePgImportError(RuntimeError):
    """Raised when signature SQLite→PostgreSQL import cannot proceed safely."""


class SignatureBlobReader(Protocol):
    def get_bytes(self, storage_key: str) -> bytes: ...


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
    assets_root: Path | str | None = None,
    blob_reader: SignatureBlobReader | EncryptedSignatureBlobStore | None = None,
    target_repository: SignatureRepository | None = None,
) -> ImportResult:
    """Import signature metadata; ``storage_key`` remains a filesystem path, no blob copy."""
    source = Path(sqlite_path)
    report_root = Path(report_dir)
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "signature_sqlite_pg_import_manifest.json"
    before = fingerprint_sqlite_bundle(source)
    _assert_resume_compatible(report_path, before)

    if target_repository is None:
        if not postgres_dsn or not str(postgres_dsn).strip():
            raise SqlitePgImportError("postgres_dsn or target_repository is required")
        target: SignatureRepository = PostgresSignatureRepository(str(postgres_dsn))
    else:
        target = target_repository

    manifest: dict[str, Any] = {
        "schema_map_version": SCHEMA_MAP_VERSION,
        "module": "signature",
        "status": STATUS_IN_PROGRESS,
        "source_path": str(source),
        "source_fingerprints_before": before,
        "inserted": 0,
        "skipped_equal": 0,
    }
    _write_manifest(report_path, manifest)

    try:
        assets, templates, actives = _read_source(source)
        if assets:
            if assets_root is None:
                raise SqlitePgImportError("assets_root required when signature assets are present")
            if blob_reader is None:
                raise SqlitePgImportError(
                    "blob_reader required when signature assets are present; "
                    "refusing to invent an encryption key"
                )
            _assert_existing_blob_reader(blob_reader)
            _preflight_storage_keys(assets, Path(assets_root), blob_reader)

        inserted = 0
        skipped = 0

        for asset in assets:
            existing = target.get_asset(asset.asset_id)
            if existing is None:
                target.add_asset(asset)
                inserted += 1
            elif _canonical_asset(existing) == _canonical_asset(asset):
                skipped += 1
            else:
                raise SqlitePgImportError(
                    f"signature asset conflict asset_id={asset.asset_id}"
                )

        for template in templates:
            existing_t = target.get_template(template.template_id)
            if existing_t is None:
                target.upsert_template(template)
                inserted += 1
            elif _canonical_template(existing_t) == _canonical_template(template):
                skipped += 1
            else:
                raise SqlitePgImportError(
                    f"signature template conflict template_id={template.template_id}"
                )

        for owner_user_id, asset_id in actives:
            current = target.get_active_signature_asset_id(owner_user_id)
            if current is None:
                target.set_active_signature_asset(owner_user_id, asset_id)
                inserted += 1
            elif current == asset_id:
                skipped += 1
            else:
                raise SqlitePgImportError(
                    f"active signature conflict owner_user_id={owner_user_id}"
                )

        after = fingerprint_sqlite_bundle(source)
        if after != before:
            raise SqlitePgImportError("sqlite_source_mutated")

        digest = _content_digest(assets, templates, actives)
        manifest.update(
            {
                "status": STATUS_COMPLETED,
                "source_fingerprints_after": after,
                "inserted": inserted,
                "skipped_equal": skipped,
                "asset_count": len(assets),
                "template_count": len(templates),
                "active_count": len(actives),
                "content_digest": digest,
                "tables": {
                    "signature_assets": {
                        "count": len(assets),
                        "digest": _digest_strings([_canonical_asset(a) for a in assets]),
                    },
                    "user_signature_templates": {
                        "count": len(templates),
                        "digest": _digest_strings([_canonical_template(t) for t in templates]),
                    },
                    "user_active_signatures": {
                        "count": len(actives),
                        "digest": _digest_strings([f"{o}:{a}" for o, a in actives]),
                    },
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


def _assert_existing_blob_reader(blob_reader: SignatureBlobReader | EncryptedSignatureBlobStore) -> None:
    """Never construct or rotate keys during import; require an already-keyed store when applicable."""
    if isinstance(blob_reader, EncryptedSignatureBlobStore):
        key_file = getattr(blob_reader, "_key_file", None)
        if key_file is None or not Path(key_file).is_file():
            raise SqlitePgImportError(
                "EncryptedSignatureBlobStore key_file missing; refusing to create a new key"
            )


def _read_source(
    path: Path,
) -> tuple[list[SignatureAsset], list[UserSignatureTemplate], list[tuple[str, str]]]:
    conn = open_readonly_sqlite(path)
    try:
        conn.execute("BEGIN")
        asset_rows = conn.execute(
            "SELECT * FROM signature_assets ORDER BY asset_id ASC"
        ).fetchall()
        template_rows = conn.execute(
            "SELECT * FROM user_signature_templates ORDER BY template_id ASC"
        ).fetchall()
        active_rows = conn.execute(
            "SELECT owner_user_id, asset_id FROM user_active_signatures ORDER BY owner_user_id ASC"
        ).fetchall()
        conn.execute("COMMIT")
    finally:
        conn.close()

    helper = SQLiteSignatureRepository(path)
    assets = [
        SignatureAsset(
            asset_id=str(row["asset_id"]),
            owner_user_id=str(row["owner_user_id"]),
            storage_key=str(row["storage_key"]),
            media_type=str(row["media_type"]),
            original_filename=str(row["original_filename"]),
            sha256=str(row["sha256"]),
            size_bytes=int(row["size_bytes"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )
        for row in asset_rows
    ]
    templates = [helper._row_to_template(row) for row in template_rows]
    actives = [(str(r["owner_user_id"]), str(r["asset_id"])) for r in active_rows]
    return assets, templates, actives


def _resolve_under_root(root: Path, storage_key: str) -> Path:
    raw = str(storage_key)
    if not raw or raw.strip() != raw:
        raise SqlitePgImportError(f"invalid storage_key: {storage_key!r}")
    if Path(raw).is_absolute():
        raise SqlitePgImportError(f"absolute storage_key rejected: {storage_key}")
    root_res = root.resolve()
    candidate = (root_res / raw).resolve()
    try:
        candidate.relative_to(root_res)
    except ValueError as exc:
        raise SqlitePgImportError(f"storage_key escapes root: {storage_key}") from exc
    return candidate


def _preflight_storage_keys(
    assets: list[SignatureAsset],
    assets_root: Path,
    blob_reader: SignatureBlobReader,
) -> None:
    for asset in assets:
        candidate = _resolve_under_root(assets_root, asset.storage_key)
        if not candidate.is_file():
            raise SqlitePgImportError(
                f"signature storage_key unavailable: {asset.storage_key}"
            )
        try:
            plaintext = blob_reader.get_bytes(asset.storage_key)
        except Exception as exc:  # noqa: BLE001 — surface as import failure
            raise SqlitePgImportError(
                f"signature blob decrypt failed storage_key={asset.storage_key}: {exc}"
            ) from exc
        if len(plaintext) != int(asset.size_bytes):
            raise SqlitePgImportError(
                f"signature plaintext size mismatch storage_key={asset.storage_key}: "
                f"bytes={len(plaintext)} meta={asset.size_bytes}"
            )
        digest = hashlib.sha256(plaintext).hexdigest().lower()
        if digest != str(asset.sha256).lower():
            raise SqlitePgImportError(
                f"signature plaintext sha256 mismatch storage_key={asset.storage_key}"
            )


def _canonical_asset(asset: SignatureAsset) -> str:
    payload = asdict(asset)
    if isinstance(payload.get("created_at"), datetime):
        payload["created_at"] = asset.created_at.astimezone(timezone.utc).isoformat()
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _canonical_template(template: UserSignatureTemplate) -> str:
    payload = asdict(template)
    if isinstance(payload.get("created_at"), datetime):
        payload["created_at"] = template.created_at.astimezone(timezone.utc).isoformat()
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _content_digest(
    assets: list[SignatureAsset],
    templates: list[UserSignatureTemplate],
    actives: list[tuple[str, str]],
) -> str:
    parts = (
        [_canonical_asset(a) for a in assets]
        + [_canonical_template(t) for t in templates]
        + [f"{o}:{a}" for o, a in actives]
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
