"""Focused Slot-2 live coverage for PostgreSQL Documents backend provenance.

Option 2: runtime never auto-seeds empty PG stock. Explicit seed uses the
public operator API. Composition uses build_backend_container().
"""
from __future__ import annotations

import pytest

import psycopg

from modules.documents import postgres_schema as documents_schema
from modules.documents.api import seed_postgres_workflow_profiles
from modules.documents.errors import ValidationError
from modules.registry import postgres_schema as registry_schema
from modules.signature import postgres_schema as signature_schema
from modules.usermanagement import postgres_schema as usermanagement_schema
from src.backend.bootstrap import build_backend_container
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres

_BOOTSTRAP_USER = "opsadmin"
_BOOTSTRAP_PASSWORD = "ops-secret-1"


@pytest.fixture
def backend_pg(tmp_path, monkeypatch, live_postgres_env: LivePostgresEnv):
    usermanagement_schema.migrate_usermanagement_schema(live_postgres_env.migrator_dsn)
    documents_schema.provision_documents_schema(live_postgres_env.admin_dsn)
    documents_schema.migrate_documents_schema(live_postgres_env.migrator_dsn)
    registry_schema.provision_registry_schema(live_postgres_env.admin_dsn)
    registry_schema.migrate_registry_schema(live_postgres_env.migrator_dsn)
    signature_schema.provision_signature_schema(live_postgres_env.admin_dsn)
    signature_schema.migrate_signature_schema(live_postgres_env.migrator_dsn)
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_LICENSE_MODE", "dev")
    monkeypatch.setenv("QMTOOL_PG_DSN", live_postgres_env.runtime_dsn)
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", _BOOTSTRAP_USER)
    monkeypatch.setenv("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", _BOOTSTRAP_PASSWORD)
    yield live_postgres_env
    with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS documents CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS registry CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS signature CASCADE")


def test_empty_postgres_documents_backend_does_not_autoseed(backend_pg) -> None:
    with pytest.raises(ValidationError, match="refusing silent re-seed"):
        build_backend_container()


def test_explicit_seed_then_restart_without_reseed(backend_pg) -> None:
    seed_postgres_workflow_profiles(backend_pg.runtime_dsn)
    first = build_backend_container()
    first_codes = {
        row["profile_code"]
        for row in first.get_port("documents_service")._profile_store.list_definitions()
    }
    second = build_backend_container()
    second_codes = {
        row["profile_code"]
        for row in second.get_port("documents_service")._profile_store.list_definitions()
    }
    assert first_codes == second_codes
    assert "long_release" in second_codes


def test_damaged_empty_postgres_profiles_are_not_reseeded(backend_pg) -> None:
    with psycopg.connect(backend_pg.runtime_dsn) as conn:
        conn.execute("SET search_path TO documents, public")
        conn.execute(
            """
            INSERT INTO workflow_profile_imports (
                import_id, source_path, source_kind, raw_sha256, semantic_sha256,
                import_classification, imported_at, report_json
            ) VALUES (
                'imp-residue', 'residue.json', 'bundled_seed',
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                'SEED', now(), '{}'
            )
            """
        )
        conn.commit()
    with pytest.raises(ValidationError, match="refusing silent re-seed"):
        seed_postgres_workflow_profiles(backend_pg.runtime_dsn)
    with pytest.raises(ValidationError, match="refusing silent re-seed"):
        build_backend_container()
