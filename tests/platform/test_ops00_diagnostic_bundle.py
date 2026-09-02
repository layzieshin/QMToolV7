"""Static checks for OPS00-F secret-redacted diagnostic bundles."""
from __future__ import annotations

import json
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest

from qm_platform.audit.redaction import redact_audit_details
from qm_platform.logging import diagnostic_bundle as diagnostic_bundle_mod
from qm_platform.logging.diagnostic_bundle import (
    DIAGNOSTIC_SCHEMA_ID,
    DiagnosticBundleError,
    create_diagnostic_bundle,
)
from qm_platform.runtime.paths import resolve_home_path
from interfaces.cli.commands import ops_commands
from interfaces.cli.main import _build_parser


def _home_with_logs(tmp_path: Path, *, secret_line: str | None = None) -> Path:
    logs = resolve_home_path(tmp_path, "storage/platform/logs")
    logs.mkdir(parents=True, exist_ok=True)
    resolve_home_path(tmp_path, "storage/platform/blobs").mkdir(parents=True, exist_ok=True)
    clean = json.dumps({"timestamp_utc": "2026-09-01T00:00:00+00:00", "message": "ok"}, ensure_ascii=True)
    platform_lines = [clean]
    if secret_line is not None:
        platform_lines.append(secret_line)
    (logs / "platform.log").write_text("\n".join(platform_lines) + "\n", encoding="utf-8")
    (logs / "audit.log").write_text(clean + "\n", encoding="utf-8")
    return tmp_path


def test_diagnostic_zip_is_not_backup_or_export(tmp_path: Path) -> None:
    home = _home_with_logs(tmp_path)
    result = create_diagnostic_bundle(output_dir=tmp_path / "out", app_home=home, postgres_dsn=None)
    assert result.schema_id == DIAGNOSTIC_SCHEMA_ID
    with zipfile.ZipFile(result.archive_path) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "checksums.json" in names
        assert "ready.json" in names
        assert "config-keys.json" in names
        assert "logs/platform.log.jsonl" in names
        assert "database.dump" not in names
        assert "data.json" not in names
        assert "audit.jsonl" not in names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["schema_id"] == DIAGNOSTIC_SCHEMA_ID
        assert manifest["kind"] == "diagnostic"
        checksums = json.loads(archive.read("checksums.json"))
        ready = archive.read("ready.json")
        assert checksums["ready.json"] == __import__("hashlib").sha256(ready).hexdigest()
        ready_payload = json.loads(ready)
        assert ready_payload["ready"] is False
        assert ready_payload["checks"]["postgres"] == "missing_dsn"


def test_diagnostic_redacts_secret_log_lines_without_truncating_source(tmp_path: Path) -> None:
    secret = json.dumps(
        {
            "timestamp_utc": "2026-09-01T00:00:01+00:00",
            "message": "postgresql://u:p@127.0.0.1:5432/db",
        },
        ensure_ascii=True,
    )
    home = _home_with_logs(tmp_path, secret_line=secret)
    original = (resolve_home_path(home, "storage/platform/logs/platform.log")).read_text(encoding="utf-8")
    result = create_diagnostic_bundle(output_dir=tmp_path / "out", app_home=home, postgres_dsn=None)
    after = (resolve_home_path(home, "storage/platform/logs/platform.log")).read_text(encoding="utf-8")
    assert after == original
    with zipfile.ZipFile(result.archive_path) as archive:
        body = archive.read("logs/platform.log.jsonl").decode("utf-8")
        assert "postgresql://u:p@" not in body.casefold()
        assert "<redacted>" in body
        assert '"message": "ok"' in body


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("password", "hunter2-should-not-leak"),
        ("api_key", "key-should-not-leak"),
        ("session_token", "sess-should-not-leak"),
        ("dsn", "postgresql://host-should-not-leak@127.0.0.1/db"),
        ("private_key", "pem-should-not-leak"),
        ("apiKey", "camel-api-key-must-not-leak"),
        ("sessionToken", "camel-session-must-not-leak"),
        ("privateKey", "camel-private-must-not-leak"),
    ],
)
def test_json_secret_fields_are_redacted_from_diagnostic_zip(
    tmp_path: Path, field: str, value: str
) -> None:
    secret = json.dumps(
        {
            "timestamp_utc": "2026-09-01T00:00:02+00:00",
            "message": "login",
            field: value,
        },
        ensure_ascii=True,
    )
    home = _home_with_logs(tmp_path, secret_line=secret)
    original = resolve_home_path(home, "storage/platform/logs/platform.log").read_text(encoding="utf-8")
    result = create_diagnostic_bundle(output_dir=tmp_path / "out", app_home=home, postgres_dsn=None)
    after = resolve_home_path(home, "storage/platform/logs/platform.log").read_text(encoding="utf-8")
    assert after == original
    with zipfile.ZipFile(result.archive_path) as archive:
        body = archive.read("logs/platform.log.jsonl").decode("utf-8")
        assert value not in body
        assert "<redacted>" in body


def test_nested_json_secret_field_is_redacted(tmp_path: Path) -> None:
    secret = json.dumps(
        {
            "timestamp_utc": "2026-09-01T00:00:03+00:00",
            "nested": {"api_key": "nested-secret-must-not-leak"},
        },
        ensure_ascii=True,
    )
    home = _home_with_logs(tmp_path, secret_line=secret)
    result = create_diagnostic_bundle(output_dir=tmp_path / "out", app_home=home, postgres_dsn=None)
    with zipfile.ZipFile(result.archive_path) as archive:
        body = archive.read("logs/platform.log.jsonl").decode("utf-8")
        assert "nested-secret-must-not-leak" not in body
        assert "<redacted>" in body


def test_config_keys_are_presence_booleans_not_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QMTOOL_PG_PASSWORD", "should-never-appear")
    monkeypatch.setenv("QMTOOL_PG_DSN", "postgresql://u:p@127.0.0.1:5432/db")
    home = _home_with_logs(tmp_path)
    result = create_diagnostic_bundle(output_dir=tmp_path / "out", app_home=home, postgres_dsn=None)
    with zipfile.ZipFile(result.archive_path) as archive:
        payload = json.loads(archive.read("config-keys.json"))
        present = payload["keys_present"]
        assert present["QMTOOL_PG_PASSWORD"] is True
        assert present["QMTOOL_PG_DSN"] is True
        raw = archive.read("config-keys.json").decode("utf-8")
        assert "should-never-appear" not in raw
        assert "postgresql://" not in raw.casefold()


def test_forbidden_dump_and_pem_members_are_rejected() -> None:
    from qm_platform.logging.diagnostic_bundle import _reject_forbidden_names

    with pytest.raises(DiagnosticBundleError, match="forbidden diagnostic member"):
        _reject_forbidden_names({"database.dump"})
    with pytest.raises(DiagnosticBundleError, match="forbidden diagnostic member"):
        _reject_forbidden_names({"certs/tls.pem"})
    with pytest.raises(DiagnosticBundleError, match="forbidden diagnostic member"):
        _reject_forbidden_names({"license.json"})


def test_cli_diagnostic_bundle_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.bootstrap import BackendBootstrapError

    home = _home_with_logs(tmp_path)
    monkeypatch.setenv("QMTOOL_HOME", str(home))

    def _missing_dsn() -> str:
        raise BackendBootstrapError("dsn missing")

    monkeypatch.setattr(
        "interfaces.cli.commands.ops_commands.resolve_usermanagement_postgres_dsn",
        _missing_dsn,
    )
    out = tmp_path / "diag"
    args = Namespace(output_dir=str(out))
    assert ops_commands.cmd_ops_diagnostic_bundle(args) == 0
    assert list(out.glob("diagnostic-*.zip"))


def test_ops_diagnostic_bundle_parser_is_registered() -> None:
    parser = _build_parser()
    args = parser.parse_args(["ops", "diagnostic-bundle", "--output-dir", "out"])
    assert args.ops_command == "diagnostic-bundle"
    assert args.output_dir == "out"


@pytest.mark.parametrize(
    "secret_line",
    [
        json.dumps({"Authorization": "Bearer leak-token-abc"}, ensure_ascii=True),
        json.dumps({"authorization": "Bearer leak-token-abc"}, ensure_ascii=True),
        json.dumps({"nested": {"Authorization": "Bearer leak-token-abc"}}, ensure_ascii=True),
        json.dumps({"message": "Authorization: Bearer leak-token-abc"}, ensure_ascii=True),
        json.dumps({"note": "Bearer leak-token-abc"}, ensure_ascii=True),
        "plain Authorization: Bearer leak-token-abc",
        "BEARER leak-token-abc leftover",
        json.dumps({"message": "Authorization: Basic dXNlcjpwYXNz"}, ensure_ascii=True),
        json.dumps({"Authorization": "Basic dXNlcjpwYXNz"}, ensure_ascii=True),
        json.dumps({"note": "Basic dXNlcjpwYXNz"}, ensure_ascii=True),
        "plain Authorization: Basic dXNlcjpwYXNz",
        "plain Basic dXNlcjpwYXNz leftover",
        "BASIC dXNlcjpwYXNz leftover",
        json.dumps({"pwd": "pwd-json-secret"}, ensure_ascii=True),
        json.dumps({"note": "pwd=live-secret"}, ensure_ascii=True),
        "plain pwd: live-secret leftover",
    ],
)
def test_diagnostic_redacts_bearer_tokens_via_canonical_owner(
    tmp_path: Path, secret_line: str
) -> None:
    home = _home_with_logs(tmp_path, secret_line=secret_line)
    original = resolve_home_path(home, "storage/platform/logs/platform.log").read_text(
        encoding="utf-8"
    )
    result = create_diagnostic_bundle(output_dir=tmp_path / "out", app_home=home, postgres_dsn=None)
    after = resolve_home_path(home, "storage/platform/logs/platform.log").read_text(encoding="utf-8")
    assert after == original
    with zipfile.ZipFile(result.archive_path) as archive:
        body = b"".join(archive.read(name) for name in archive.namelist()).decode("utf-8")
        assert "leak-token-abc" not in body
        assert "Bearer leak-token-abc" not in body
        assert "dXNlcjpwYXNz" not in body
        assert "Basic dXNlcjpwYXNz" not in body
        assert "pwd-json-secret" not in body
        assert "live-secret" not in body


def test_diagnostic_http_redaction_uses_canonical_owner_not_local_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not hasattr(diagnostic_bundle_mod, "_consume_remaining_http_credentials")
    calls: list[object] = []

    def _spy(value: object) -> object:
        calls.append(value)
        return redact_audit_details(value)

    monkeypatch.setattr(diagnostic_bundle_mod, "redact_audit_details", _spy)
    json_line = json.dumps({"message": "Authorization: Basic dXNlcjpwYXNz"}, ensure_ascii=True)
    home = _home_with_logs(tmp_path, secret_line=json_line)
    audit_path = resolve_home_path(home, "storage/platform/logs/audit.log")
    audit_path.write_text("plain Bearer leak-token-abc leftover\n", encoding="utf-8")
    original_platform = resolve_home_path(home, "storage/platform/logs/platform.log").read_text(
        encoding="utf-8"
    )
    original_audit = audit_path.read_text(encoding="utf-8")
    result = create_diagnostic_bundle(output_dir=tmp_path / "out", app_home=home, postgres_dsn=None)
    assert resolve_home_path(home, "storage/platform/logs/platform.log").read_text(
        encoding="utf-8"
    ) == original_platform
    assert audit_path.read_text(encoding="utf-8") == original_audit
    assert calls, "canonical redact_audit_details must be used"
    with zipfile.ZipFile(result.archive_path) as archive:
        body = b"".join(archive.read(name) for name in archive.namelist()).decode("utf-8")
        assert "dXNlcjpwYXNz" not in body
        assert "leak-token-abc" not in body
        assert "<redacted>" in body


@pytest.mark.parametrize(
    ("secret_line", "secret"),
    [
        (
            json.dumps({"note": 'pass="diagnostic pass with spaces"'}, ensure_ascii=True),
            "diagnostic pass with spaces",
        ),
        (
            json.dumps({"client_api_key": "compound client secret"}, ensure_ascii=True),
            "compound client secret",
        ),
        (
            json.dumps({"db.password": "namespaced db secret"}, ensure_ascii=True),
            "namespaced db secret",
        ),
        (
            json.dumps({"auth/api_key": "namespaced api secret"}, ensure_ascii=True),
            "namespaced api secret",
        ),
        (
            json.dumps({"note": "message=token=nested diagnostic secret"}, ensure_ascii=True),
            "nested diagnostic secret",
        ),
        (
            json.dumps(
                {"url": "https://host/path?token=query-diagnostic-secret"},
                ensure_ascii=True,
            ),
            "query-diagnostic-secret",
        ),
        ("plain tls_private_key='tls private material'", "tls private material"),
    ],
)
def test_diagnostic_consumes_pass_quoted_values_and_compound_aliases(
    tmp_path: Path, secret_line: str, secret: str
) -> None:
    home = _home_with_logs(tmp_path, secret_line=secret_line)
    result = create_diagnostic_bundle(output_dir=tmp_path / "out", app_home=home, postgres_dsn=None)
    with zipfile.ZipFile(result.archive_path) as archive:
        body = b"".join(archive.read(name) for name in archive.namelist()).decode("utf-8")
        assert secret not in body
        assert "<redacted>" in body


@pytest.mark.parametrize(
    "payload",
    [
        b'pass="raw pass with spaces"',
        b'{"client_api_key": "raw compound secret"}',
        b'{"operator.pass": "raw namespaced secret"}',
        b'{"note": "message=token=raw nested secret"}',
        b'{"url": "https://host/path?token=raw-query-secret"}',
        b"-----BEGIN PRIVATE KEY-----",
        b"$argon2id$raw-hash-material",
        b"eyJhbGciOiJIUzI1NiJ9.raw-signature.payload",
    ],
)
def test_diagnostic_rejects_remaining_secret_markers(payload: bytes) -> None:
    with pytest.raises(DiagnosticBundleError, match="secret material remains"):
        diagnostic_bundle_mod._reject_secret_bytes(payload, field="logs/platform.log.jsonl")


def test_diagnostic_secret_guard_accepts_canonically_redacted_values() -> None:
    diagnostic_bundle_mod._reject_secret_bytes(
        b'{"password": "<redacted>", "client_api_key": "<redacted>"}',
        field="logs/platform.log.jsonl",
    )
