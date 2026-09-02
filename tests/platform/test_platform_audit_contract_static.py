"""Static checks for AP-029 PG00-C platform append-only audit contract."""
from __future__ import annotations

import json
import inspect
from pathlib import Path

import pytest
import qm_platform.audit.redaction as redaction_module

from qm_platform.audit import (
    ACTOR_ANONYMOUS,
    ACTOR_SYSTEM,
    ACTOR_USER,
    PlatformAuditEventWrite,
    PlatformAuditWriteError,
    PlatformAuditWriter,
    RESULT_SUCCEEDED,
    redact_audit_details,
)
from qm_platform.audit.postgres_writer import _json_details
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from qm_platform.persistence import postgres_schema as pgs

ROOT = Path(__file__).resolve().parents[2]


def test_migration_chain_includes_audit_events() -> None:
    steps = pgs.discover_migrations()
    assert [step.name for step in steps] == [
        "platform_settings",
        "platform_settings_integrity",
        "organization",
        "audit_events",
        "blob_artifacts",
        "blob_backup_set_org_fk",
    ]
    assert steps[3].version == 4
    assert steps[3].name == "audit_events"
    assert len(steps[3].checksum) == 64


def test_audit_migration_grants_insert_only_to_runtime() -> None:
    sql = (
        pgs.MIGRATIONS_DIR / "0004_audit_events.sql"
    ).read_text(encoding="utf-8").lower()
    assert "create table platform.audit_events" in sql
    assert "organization_id" in sql
    assert "request_id" in sql
    assert "correlation_id" in sql
    assert "details_json" in sql
    assert "grant insert on table platform.audit_events to qmtool_runtime" in sql
    assert "grant select" not in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql


def test_packaging_includes_audit_events_migration() -> None:
    text = (ROOT / "packaging/build_onedir.py").read_text(encoding="utf-8")
    assert "qm_platform/persistence/postgres/migrations/0004_audit_events.sql" in text


def test_redact_audit_details_strips_secret_keys_and_inline_material() -> None:
    payload = {
        "password": "ops-secret-1",
        "nested": {"session_token": "abc123", "note": "ok"},
        "sessionToken": "raw-session-token",
        "authorization": "Bearer eyJ.token",
        "message": "postgresql://user:secret@host/db",
    }
    redacted = redact_audit_details(payload)
    assert redacted["password"] == "<redacted>"
    assert redacted["nested"]["session_token"] == "<redacted>"
    assert redacted["nested"]["note"] == "ok"
    assert redacted["sessionToken"] == "<redacted>"
    assert redacted["authorization"] == "<redacted>"
    assert redacted["message"] == "postgresql://<redacted>"


def test_json_details_never_serializes_camel_case_session_token() -> None:
    encoded = _json_details({"sessionToken": "must-not-persist", "action": "sample"})
    assert encoded is not None
    parsed = json.loads(encoded)
    assert parsed["sessionToken"] == "<redacted>"
    assert parsed["action"] == "sample"


def test_json_details_never_serializes_inline_secrets_under_neutral_keys() -> None:
    encoded = _json_details(
        {
            "note": "token=secret-value",
            "message": "private_key=abc123",
            "detail": "sessionToken: raw-token",
        }
    )
    assert encoded is not None
    parsed = json.loads(encoded)
    assert parsed["note"] == "token=<redacted>"
    assert parsed["message"] == "private_key=<redacted>"
    assert parsed["detail"] == "sessionToken: <redacted>"


def test_json_details_never_serializes_raw_secrets() -> None:
    encoded = _json_details({"password": "hidden", "action": "sample"})
    assert encoded is not None
    parsed = json.loads(encoded)
    assert parsed["password"] == "<redacted>"
    assert parsed["action"] == "sample"


def test_blank_request_id_is_an_audit_failure_before_sql() -> None:
    class _NoSqlConnection:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("request-id validation must run before SQL")

    event = PlatformAuditEventWrite(
        action="platform.sample",
        object_type="platform.sample",
        object_id="sample-1",
        result=RESULT_SUCCEEDED,
        actor_kind=ACTOR_ANONYMOUS,
        request_id="  ",
    )
    with pytest.raises(PlatformAuditWriteError):
        PlatformAuditWriter.insert_on_connection(_NoSqlConnection(), event)


def test_organization_spoof_is_rejected_before_sql() -> None:
    class _NoSqlConnection:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("organization validation must run before SQL")

    event = PlatformAuditEventWrite(
        action="platform.sample",
        object_type="platform.sample",
        object_id="sample-1",
        result=RESULT_SUCCEEDED,
        actor_kind=ACTOR_USER,
        actor_user_id="00000000-0000-4000-8000-000000000099",
        request_id="req-1",
        organization_id="00000000-0000-4000-8000-000000009999",
    )
    with pytest.raises(PlatformAuditWriteError):
        PlatformAuditWriter.insert_on_connection(_NoSqlConnection(), event)


def test_resolved_organization_id_defaults_to_installation() -> None:
    event = PlatformAuditEventWrite(
        action="platform.sample",
        object_type="platform.sample",
        object_id="sample-1",
        result=RESULT_SUCCEEDED,
        actor_kind=ACTOR_SYSTEM,
        actor_label="qmtool.sample",
        request_id="req-1",
    )
    assert event.resolved_organization_id() == INSTALLATION_ORGANIZATION_ID


def test_actor_kinds_are_exported() -> None:
    assert ACTOR_USER == "user"
    assert ACTOR_SYSTEM == "system"
    assert ACTOR_ANONYMOUS == "anonymous"


def test_redact_audit_details_consumes_basic_authorization_credentials() -> None:
    payload = {
        "Authorization": "Basic dXNlcjpwYXNz",
        "authorization": "BASIC dXNlcjpwYXNz",
        "nested": {"Authorization": "basic dXNlcjpwYXNz"},
        "header": "Authorization: Basic dXNlcjpwYXNz",
        "header_case": "AUTHORIZATION: BASIC dXNlcjpwYXNz",
        "scheme_only": "Basic dXNlcjpwYXNz",
        "scheme_case": "BASIC dXNlcjpwYXNz",
        "note": "ok",
    }
    redacted = redact_audit_details(payload)
    dumped = json.dumps(redacted)
    assert "dXNlcjpwYXNz" not in dumped
    assert redacted["Authorization"] == "<redacted>"
    assert redacted["authorization"] == "<redacted>"
    assert redacted["nested"]["Authorization"] == "<redacted>"
    assert "dXNlcjpwYXNz" not in str(redacted["header"])
    assert "<redacted>" in str(redacted["header"])
    assert "dXNlcjpwYXNz" not in str(redacted["header_case"])
    assert redacted["scheme_only"] == "Basic <redacted>"
    assert "dXNlcjpwYXNz" not in str(redacted["scheme_case"])
    assert redacted["note"] == "ok"
    assert redact_audit_details("Authorization: Basic dXNlcjpwYXNz").find("dXNlcjpwYXNz") == -1
    assert redact_audit_details("Basic dXNlcjpwYXNz") == "Basic <redacted>"


def test_redact_audit_details_treats_pwd_as_secret_alias() -> None:
    payload = {
        "pwd": "json-key-secret",
        "PWD": "json-key-secret-case",
        "nested": {"pwd": "nested-pwd-secret"},
        "note": "pwd=inline-equals-secret",
        "detail": "pwd: inline-colon-secret",
        "case": "PWD=inline-equals-case",
        "colon_case": "Pwd: inline-colon-case",
        "ok": "visible",
    }
    redacted = redact_audit_details(payload)
    dumped = json.dumps(redacted)
    assert "json-key-secret" not in dumped
    assert "nested-pwd-secret" not in dumped
    assert "inline-equals-secret" not in dumped
    assert "inline-colon-secret" not in dumped
    assert "inline-equals-case" not in dumped
    assert "inline-colon-case" not in dumped
    assert redacted["pwd"] == "<redacted>"
    assert redacted["PWD"] == "<redacted>"
    assert redacted["nested"]["pwd"] == "<redacted>"
    assert redacted["note"] == "pwd=<redacted>"
    assert redacted["detail"] == "pwd: <redacted>"
    assert redacted["ok"] == "visible"


def test_redact_audit_details_keeps_existing_bearer_password_and_token_behavior() -> None:
    payload = {
        "password": "ops-secret-1",
        "nested": {"session_token": "abc123", "note": "ok"},
        "authorization": "Bearer eyJ.token",
        "message": "postgresql://user:secret@host/db",
        "note": "Bearer eyJ.token",
        "detail": "token=secret-value",
    }
    redacted = redact_audit_details(payload)
    assert redacted["password"] == "<redacted>"
    assert redacted["nested"]["session_token"] == "<redacted>"
    assert redacted["nested"]["note"] == "ok"
    assert redacted["authorization"] == "<redacted>"
    assert redacted["message"] == "postgresql://<redacted>"
    assert redacted["note"] == "Bearer <redacted>"
    assert redacted["detail"] == "token=<redacted>"
    assert redact_audit_details("Bearer eyJ.token") == "Bearer <redacted>"


@pytest.mark.parametrize(
    ("raw", "secret", "expected"),
    [
        ("pass=inline-secret", "inline-secret", "pass=<redacted>"),
        (
            "pass: 'secret value with spaces'",
            "secret value with spaces",
            "pass: '<redacted>'",
        ),
        (
            'password="quoted password with spaces"',
            "quoted password with spaces",
            'password="<redacted>"',
        ),
        (
            'client_api_key = "client key with spaces"',
            "client key with spaces",
            'client_api_key = "<redacted>"',
        ),
        (
            "tls_private_key='private key phrase'",
            "private key phrase",
            "tls_private_key='<redacted>'",
        ),
        (
            'db.password="namespaced password"',
            "namespaced password",
            'db.password="<redacted>"',
        ),
        (
            "auth/api_key='namespaced api key'",
            "namespaced api key",
            "auth/api_key='<redacted>'",
        ),
        (
            "message=token=secret-value",
            "secret-value",
            "message=token=<redacted>",
        ),
        (
            "note: password=hunter2",
            "hunter2",
            "note: password=<redacted>",
        ),
        (
            "https://host/path?token=abc",
            "abc",
            "https://host/path?token=<redacted>",
        ),
        (
            'message="token=quoted-inner-secret"',
            "quoted-inner-secret",
            'message="token=<redacted>"',
        ),
    ],
)
def test_redact_audit_details_consumes_pass_and_complete_quoted_values(
    raw: str, secret: str, expected: str
) -> None:
    redacted = redact_audit_details(raw)
    assert secret not in redacted
    assert redacted == expected


def test_redact_audit_details_rejects_compound_secret_alias_keys() -> None:
    payload = {
        "client_api_key": "client-key-secret",
        "tls_private_key": "private-key-secret",
        "operatorPass": "operator-pass-secret",
        "db.password": "database-password-secret",
        "auth/api_key": "auth-api-secret",
        "operator.pass": "operator-password-secret",
        "compassion": "visible",
    }
    redacted = redact_audit_details(payload)
    assert redacted["client_api_key"] == "<redacted>"
    assert redacted["tls_private_key"] == "<redacted>"
    assert redacted["operatorPass"] == "<redacted>"
    assert redacted["db.password"] == "<redacted>"
    assert redacted["auth/api_key"] == "<redacted>"
    assert redacted["operator.pass"] == "<redacted>"
    assert redacted["compassion"] == "visible"


def test_inline_redaction_scans_only_secret_values_in_long_neutral_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_scan = redaction_module._inline_value_replacement
    scanned_values = 0

    def _tracked_scan(text: str, start: int) -> tuple[int, str]:
        nonlocal scanned_values
        scanned_values += 1
        return real_scan(text, start)

    monkeypatch.setattr(redaction_module, "_inline_value_replacement", _tracked_scan)
    neutral_prefix = "a=" * 12_000
    redacted = redact_audit_details(f"{neutral_prefix}token=tail-secret")
    assert redacted == f"{neutral_prefix}token=<redacted>"
    assert scanned_values == 1


def test_inline_redaction_scans_long_namespace_text_once_without_value_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probes = 0

    def _unexpected_value_probe(text: str, start: int) -> tuple[int, str]:
        nonlocal probes
        probes += 1
        return start, "<redacted>"

    monkeypatch.setattr(
        redaction_module,
        "_inline_value_replacement",
        _unexpected_value_probe,
    )
    raw = ("a/" * 12_000) + "a"
    assert redact_audit_details(raw) == raw
    assert probes == 0


def test_inline_redaction_applies_many_secret_replacements_in_one_forward_join() -> None:
    raw = "token=x " * 12_000
    redacted = redact_audit_details(raw)
    assert redacted == "token=<redacted> " * 12_000
    source = inspect.getsource(redaction_module._redact_inline_key_values)
    assert 'return "".join(parts)' in source
    assert "reversed(replacements)" not in source
