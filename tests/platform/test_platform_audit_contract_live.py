"""Live PostgreSQL checks for AP-029 PG00-C platform audit contract."""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg
import pytest

from qm_platform.audit import (
    ACTOR_ANONYMOUS,
    ACTOR_SYSTEM,
    PlatformAuditEventWrite,
    PlatformAuditWriter,
    RESULT_SUCCEEDED,
)
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from qm_platform.persistence import postgres_schema as pgs
from tests.platform.test_postgres_schema_live import _prepare_platform_schema
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres


def _read_audits(migrator_dsn: str) -> list[dict]:
    with psycopg.connect(migrator_dsn, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(f"SET ROLE {pgs.MIGRATOR_ROLE}")
        rows = conn.execute(
            """
            SELECT audit_id::text AS audit_id,
                   organization_id,
                   request_id,
                   correlation_id,
                   actor_kind,
                   actor_user_id::text AS actor_user_id,
                   actor_label,
                   action,
                   object_type,
                   object_id,
                   result,
                   reason_code,
                   details_json
            FROM platform.audit_events
            ORDER BY occurred_at, audit_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


@pytest.fixture
def platform_env(live_postgres_env: LivePostgresEnv) -> LivePostgresEnv:
    _prepare_platform_schema(live_postgres_env)
    pgs.migrate_platform_schema(live_postgres_env.migrator_dsn)
    yield live_postgres_env


def test_runtime_can_insert_audit_but_not_read_or_mutate(platform_env: LivePostgresEnv) -> None:
    event = PlatformAuditEventWrite(
        action="platform.sample",
        object_type="platform.contract",
        object_id="sample-1",
        result=RESULT_SUCCEEDED,
        actor_kind=ACTOR_SYSTEM,
        actor_label="qmtool.platform-test",
        request_id="req-audit-1",
        correlation_id="corr-1",
        occurred_at=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        details={"password": "must-not-persist", "note": "visible"},
    )
    with psycopg.connect(platform_env.runtime_dsn) as runtime:
        runtime.execute("SET ROLE qmtool_runtime")
        audit_id = PlatformAuditWriter.insert_on_connection(runtime, event)
        runtime.commit()
        with pytest.raises(Exception):
            runtime.execute("SELECT COUNT(*) FROM platform.audit_events")
            runtime.commit()
        runtime.rollback()
        with pytest.raises(Exception):
            runtime.execute(
                "UPDATE platform.audit_events SET action='tampered' WHERE audit_id=%s::uuid",
                (audit_id,),
            )
            runtime.commit()
        runtime.rollback()
        with pytest.raises(Exception):
            runtime.execute(
                "DELETE FROM platform.audit_events WHERE audit_id=%s::uuid",
                (audit_id,),
            )
            runtime.commit()
        runtime.rollback()

    rows = _read_audits(platform_env.migrator_dsn)
    assert len(rows) == 1
    row = rows[0]
    assert row["audit_id"] == audit_id
    assert row["organization_id"] == INSTALLATION_ORGANIZATION_ID
    assert row["request_id"] == "req-audit-1"
    assert row["correlation_id"] == "corr-1"
    assert row["actor_kind"] == ACTOR_SYSTEM
    assert row["details_json"]["password"] == "<redacted>"
    assert row["details_json"]["note"] == "visible"


def test_anonymous_actor_form_is_enforced(platform_env: LivePostgresEnv) -> None:
    event = PlatformAuditEventWrite(
        action="platform.sample",
        object_type="platform.contract",
        object_id="sample-2",
        result=RESULT_SUCCEEDED,
        actor_kind=ACTOR_ANONYMOUS,
        request_id="req-audit-2",
    )
    with psycopg.connect(platform_env.runtime_dsn) as runtime:
        runtime.execute("SET ROLE qmtool_runtime")
        PlatformAuditWriter.insert_on_connection(runtime, event)
        runtime.commit()

    rows = _read_audits(platform_env.migrator_dsn)
    assert len(rows) == 1
    assert rows[0]["actor_kind"] == ACTOR_ANONYMOUS
    assert rows[0]["actor_user_id"] is None
    assert rows[0]["actor_label"] is None
