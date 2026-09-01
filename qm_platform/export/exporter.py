"""Portability and Nachweis export writers (OPS00-E)."""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from qm_platform.export.schemas import (
    BACKUP_FILENAMES,
    EVIDENCE_RECORD_KEYS,
    EVIDENCE_SCHEMA_ID,
    FORBIDDEN_KEY_FRAGMENTS,
    PORTABILITY_ARTIFACT_KEYS,
    PORTABILITY_RECORD_KEYS,
    PORTABILITY_SCHEMA_ID,
)
from qm_platform.runtime.paths import resolve_home_path, runtime_home


class ExportError(RuntimeError):
    """Raised when an export cannot be produced without violating the schema."""


@dataclass(frozen=True)
class ExportResult:
    export_id: str
    export_kind: str
    schema_id: str
    archive_path: str
    manifest_checksum_sha256: str
    member_count: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _reject_secret_keys(payload: Any, *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            name = str(key)
            lowered = name.casefold()
            if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise ExportError(f"secret key {path + name!r} is not exportable")
            child_path = f"{path}{name}."
            _reject_secret_keys(value, path=child_path)
        return
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            _reject_secret_keys(item, path=f"{path}[{index}].")
        return
    _reject_secret_scalar(payload, field=path.rstrip("."))


_SECRET_VALUE_MARKERS = (
    "password=",
    "passwd=",
    "-----begin ",
    "private key",
    "postgresql://",
    "postgres://",
    "$2a$",
    "$2b$",
    "$2y$",
    "$argon2",
    "eyj",
    "session=",
)


def _reject_secret_scalar(value: Any, *, field: str) -> None:
    if not isinstance(value, str):
        return
    lowered = value.casefold()
    if any(marker in lowered for marker in _SECRET_VALUE_MARKERS):
        raise ExportError(f"{field} contains secret material and is not exportable")


def _project_record(payload: Mapping[str, Any], allowed: frozenset[str], *, schema_id: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ExportError(f"{schema_id} record must be an object")
    _reject_secret_keys(payload, path="")
    unknown = sorted(str(key) for key in payload.keys() if str(key) not in allowed)
    if unknown:
        raise ExportError(f"{schema_id} unknown keys are not exportable: {', '.join(unknown)}")
    projected: dict[str, Any] = {}
    for key in sorted(allowed):
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, (dict, list)):
            raise ExportError(f"{schema_id} field {key!r} must be a scalar")
        _reject_secret_scalar(value, field=f"{schema_id}.{key}")
        projected[key] = value
    return projected


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _dumps(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2).encode("utf-8")


def _write_zip(archive_path: Path, members: dict[str, bytes]) -> str:
    checksums = {name: _sha256_bytes(content) for name, content in sorted(members.items())}
    members = dict(members)
    members["checksums.json"] = _dumps(checksums)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(members.items()):
            archive.writestr(name, content)
    return _sha256_file(archive_path)


def _exports_root(app_home: Path | None) -> Path:
    home = app_home if app_home is not None else runtime_home()
    return resolve_home_path(home, "exports")


def create_portability_export(
    *,
    records: list[Mapping[str, Any]],
    released_artifacts: list[tuple[Mapping[str, Any], Path]] | None = None,
    output_dir: Path | None = None,
    app_home: Path | None = None,
) -> ExportResult:
    """Write a portability ZIP. Released artifacts only; never a backup dump."""
    if not isinstance(records, list):
        raise ExportError("portability records must be a list")
    projected_records = [
        _project_record(item, PORTABILITY_RECORD_KEYS, schema_id=PORTABILITY_SCHEMA_ID)
        for item in records
    ]
    artifact_entries: list[dict[str, Any]] = []
    members: dict[str, bytes] = {}
    for meta, source in released_artifacts or ():
        projected = _project_record(meta, PORTABILITY_ARTIFACT_KEYS, schema_id=PORTABILITY_SCHEMA_ID)
        if projected.get("released") is not True:
            raise ExportError("portability artifacts must be marked released=true")
        file_name = str(projected.get("file_name") or "")
        if not file_name or "/" in file_name or "\\" in file_name or file_name in BACKUP_FILENAMES:
            raise ExportError("portability artifact file_name is invalid")
        source_path = Path(source)
        if not source_path.is_file():
            raise ExportError(f"released artifact file is missing: {file_name}")
        if source_path.name in BACKUP_FILENAMES or source_path.suffix.lower() == ".dump":
            raise ExportError("backup dump files are not a portability export")
        payload = source_path.read_bytes()
        actual_checksum = _sha256_bytes(payload)
        declared = str(projected.get("checksum_sha256") or "")
        if declared and declared.casefold() != actual_checksum:
            raise ExportError(f"released artifact checksum mismatch for {file_name}")
        projected["checksum_sha256"] = actual_checksum
        projected["size_bytes"] = len(payload)
        members[f"artifacts/{file_name}"] = payload
        artifact_entries.append(projected)

    export_id = str(uuid4())
    manifest = {
        "export_id": export_id,
        "export_kind": "portability",
        "schema_id": PORTABILITY_SCHEMA_ID,
        "created_at": _utc_now(),
        "record_count": len(projected_records),
        "artifact_count": len(artifact_entries),
    }
    members["manifest.json"] = _dumps(manifest)
    members["data.json"] = _dumps(projected_records)
    members["artifacts.json"] = _dumps(artifact_entries)
    destination = Path(output_dir) if output_dir is not None else _exports_root(app_home)
    archive_path = destination / f"portability-{export_id}.zip"
    archive_checksum = _write_zip(archive_path, members)
    return ExportResult(
        export_id=export_id,
        export_kind="portability",
        schema_id=PORTABILITY_SCHEMA_ID,
        archive_path=str(archive_path),
        manifest_checksum_sha256=archive_checksum,
        member_count=len(members) + 1,
    )


def create_evidence_export(
    *,
    audit_records: list[Mapping[str, Any]],
    output_dir: Path | None = None,
    app_home: Path | None = None,
) -> ExportResult:
    """Write a readable Nachweis ZIP from allowlisted audit records."""
    if not isinstance(audit_records, list):
        raise ExportError("evidence records must be a list")
    projected = [
        _project_record(item, EVIDENCE_RECORD_KEYS, schema_id=EVIDENCE_SCHEMA_ID)
        for item in audit_records
    ]
    export_id = str(uuid4())
    manifest = {
        "export_id": export_id,
        "export_kind": "evidence",
        "schema_id": EVIDENCE_SCHEMA_ID,
        "created_at": _utc_now(),
        "record_count": len(projected),
    }
    members = {
        "manifest.json": _dumps(manifest),
        "audit.jsonl": "".join(
            json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in projected
        ).encode("utf-8"),
    }
    destination = Path(output_dir) if output_dir is not None else _exports_root(app_home)
    archive_path = destination / f"evidence-{export_id}.zip"
    archive_checksum = _write_zip(archive_path, members)
    return ExportResult(
        export_id=export_id,
        export_kind="evidence",
        schema_id=EVIDENCE_SCHEMA_ID,
        archive_path=str(archive_path),
        manifest_checksum_sha256=archive_checksum,
        member_count=len(members) + 1,
    )


def load_json_records(path: Path) -> list[Mapping[str, Any]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExportError("records file is invalid JSON") from exc
    if not isinstance(raw, list):
        raise ExportError("records file must contain a JSON array")
    records: list[Mapping[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ExportError("records file entries must be objects")
        records.append(item)
    return records


def load_jsonl_records(path: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ExportError("audit jsonl is invalid JSON") from exc
        if not isinstance(item, Mapping):
            raise ExportError("audit jsonl entries must be objects")
        records.append(item)
    return records
