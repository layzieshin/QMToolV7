"""PostgreSQL backend Documents composition provenance (PG01 premerge R3)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import MappingProxyType

from modules.documents.bootstrap_provenance import DocumentsBootstrapProvenance
from modules.documents.postgres_repository import PostgresDocumentsRepository
from modules.documents.service import DocumentsService
from modules.documents.wiring import register_documents_ports
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.persistence.database_evolution import DATABASE_PREFLIGHT_STATUSES_PORT
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.testing import build_settings_service_for_tests

ROOT = Path(__file__).resolve().parents[2]


def _postgres_documents_container(root: Path) -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("logger", LoggerService(root / "logs.jsonl"))
    container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
    container.register_port("event_bus", EventBus())
    container.register_port("settings_service", build_settings_service_for_tests(root))
    container.register_port("app_home", root)
    container.register_port("resource_root", ROOT)
    container.register_port("documents_runtime_owner", "backend")
    container.register_port("documents_postgres_dsn", "postgresql://example.invalid/db")
    container.register_port("signature_api", object())
    container.register_port("registry_projection_api", object())
    # Real PG composition captures preflight for remaining SQLite DBs only — no documents key.
    container.register_port(DATABASE_PREFLIGHT_STATUSES_PORT, MappingProxyType({}))
    return container


def test_postgres_documents_wiring_does_not_use_sqlite_preflight_injection(monkeypatch) -> None:
    monkeypatch.setattr(
        "modules.documents.wiring.WorkflowProfileRelationalStore.ensure_seeded",
        lambda self, seed_reader: None,
    )
    with tempfile.TemporaryDirectory() as tmp:
        container = _postgres_documents_container(Path(tmp))
        statuses = container.get_port(DATABASE_PREFLIGHT_STATUSES_PORT)
        assert "documents" not in statuses
        register_documents_ports(container)
        service = container.get_port("documents_service")
        assert isinstance(service, DocumentsService)
        assert isinstance(service._repository, PostgresDocumentsRepository)
        assert service._profile_store._bootstrap_provenance == DocumentsBootstrapProvenance.POST_J03_SCHEMA
