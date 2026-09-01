"""Secret-redacted technical diagnostic ZIP (OPS00-F).

Not a backup set, not a portability export, and not a fachliche Nachweisquelle.
Does not truncate live logs.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from qm_platform.audit.redaction import redact_audit_details
from qm_platform.runtime.health import build_readiness_report
from qm_platform.runtime.paths import resolve_home_path, runtime_home

DIAGNOSTIC_SCHEMA_ID = "ops00-diagnostic-v1"
_FORBIDDEN_MEMBER_NAMES = frozenset(
    {
        "database.dump",
        "license.json",
        "dev_ed25519_private.pem",
        "prod_ed25519_private.pem",
    }
)
_CONFIG_KEYS = (
    "QMTOOL_HOME",
    "QMTOOL_BIND_HOST",
    "QMTOOL_BIND_PORT",
    "QMTOOL_TLS_CERT_FILE",
    "QMTOOL_TLS_KEY_FILE",
    "QMTOOL_WEBCLIENT_DIST",
    "QMTOOL_LICENSE_MODE",
    "QMTOOL_RUNTIME_PROFILE",
    "QMTOOL_PG_DSN",
    "QMTOOL_PG_HOST",
    "QMTOOL_PG_PORT",
    "QMTOOL_PG_DATABASE",
    "QMTOOL_PG_USER",
    "QMTOOL_PG_PASSWORD",
)


class DiagnosticBundleError(RuntimeError):
    """Raised when a diagnostic ZIP cannot be produced without leaking secrets."""


@dataclass(frozen=True)
class DiagnosticBundleResult:
    bundle_id: str
    schema_id: str
    archive_path: str
    member_count: int
    manifest_checksum_sha256: str


def create_diagnostic_bundle(
    *,
    output_dir: Path,
    app_home: Path | None = None,
    postgres_dsn: str | None = None,
) -> DiagnosticBundleResult:
    home = app_home if app_home is not None else runtime_home()
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    bundle_id = uuid4().hex
    archive_path = destination / f"diagnostic-{bundle_id}.zip"

    readiness = build_readiness_report(app_home=home, postgres_dsn=postgres_dsn)
    members: dict[str, bytes] = {
        "ready.json": _dump_json(
            {
                "ready": readiness.ready,
                "checks": dict(readiness.checks),
            }
        ),
        "config-keys.json": _dump_json(
            {
                "keys_present": {
                    key: bool(str(os.environ.get(key, "") or "").strip())
                    for key in _CONFIG_KEYS
                }
            }
        ),
        "logs/platform.log.jsonl": _redact_log_bytes(
            resolve_home_path(home, "storage/platform/logs/platform.log")
        ),
        "logs/audit.log.jsonl": _redact_log_bytes(
            resolve_home_path(home, "storage/platform/logs/audit.log")
        ),
    }
    checksums = {name: hashlib.sha256(payload).hexdigest() for name, payload in members.items()}
    manifest = {
        "schema_id": DIAGNOSTIC_SCHEMA_ID,
        "bundle_id": bundle_id,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "kind": "diagnostic",
        "member_count": len(members) + 2,
    }
    manifest_bytes = _dump_json(manifest)
    checksums["manifest.json"] = hashlib.sha256(manifest_bytes).hexdigest()
    checksum_bytes = _dump_json(checksums)

    _reject_forbidden_names(set(members) | {"manifest.json", "checksums.json"})
    _reject_secret_bytes(manifest_bytes, field="manifest.json")
    _reject_secret_bytes(checksum_bytes, field="checksums.json")
    for name, payload in members.items():
        _reject_secret_bytes(payload, field=name)

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", manifest_bytes)
        archive.writestr("checksums.json", checksum_bytes)
        for name, payload in members.items():
            archive.writestr(name, payload)

    return DiagnosticBundleResult(
        bundle_id=bundle_id,
        schema_id=DIAGNOSTIC_SCHEMA_ID,
        archive_path=str(archive_path),
        member_count=len(members) + 2,
        manifest_checksum_sha256=checksums["manifest.json"],
    )


def _dump_json(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8")


def _redact_log_bytes(path: Path) -> bytes:
    if not path.is_file():
        return b""
    redacted: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        redacted.append(_redact_log_line(line))
    if not redacted:
        return b""
    return ("\n".join(redacted) + "\n").encode("utf-8")


def _redact_log_line(line: str) -> str:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return str(redact_audit_details(line))
    return json.dumps(redact_audit_details(parsed), ensure_ascii=True)


def _reject_secret_bytes(payload: bytes, *, field: str) -> None:
    text = payload.decode("utf-8", errors="replace")
    if re.search(r"Bearer\s+(?!<redacted>)\S+", text, re.IGNORECASE):
        raise DiagnosticBundleError(f"secret material remains in {field}")
    if re.search(r"Basic\s+(?!<redacted>)\S+", text, re.IGNORECASE):
        raise DiagnosticBundleError(f"secret material remains in {field}")


def _reject_forbidden_names(names: set[str]) -> None:
    lowered = {name.casefold() for name in names}
    for forbidden in _FORBIDDEN_MEMBER_NAMES:
        if forbidden in lowered or any(name.endswith("/" + forbidden) for name in lowered):
            raise DiagnosticBundleError(f"forbidden diagnostic member {forbidden}")
    for name in names:
        lowered_name = name.casefold()
        if lowered_name.endswith(".dump") or lowered_name.endswith(".pem"):
            raise DiagnosticBundleError(f"forbidden diagnostic member {name}")
