"""Static (no PostgreSQL) checks for AP-029 PG01-D signature repository wiring."""
from __future__ import annotations

import inspect
import tempfile
from pathlib import Path

import pytest

from modules.signature.api import ensure_postgres_schema_ready
from modules.signature.module import create_signature_module_contract
from modules.signature.postgres_repository import PostgresSignatureRepository
from modules.signature.repository import SignatureRepository
from modules.signature.service import SignatureServiceV2
from modules.signature.sqlite_repository import SQLiteSignatureRepository
from modules.signature.wiring import register_signature_ports
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.testing import build_settings_service_for_tests


class _FakeUsermanagement:
    def authenticate(self, username: str, password: str):
        return {"username": username}


def _container(root: Path, *, postgres_dsn: str | None = None) -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("logger", LoggerService(root / "logs.jsonl"))
    container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
    container.register_port("event_bus", EventBus())
    container.register_port("settings_service", build_settings_service_for_tests(root))
    container.register_port("app_home", root)
    container.register_port("usermanagement_service", _FakeUsermanagement())
    container.register_port("signature_runtime_owner", "backend")
    if postgres_dsn is not None:
        container.register_port("signature_postgres_dsn", postgres_dsn)
    return container


def test_register_signature_ports_uses_sqlite_without_postgres_port() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        container = _container(Path(tmp))
        register_signature_ports(container)
        service = container.get_port("signature_service")
        assert isinstance(service, SignatureServiceV2)
        assert isinstance(service.repository, SQLiteSignatureRepository)


def test_register_signature_ports_uses_postgres_when_dsn_port_present() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        container = _container(Path(tmp), postgres_dsn="postgresql://example.invalid/signature")
        register_signature_ports(container)
        service = container.get_port("signature_service")
        assert isinstance(service.repository, PostgresSignatureRepository)


def test_signature_module_contract_still_registers_ports() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        container = _container(root)
        create_signature_module_contract().register(container)
        assert container.has_port("signature_service")
        assert container.has_port("signature_api")


def test_ensure_postgres_schema_ready_delegates_to_schema_module(monkeypatch) -> None:
    calls: list[str] = []

    def _assert_ready(dsn: str) -> int:
        calls.append(dsn)
        return 2

    monkeypatch.setattr(
        "modules.signature.postgres_schema.assert_runtime_schema_ready",
        _assert_ready,
    )
    container = RuntimeContainer()
    container.register_port("signature_postgres_dsn", "postgresql://runtime.example/db")
    assert ensure_postgres_schema_ready(container) == 2
    assert calls == ["postgresql://runtime.example/db"]


def test_postgres_repository_implements_signature_repository_abc() -> None:
    for name in SignatureRepository.__abstractmethods__:
        assert hasattr(PostgresSignatureRepository, name)
        assert callable(getattr(PostgresSignatureRepository, name))


def test_sqlite_repository_subclasses_signature_repository_abc() -> None:
    assert issubclass(SQLiteSignatureRepository, SignatureRepository)


def test_postgres_repository_does_not_use_sqlite_only_insert_or_replace() -> None:
    repo_path = Path(inspect.getfile(PostgresSignatureRepository))
    text = repo_path.read_text(encoding="utf-8")
    assert "INSERT OR REPLACE" not in text
    assert " ON CONFLICT" in text


def test_postgres_upsert_template_writes_python_bools(monkeypatch) -> None:
    captured: list[tuple] = []

    class _FakeConn:
        def execute(self, _sql, params=None, **_kwargs):
            captured.append(tuple(params or ()))
            return None

        def commit(self) -> None:
            return None

    def _fake_runtime_connection(_dsn):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield _FakeConn()

        return _cm()

    monkeypatch.setattr(
        "modules.signature.postgres_repository.runtime_connection",
        _fake_runtime_connection,
    )
    from datetime import datetime, timezone

    from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput, UserSignatureTemplate

    repo = PostgresSignatureRepository("postgresql://example.invalid/db")
    template = UserSignatureTemplate(
        template_id="tpl-1",
        owner_user_id="user-1",
        name="Default",
        placement=SignaturePlacementInput(page_index=0, x=10.0, y=20.0, target_width=100.0),
        layout=LabelLayoutInput(show_signature=True, show_name=False, show_date=True),
        signature_asset_id=None,
        created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        scope="user",
    )
    repo.upsert_template(template)
    assert captured
    params = captured[0]
    assert isinstance(params[7], bool)
    assert isinstance(params[8], bool)
    assert isinstance(params[9], bool)


def test_build_backend_container_registers_signature_postgres_dsn() -> None:
    bootstrap_path = Path(inspect.getfile(__import__("src.backend.bootstrap", fromlist=["bootstrap"])))
    text = bootstrap_path.read_text(encoding="utf-8")
    assert 'register_port("signature_postgres_dsn"' in text


def test_backend_bootstrap_excludes_signature_sqlite_when_postgres_active() -> None:
    bootstrap_path = Path(inspect.getfile(__import__("qm_platform.runtime.backend_bootstrap", fromlist=["backend_bootstrap"])))
    text = bootstrap_path.read_text(encoding="utf-8")
    assert "use_signature_postgres" in text
    assert 'contribution.database_id != "signature"' in text
    assert "ensure_signature_postgres_schema_ready" in text
