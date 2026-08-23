"""Live PostgreSQL repository tests for AP-029 PG01-B registry."""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

from modules.registry import postgres_schema as registry_schema
from modules.registry.contracts import RegisterState, ReleaseEvidenceMode, RegistryEntry
from modules.registry.postgres_connection import PostgresRepositoryError
from modules.registry.postgres_repository import PostgresRegistryRepository
from modules.registry.service import RegistryService
from modules.registry.sqlite_repository import SQLiteRegistryRepository
from qm_platform.events.event_envelope import EventEnvelope

from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres


@pytest.fixture
def registry_repository(live_postgres_env: LivePostgresEnv) -> PostgresRegistryRepository:
    registry_schema.provision_registry_schema(live_postgres_env.admin_dsn)
    registry_schema.migrate_registry_schema(live_postgres_env.migrator_dsn)
    repository = PostgresRegistryRepository(live_postgres_env.runtime_dsn)
    yield repository
    with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS registry CASCADE")


def _sample_entry(document_id: str = "DOC-PG-1") -> RegistryEntry:
    moment = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    return RegistryEntry(
        document_id=document_id,
        active_version=2,
        release_note="approved via workflow",
        release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
        register_state=RegisterState.VALID,
        is_findable=True,
        valid_from=moment,
        valid_until=None,
        last_update_event_id="evt-pg-1",
        last_update_at=moment,
    )


def test_postgres_registry_repository_crud_roundtrip(registry_repository: PostgresRegistryRepository) -> None:
    entry = _sample_entry()
    registry_repository.upsert(entry)
    loaded = registry_repository.get("DOC-PG-1")
    assert loaded == entry
    assert registry_repository.list_entries() == [entry]

    updated = RegistryEntry(
        document_id="DOC-PG-1",
        active_version=3,
        release_note="updated note",
        release_evidence_mode=ReleaseEvidenceMode.REGISTRY_NOTE,
        register_state=RegisterState.IN_REVIEW,
        is_findable=True,
        valid_from=entry.valid_from,
        valid_until=entry.valid_until,
        last_update_event_id="evt-pg-2",
        last_update_at=datetime(2024, 6, 2, 12, 0, tzinfo=timezone.utc),
    )
    registry_repository.upsert(updated)
    assert registry_repository.get("DOC-PG-1") == updated


def test_postgres_registry_service_replay_matches_sqlite_reference(
    registry_repository: PostgresRegistryRepository,
) -> None:
    evt = EventEnvelope(
        event_id="recovery-replay-pg",
        name="domain.documents.state.replay.v1",
        occurred_at_utc="2024-06-01T10:00:00+00:00",
        correlation_id="corr-pg",
        causation_id=None,
        actor_user_id="system",
        module_id="documents",
        payload={"document_id": "DOC-R-PG", "version": 2},
    )
    pg_service = RegistryService(registry_repository)
    with tempfile.TemporaryDirectory() as tmp:
        sqlite_service = RegistryService(SQLiteRegistryRepository(Path(tmp) / "registry.db"))
        pg_result = pg_service.apply_documents_state(
            document_id="DOC-R-PG",
            version=2,
            status="APPROVED",
            release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
            event=evt,
        )
        sqlite_result = sqlite_service.apply_documents_state(
            document_id="DOC-R-PG",
            version=2,
            status="APPROVED",
            release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
            event=evt,
        )
        assert pg_result == sqlite_result


def test_postgres_registry_repository_rejects_migrator_login(
    live_postgres_env: LivePostgresEnv,
) -> None:
    registry_schema.provision_registry_schema(live_postgres_env.admin_dsn)
    registry_schema.migrate_registry_schema(live_postgres_env.migrator_dsn)
    repository = PostgresRegistryRepository(live_postgres_env.migrator_dsn)
    try:
        with pytest.raises(PostgresRepositoryError):
            repository.list_entries()
    finally:
        with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS registry CASCADE")
