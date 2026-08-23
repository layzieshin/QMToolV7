"""Static (no PostgreSQL) checks for AP-029 PG01-C documents repository wiring."""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import MappingProxyType

from modules.documents.api import ensure_postgres_schema_ready
from modules.documents.postgres_repository import PostgresDocumentsRepository
from modules.documents.service import DocumentsService
from modules.documents.sqlite_repository import SQLiteDocumentsRepository
from modules.documents.wiring import register_documents_ports
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.persistence.database_evolution import (
    DATABASE_PREFLIGHT_STATUSES_PORT,
    DatabaseStatus,
)
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.testing import build_settings_service_for_tests


def _fresh_documents_status(root: Path) -> DatabaseStatus:
    return DatabaseStatus(
        database_id="documents",
        path=str(root / "documents.db"),
        state="missing",
        current_version=0,
        target_version=2,
        pending_versions=(2,),
        integrity="ok",
        detail=None,
    )


def _container(root: Path, *, postgres_dsn: str | None = None) -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("logger", LoggerService(root / "logs.jsonl"))
    container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
    container.register_port("event_bus", EventBus())
    container.register_port("settings_service", build_settings_service_for_tests(root))
    container.register_port("app_home", root)
    container.register_port("resource_root", root)
    container.register_port("documents_runtime_owner", "backend")
    container.register_port("signature_api", object())
    container.register_port("registry_projection_api", object())
    container.register_port(
        DATABASE_PREFLIGHT_STATUSES_PORT,
        MappingProxyType({"documents": _fresh_documents_status(root)}),
    )
    if postgres_dsn is not None:
        container.register_port("documents_postgres_dsn", postgres_dsn)
    return container


def test_adapt_sql_converts_placeholders_and_active_predicate() -> None:
    repo = PostgresDocumentsRepository("postgresql://example.invalid/db")
    sql = "SELECT 1 FROM workflow_profile_definitions WHERE profile_code = ? AND is_active = 1"
    assert repo.adapt_sql(sql) == (
        "SELECT 1 FROM workflow_profile_definitions WHERE profile_code = %s AND is_active = true"
    )


def test_register_documents_ports_uses_postgres_when_dsn_present(monkeypatch) -> None:
    monkeypatch.setattr(
        "modules.documents.wiring.WorkflowProfileRelationalStore.ensure_seeded",
        lambda self, seed_reader: None,
    )
    with tempfile.TemporaryDirectory() as tmp:
        container = _container(Path(tmp), postgres_dsn="postgresql://example.invalid/db")
        register_documents_ports(container)
        service = container.get_port("documents_service")
        assert isinstance(service, DocumentsService)
        assert isinstance(service._repository, PostgresDocumentsRepository)


def test_register_documents_ports_uses_sqlite_without_dsn(monkeypatch) -> None:
    monkeypatch.setattr(
        "modules.documents.wiring.WorkflowProfileRelationalStore.ensure_seeded",
        lambda self, seed_reader: None,
    )
    with tempfile.TemporaryDirectory() as tmp:
        container = _container(Path(tmp))
        register_documents_ports(container)
        service = container.get_port("documents_service")
        assert isinstance(service._repository, SQLiteDocumentsRepository)


def test_ensure_postgres_schema_ready_delegates(monkeypatch) -> None:
    calls: list[str] = []

    def _ready(dsn: str) -> int:
        calls.append(dsn)
        return 3

    monkeypatch.setattr("modules.documents.postgres_schema.assert_runtime_schema_ready", _ready)
    container = RuntimeContainer()
    container.register_port("documents_postgres_dsn", "postgresql://runtime.example/db")
    assert ensure_postgres_schema_ready(container) == 3
    assert calls == ["postgresql://runtime.example/db"]


def test_postgres_repository_implements_documents_repository_abc() -> None:
    from modules.documents.repository import DocumentsRepository

    for name in DocumentsRepository.__abstractmethods__:
        assert hasattr(PostgresDocumentsRepository, name)
        assert callable(getattr(PostgresDocumentsRepository, name))


def test_postgres_repository_does_not_use_sqlite_only_insert_or_replace() -> None:
    import inspect

    repo_path = Path(inspect.getfile(PostgresDocumentsRepository))
    text = repo_path.read_text(encoding="utf-8")
    assert "INSERT OR REPLACE" not in text
    assert " ON CONFLICT" in text


def test_postgres_repository_open_connection_validates_runtime_identity(monkeypatch) -> None:
    calls: list[str] = []

    class _FakeConn:
        def execute(self, *_args, **_kwargs):
            return None

    def _fake_connect(_dsn, *, row_factory):
        calls.append("connect")
        return _FakeConn()

    def _fake_validate(_conn) -> None:
        calls.append("validate")

    monkeypatch.setattr("modules.documents.postgres_repository.psycopg.connect", _fake_connect)
    monkeypatch.setattr(
        "modules.documents.postgres_connection._validate_runtime_identity",
        _fake_validate,
    )
    repo = PostgresDocumentsRepository("postgresql://example.invalid/db")
    repo._open_connection()
    assert calls == ["connect", "validate"]
