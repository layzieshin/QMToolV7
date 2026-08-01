"""AP-028 M7: static contracts for append-only PG audit evidence."""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.usermanagement import api as um_api
from modules.usermanagement import postgres_schema as pgs
from modules.usermanagement.errors import AuditUnavailableError
from modules.usermanagement.postgres_audit_repository import (
    ACTOR_ANONYMOUS,
    EVENT_LOGIN_DENIED,
    RESULT_DENIED,
    AuditEventWrite,
    PostgresAuditRepository,
)


ROOT = Path(__file__).resolve().parents[3]


def test_api_exports_login_logout_backend_and_audit_unavailable() -> None:
    assert "login_backend" in um_api.__all__
    assert "logout_backend" in um_api.__all__
    assert "AuditUnavailableError" in um_api.__all__
    assert callable(um_api.login_backend)
    assert callable(um_api.logout_backend)
    assert "create_backend_session" not in um_api.__all__
    assert "revoke_session" not in um_api.__all__
    assert not hasattr(um_api, "create_backend_session")
    assert not hasattr(um_api, "revoke_session")


def test_packaging_includes_audit_evidence_migration() -> None:
    text = (ROOT / "packaging/build_onedir.py").read_text(encoding="utf-8")
    assert "modules/usermanagement/postgres/migrations/0003_audit_evidence.sql" in text


def test_audit_repository_is_not_public_api_surface() -> None:
    text = (ROOT / "modules/usermanagement/api.py").read_text(encoding="utf-8")
    assert "postgres_audit_repository" in text
    assert "from .postgres_audit_repository" not in text
    assert "PostgresAuditRepository" not in um_api.__all__


def test_migration_chain_includes_audit_evidence() -> None:
    steps = pgs.discover_migrations()
    assert [step.version for step in steps] == [1, 2, 3]
    assert steps[2].name == "audit_evidence"
    assert len(steps[2].checksum) == 64


def test_blank_request_id_is_an_audit_failure_before_sql() -> None:
    class _NoSqlConnection:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("request-id validation must run before SQL")

    event = AuditEventWrite(
        event_type=EVENT_LOGIN_DENIED,
        result=RESULT_DENIED,
        actor_kind=ACTOR_ANONYMOUS,
        request_id="  ",
    )

    with pytest.raises(AuditUnavailableError):
        PostgresAuditRepository.insert_on_connection(_NoSqlConnection(), event)
