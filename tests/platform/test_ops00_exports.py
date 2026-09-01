"""Static checks for OPS00-E portability vs Nachweis exports."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from qm_platform.export import (
    ExportError,
    create_evidence_export,
    create_portability_export,
)
from qm_platform.export.schemas import EVIDENCE_SCHEMA_ID, PORTABILITY_SCHEMA_ID


def _portability_record() -> dict[str, str]:
    return {
        "organization_id": "org-1",
        "record_id": "rec-1",
        "record_type": "document",
        "title": "Released procedure",
        "released_at": "2026-09-01T00:00:00+00:00",
        "checksum_sha256": "a" * 64,
    }


def _evidence_record() -> dict[str, str]:
    return {
        "audit_id": "aud-1",
        "action": "document.release",
        "actor": "admin",
        "target": "rec-1",
        "result": "ok",
        "reason": "approved",
        "timestamp_utc": "2026-09-01T00:00:00+00:00",
        "organization_id": "org-1",
    }


def test_portability_zip_is_not_a_backup_set(tmp_path: Path) -> None:
    result = create_portability_export(
        records=[_portability_record()],
        output_dir=tmp_path,
    )
    assert result.schema_id == PORTABILITY_SCHEMA_ID
    assert result.export_kind == "portability"
    with zipfile.ZipFile(result.archive_path) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "checksums.json" in names
        assert "data.json" in names
        assert "database.dump" not in names
        manifest = json.loads(archive.read("manifest.json"))
        checksums = json.loads(archive.read("checksums.json"))
        assert manifest["schema_id"] == PORTABILITY_SCHEMA_ID
        data_checksum = hashlib.sha256(archive.read("data.json")).hexdigest()
        assert checksums["data.json"] == data_checksum


def test_evidence_export_uses_separate_schema(tmp_path: Path) -> None:
    portability = create_portability_export(
        records=[_portability_record()],
        output_dir=tmp_path,
    )
    evidence = create_evidence_export(
        audit_records=[_evidence_record()],
        output_dir=tmp_path,
    )
    assert evidence.schema_id == EVIDENCE_SCHEMA_ID
    assert evidence.schema_id != portability.schema_id
    assert evidence.export_kind == "evidence"
    with zipfile.ZipFile(evidence.archive_path) as archive:
        names = set(archive.namelist())
        assert "audit.jsonl" in names
        assert "database.dump" not in names
        assert "data.json" not in names
        body = archive.read("audit.jsonl").decode("utf-8")
        assert "password" not in body.casefold()


def test_unknown_keys_fail_closed(tmp_path: Path) -> None:
    record = dict(_portability_record())
    record["extra_field"] = "nope"
    with pytest.raises(ExportError, match="unknown keys"):
        create_portability_export(records=[record], output_dir=tmp_path)


@pytest.mark.parametrize("secret_key", ["password", "session_token", "private_key", "dsn"])
def test_nested_secret_fixtures_fail_closed(tmp_path: Path, secret_key: str) -> None:
    record = dict(_portability_record())
    record["title"] = "ok"
    nested = {"nested": {secret_key: "should-not-export"}}
    with pytest.raises(ExportError, match="secret key"):
        create_portability_export(records=[nested], output_dir=tmp_path)


def test_released_artifact_is_checksummed_and_dump_refused(tmp_path: Path) -> None:
    artifact = tmp_path / "released.pdf"
    artifact.write_bytes(b"%PDF-export")
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    result = create_portability_export(
        records=[_portability_record()],
        released_artifacts=[
            (
                {
                    "artifact_id": "art-1",
                    "file_name": "released.pdf",
                    "media_type": "application/pdf",
                    "size_bytes": artifact.stat().st_size,
                    "checksum_sha256": checksum,
                    "released": True,
                },
                artifact,
            )
        ],
        output_dir=tmp_path / "out",
    )
    with zipfile.ZipFile(result.archive_path) as archive:
        assert archive.read("artifacts/released.pdf") == b"%PDF-export"

    dump = tmp_path / "payload.dump"
    dump.write_bytes(b"PGDUMP")
    with pytest.raises(ExportError, match="backup dump"):
        create_portability_export(
            records=[_portability_record()],
            released_artifacts=[
                (
                    {
                        "artifact_id": "art-2",
                        "file_name": "payload.dump",
                        "media_type": "application/octet-stream",
                        "size_bytes": 5,
                        "checksum_sha256": hashlib.sha256(b"PGDUMP").hexdigest(),
                        "released": True,
                    },
                    dump,
                )
            ],
            output_dir=tmp_path / "out2",
        )


def test_unreleased_artifact_is_rejected(tmp_path: Path) -> None:
    artifact = tmp_path / "draft.bin"
    artifact.write_bytes(b"draft")
    with pytest.raises(ExportError, match="released=true"):
        create_portability_export(
            records=[_portability_record()],
            released_artifacts=[
                (
                    {
                        "artifact_id": "art-3",
                        "file_name": "draft.bin",
                        "media_type": "application/octet-stream",
                        "size_bytes": 5,
                        "checksum_sha256": hashlib.sha256(b"draft").hexdigest(),
                        "released": False,
                    },
                    artifact,
                )
            ],
            output_dir=tmp_path,
        )


def test_cli_evidence_requires_explicit_audit_file(tmp_path: Path) -> None:
    from argparse import Namespace

    from interfaces.cli.commands import ops_commands

    args = Namespace(export_kind="evidence", audit_file=None, output_dir=str(tmp_path))
    assert ops_commands.cmd_ops_export(args) == 1


@pytest.mark.parametrize(
    "secret_value",
    [
        "postgresql://u:p@127.0.0.1:5432/db",
        "-----BEGIN PRIVATE KEY-----abc",
        "$2b$12$notahashbutmarker",
        "session=abc123",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaa",
    ],
)
def test_secret_values_in_allowlisted_fields_fail_closed(
    tmp_path: Path, secret_value: str
) -> None:
    record = dict(_portability_record())
    record["title"] = secret_value
    with pytest.raises(ExportError, match="secret material"):
        create_portability_export(records=[record], output_dir=tmp_path)


def test_cli_portability_and_evidence_adapters(tmp_path: Path) -> None:
    from argparse import Namespace

    from interfaces.cli.commands import ops_commands

    records_path = tmp_path / "records.json"
    records_path.write_text(json.dumps([_portability_record()]), encoding="utf-8")
    out = tmp_path / "exports"
    out.mkdir()
    port_args = Namespace(
        export_kind="portability",
        records_file=str(records_path),
        output_dir=str(out),
    )
    assert ops_commands.cmd_ops_export(port_args) == 0
    zips = list(out.glob("portability-*.zip"))
    assert len(zips) == 1

    audit_path = tmp_path / "audit-records.jsonl"
    audit_path.write_text(json.dumps(_evidence_record()) + "\n", encoding="utf-8")
    evidence_args = Namespace(
        export_kind="evidence",
        audit_file=str(audit_path),
        output_dir=str(out),
    )
    assert ops_commands.cmd_ops_export(evidence_args) == 0
    assert list(out.glob("evidence-*.zip"))


def test_evidence_export_rejects_bearer_in_allowlisted_fields(tmp_path: Path) -> None:
    from qm_platform.export.exporter import _SECRET_VALUE_MARKERS

    assert "pwd=" not in _SECRET_VALUE_MARKERS
    record = dict(_evidence_record())
    record["reason"] = "Authorization: Bearer leak-token-abc"
    with pytest.raises(ExportError, match="secret material"):
        create_evidence_export(audit_records=[record], output_dir=tmp_path)
    assert list(tmp_path.glob("evidence-*.zip")) == []

    record = dict(_evidence_record())
    record["reason"] = "Bearer leak-token-abc"
    with pytest.raises(ExportError, match="secret material"):
        create_evidence_export(audit_records=[record], output_dir=tmp_path)
    assert list(tmp_path.glob("evidence-*.zip")) == []

    record = dict(_evidence_record())
    record["reason"] = "pwd=live-secret"
    with pytest.raises(ExportError, match="secret material"):
        create_evidence_export(audit_records=[record], output_dir=tmp_path)
    assert list(tmp_path.glob("evidence-*.zip")) == []

    record = dict(_evidence_record())
    record["reason"] = "pwd: live-secret"
    with pytest.raises(ExportError, match="secret material"):
        create_evidence_export(audit_records=[record], output_dir=tmp_path)
    assert list(tmp_path.glob("evidence-*.zip")) == []

    record = dict(_evidence_record())
    record["reason"] = "Authorization: Basic dXNlcjpwYXNz"
    with pytest.raises(ExportError, match="secret material"):
        create_evidence_export(audit_records=[record], output_dir=tmp_path)
    assert list(tmp_path.glob("evidence-*.zip")) == []

    record = dict(_evidence_record())
    record["reason"] = "Basic dXNlcjpwYXNz"
    with pytest.raises(ExportError, match="secret material"):
        create_evidence_export(audit_records=[record], output_dir=tmp_path)
    assert list(tmp_path.glob("evidence-*.zip")) == []


def test_duplicate_artifact_zip_member_names_are_rejected(tmp_path: Path) -> None:
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    meta = {
        "artifact_id": "art-dup-1",
        "file_name": "same.bin",
        "media_type": "application/octet-stream",
        "size_bytes": 3,
        "checksum_sha256": hashlib.sha256(b"one").hexdigest(),
        "released": True,
    }
    meta_two = dict(meta)
    meta_two["artifact_id"] = "art-dup-2"
    meta_two["checksum_sha256"] = hashlib.sha256(b"two").hexdigest()
    with pytest.raises(ExportError, match="duplicate artifact file_name"):
        create_portability_export(
            records=[_portability_record()],
            released_artifacts=[(meta, first), (meta_two, second)],
            output_dir=tmp_path / "out-dup",
        )
    assert list((tmp_path / "out-dup").glob("*.zip")) == []

    meta_case = dict(meta)
    meta_case["file_name"] = "Same.BIN"
    meta_case["artifact_id"] = "art-dup-3"
    same_case = tmp_path / "c.bin"
    same_case.write_bytes(b"one")
    with pytest.raises(ExportError, match="duplicate artifact file_name"):
        create_portability_export(
            records=[_portability_record()],
            released_artifacts=[(meta, first), (meta_case, same_case)],
            output_dir=tmp_path / "out-case",
        )
    assert list((tmp_path / "out-case").glob("*.zip")) == []


def test_unique_released_artifacts_still_export(tmp_path: Path) -> None:
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    result = create_portability_export(
        records=[_portability_record()],
        released_artifacts=[
            (
                {
                    "artifact_id": "art-1",
                    "file_name": "one.bin",
                    "media_type": "application/octet-stream",
                    "size_bytes": 3,
                    "checksum_sha256": hashlib.sha256(b"one").hexdigest(),
                    "released": True,
                },
                first,
            ),
            (
                {
                    "artifact_id": "art-2",
                    "file_name": "two.bin",
                    "media_type": "application/octet-stream",
                    "size_bytes": 3,
                    "checksum_sha256": hashlib.sha256(b"two").hexdigest(),
                    "released": True,
                },
                second,
            ),
        ],
        output_dir=tmp_path / "out-unique",
    )
    with zipfile.ZipFile(result.archive_path) as archive:
        assert archive.read("artifacts/one.bin") == b"one"
        assert archive.read("artifacts/two.bin") == b"two"
