"""Static (no PostgreSQL) checks for AP-029 PG01-B registry repository wiring."""
from __future__ import annotations

import tempfile
from pathlib import Path

from modules.registry.api import ensure_postgres_schema_ready
from modules.registry.module import create_registry_module_contract
from modules.registry.postgres_repository import PostgresRegistryRepository
from modules.registry.service import RegistryService
from modules.registry.sqlite_repository import SQLiteRegistryRepository
from modules.registry.wiring import register_registry_ports
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.testing import build_settings_service_for_tests


def _build_container(root: Path, *, postgres_dsn: str | None = None) -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("logger", LoggerService(root / "logs.jsonl"))
    container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
    container.register_port("event_bus", EventBus())
    container.register_port("settings_service", build_settings_service_for_tests(root))
    container.register_port("app_home", root)
    if postgres_dsn is not None:
        container.register_port("registry_postgres_dsn", postgres_dsn)
    return container


def test_register_registry_ports_uses_sqlite_without_postgres_port() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        container = _build_container(Path(tmp))
        register_registry_ports(container)
        service = container.get_port("registry_service")
        assert isinstance(service, RegistryService)
        assert isinstance(service._repository, SQLiteRegistryRepository)


def test_register_registry_ports_uses_postgres_when_dsn_port_present() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        container = _build_container(Path(tmp), postgres_dsn="postgresql://example.invalid/registry")
        register_registry_ports(container)
        service = container.get_port("registry_service")
        assert isinstance(service._repository, PostgresRegistryRepository)


def test_registry_module_contract_still_registers_ports() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        container = _build_container(root)
        create_registry_module_contract().register(container)
        assert container.has_port("registry_service")
        assert container.has_port("registry_api")
        assert container.has_port("registry_projection_api")


def test_ensure_postgres_schema_ready_delegates_to_schema_module(monkeypatch) -> None:
    calls: list[str] = []

    def _assert_ready(dsn: str) -> int:
        calls.append(dsn)
        return 2

    monkeypatch.setattr(
        "modules.registry.postgres_schema.assert_runtime_schema_ready",
        _assert_ready,
    )
    container = RuntimeContainer()
    container.register_port("registry_postgres_dsn", "postgresql://runtime.example/db")
    assert ensure_postgres_schema_ready(container) == 2
    assert calls == ["postgresql://runtime.example/db"]


def test_row_to_entry_normalizes_empty_release_note_like_sqlite() -> None:
    from modules.registry.postgres_repository import _row_to_entry

    entry = _row_to_entry(
        {
            "document_id": "DOC-EMPTY",
            "active_version": 1,
            "release_note": "",
            "release_evidence_mode": "WORKFLOW",
            "register_state": "VALID",
            "is_findable": True,
            "valid_from": None,
            "valid_until": None,
            "last_update_event_id": "evt-1",
            "last_update_at": "2024-06-01T10:00:00+00:00",
        }
    )
    assert entry.release_note is None
