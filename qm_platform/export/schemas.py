"""Deny-by-default versioned export schemas (OPS00-E)."""
from __future__ import annotations

PORTABILITY_SCHEMA_ID = "ops00-portability-v1"
EVIDENCE_SCHEMA_ID = "ops00-evidence-v1"

PORTABILITY_RECORD_KEYS = frozenset(
    {
        "organization_id",
        "record_id",
        "record_type",
        "title",
        "released_at",
        "checksum_sha256",
    }
)
PORTABILITY_ARTIFACT_KEYS = frozenset(
    {
        "artifact_id",
        "file_name",
        "media_type",
        "size_bytes",
        "checksum_sha256",
        "released",
    }
)
EVIDENCE_RECORD_KEYS = frozenset(
    {
        "audit_id",
        "action",
        "actor",
        "target",
        "result",
        "reason",
        "timestamp_utc",
        "organization_id",
    }
)

FORBIDDEN_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "private_key",
    "session",
    "dsn",
    "api_key",
    "passwd",
    "credential",
)

BACKUP_FILENAMES = frozenset({"database.dump", "manifest.json", "checksums.json"})
