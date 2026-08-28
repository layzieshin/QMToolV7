"""Static (no PostgreSQL) checks for AP-029 PG01-C documents repository wiring."""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import MappingProxyType

import pytest

from modules.documents.bootstrap_provenance import DocumentsBootstrapProvenance
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
    if postgres_dsn is None:
        container.register_port(
            DATABASE_PREFLIGHT_STATUSES_PORT,
            MappingProxyType({"documents": _fresh_documents_status(root)}),
        )
    else:
        container.register_port("documents_postgres_dsn", postgres_dsn)
        container.register_port(DATABASE_PREFLIGHT_STATUSES_PORT, MappingProxyType({}))
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
        assert "documents" not in container.get_port(DATABASE_PREFLIGHT_STATUSES_PORT)
        register_documents_ports(container)
        service = container.get_port("documents_service")
        assert isinstance(service, DocumentsService)
        assert isinstance(service._repository, PostgresDocumentsRepository)
        assert service._profile_store._bootstrap_provenance == DocumentsBootstrapProvenance.POST_J03_SCHEMA


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


def test_postgres_repository_has_exactly_one_transaction_helper_definition() -> None:
    import ast
    import inspect

    source = Path(inspect.getfile(PostgresDocumentsRepository)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_body = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PostgresDocumentsRepository"
    )
    counts: dict[str, int] = {}
    for node in class_body.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            counts[node.name] = counts.get(node.name, 0) + 1
    for name in ("_txn_conn", "_set_txn_conn", "write_transaction", "_connect", "_commit_if_needed"):
        assert counts.get(name) == 1, f"{name} defined {counts.get(name, 0)} times"


def test_get_uses_for_update_only_inside_write_transaction(monkeypatch) -> None:
    recorded: list[str] = []

    class _FakeCursor:
        def fetchone(self):
            return None

    class _FakeConn:
        def execute(self, sql, *_args, **_kwargs):
            recorded.append(str(sql))
            return _FakeCursor()

        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    repo = PostgresDocumentsRepository("postgresql://example.invalid/db")
    monkeypatch.setattr(repo, "_open_connection", lambda: _FakeConn())

    repo.get("DOC-1", 1)
    assert recorded == [
        "SELECT * FROM documents.document_versions WHERE document_id = %s AND version = %s"
    ]

    recorded.clear()
    with repo.write_transaction():
        repo.get("DOC-1", 1)
    assert recorded == [
        "BEGIN",
        "SELECT * FROM documents.document_versions WHERE document_id = %s AND version = %s FOR UPDATE",
    ]


def test_write_transaction_nested_is_noop_and_outer_commits(monkeypatch) -> None:
    events: list[str] = []

    class _FakeConn:
        def execute(self, sql, *_args, **_kwargs):
            events.append(f"execute:{sql}")
            return None

        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:
            events.append("rollback")

        def close(self) -> None:
            events.append("close")

    repo = PostgresDocumentsRepository("postgresql://example.invalid/db")
    monkeypatch.setattr(repo, "_open_connection", lambda: _FakeConn())

    with repo.write_transaction():
        events.append("outer")
        with repo.write_transaction():
            events.append("inner")
            with repo._connect() as conn:
                assert conn is repo._txn_conn()
                repo._commit_if_needed(conn)
                events.append("nested-commit-skipped")

    assert events == [
        "execute:BEGIN",
        "outer",
        "inner",
        "nested-commit-skipped",
        "commit",
        "close",
    ]
    assert repo._txn_conn() is None


def test_write_transaction_rolls_back_and_clears_on_error(monkeypatch) -> None:
    events: list[str] = []

    class _FakeConn:
        def execute(self, sql, *_args, **_kwargs):
            events.append(f"execute:{sql}")
            return None

        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:
            events.append("rollback")

        def close(self) -> None:
            events.append("close")

    repo = PostgresDocumentsRepository("postgresql://example.invalid/db")
    monkeypatch.setattr(repo, "_open_connection", lambda: _FakeConn())

    with pytest.raises(RuntimeError, match="boom"):
        with repo.write_transaction():
            events.append("body")
            raise RuntimeError("boom")

    assert events == ["execute:BEGIN", "body", "rollback", "close"]
    assert repo._txn_conn() is None


def test_workflow_profile_store_writes_python_bools_via_postgres_adapter() -> None:
    """Execute real WorkflowProfileRelationalStore write paths against a recording PG adapter."""
    from contextlib import contextmanager

    from modules.documents.bootstrap_provenance import DocumentsBootstrapProvenance
    from modules.documents.contracts import ControlClass, DocumentType
    from modules.documents.workflow_profile_store import (
        WorkflowProfileRelationalStore,
        WorkflowProfileTransitionDefinition,
        WorkflowProfileVersionDefinition,
    )

    recorded: list[tuple[str, tuple[object, ...]]] = []

    class _RecordingCursor:
        def __init__(self, rows=None) -> None:
            self._rows = rows or []

        def fetchone(self):
            return self._rows[0] if self._rows else None

        def fetchall(self):
            return list(self._rows)

    class _RecordingConn:
        def execute(self, sql, params=()):
            param_tuple = tuple(params) if params else ()
            recorded.append((str(sql), param_tuple))
            upper = str(sql).upper()
            if "SELECT 1 FROM WORKFLOW_PROFILE_DEFINITIONS" in upper:
                return _RecordingCursor([])
            if "SELECT ALLOWS_PROFILE_OVERRIDE FROM DOCUMENT_TYPE_DEFINITIONS" in upper:
                return _RecordingCursor([])
            if "SELECT CONTROL_CLASS FROM WORKFLOW_PROFILE_DEFINITIONS" in upper:
                return _RecordingCursor([{"control_class": ControlClass.CONTROLLED.value}])
            return _RecordingCursor([])

    class _RecordingPostgresRepo:
        def adapt_sql(self, sql: str) -> str:
            return PostgresDocumentsRepository.adapt_sql(self, sql)

        def adapt_params(self, params):
            return PostgresDocumentsRepository.adapt_params(params)

        @contextmanager
        def write_transaction(self):
            yield

        @contextmanager
        def _connect(self):
            yield _RecordingConn()

    payload = WorkflowProfileVersionDefinition(
        profile_code="pg_bool_probe",
        label="PG Bool Probe",
        control_class=ControlClass.CONTROLLED,
        release_evidence_mode="WORKFLOW",
        requires_editors=True,
        requires_reviewers=True,
        requires_approvers=True,
        allows_content_changes=False,
        transitions=(
            WorkflowProfileTransitionDefinition(
                transition_no=1,
                from_status="DRAFT",
                to_status="IN_REVIEW",
                required_role="EDITOR",
                decision_policy="ONE_OF_POOL",
                signature_required=True,
                four_eyes_required=False,
                revoke_if_changed=False,
                deadline_seconds=None,
                is_enabled=True,
            ),
            WorkflowProfileTransitionDefinition(
                transition_no=2,
                from_status="IN_REVIEW",
                to_status="IN_APPROVAL",
                required_role="REVIEWER",
                decision_policy="ONE_OF_POOL",
                signature_required=True,
                four_eyes_required=False,
                revoke_if_changed=False,
                deadline_seconds=None,
                is_enabled=True,
            ),
            WorkflowProfileTransitionDefinition(
                transition_no=3,
                from_status="IN_APPROVAL",
                to_status="APPROVED",
                required_role="APPROVER",
                decision_policy="ONE_OF_POOL",
                signature_required=True,
                four_eyes_required=True,
                revoke_if_changed=False,
                deadline_seconds=None,
                is_enabled=True,
            ),
        ),
    )
    store = WorkflowProfileRelationalStore(
        _RecordingPostgresRepo(),
        bundled_seed_path=Path("modules/documents/workflow_profiles.json"),
        legacy_profiles_path=Path("modules/documents/workflow_profiles.json"),
        bootstrap_provenance=DocumentsBootstrapProvenance.FRESH_INSTALL,
    )
    store.create_definition(
        payload,
        source_kind="ADMIN",
        change_reason="hr2-bool-probe",
        actor_user_id="tester",
    )
    store.bind_default_profile(
        DocumentType.OTHER,
        "pg_bool_probe",
        allows_profile_override=True,
        actor_user_id="tester",
    )

    inserts = [(sql, params) for sql, params in recorded if "INSERT INTO" in sql.upper()]
    assert inserts, "expected INSERT statements from profile store write paths"

    boolean_params: list[object] = []
    integer_params: list[object] = []
    for sql, params in inserts:
        upper = sql.upper()
        if "WORKFLOW_PROFILE_DEFINITIONS" in upper:
            # profile_code, label, control_class, is_active, active_version, ...
            assert isinstance(params[3], bool), params
            assert params[3] is True
            assert isinstance(params[4], int) and not isinstance(params[4], bool)
            assert params[4] == 1
            boolean_params.append(params[3])
            integer_params.append(params[4])
        elif "WORKFLOW_PROFILE_VERSIONS" in upper:
            # ..., version_no, ..., four_eyes, requires_*, allows_content_changes, ...
            assert isinstance(params[2], int) and not isinstance(params[2], bool)
            for idx in (8, 9, 10, 11, 12):
                assert isinstance(params[idx], bool), (idx, params[idx], params)
                boolean_params.append(params[idx])
            integer_params.append(params[2])
        elif "WORKFLOW_PROFILE_TRANSITIONS" in upper:
            assert isinstance(params[2], int) and not isinstance(params[2], bool)
            for idx in (7, 8, 9, 11):
                assert isinstance(params[idx], bool), (idx, params[idx], params)
                boolean_params.append(params[idx])
            integer_params.append(params[2])
            assert params[10] is None
        elif "DOCUMENT_TYPE_DEFINITIONS" in upper:
            assert isinstance(params[3], bool), params
            boolean_params.append(params[3])

    assert boolean_params
    assert all(isinstance(value, bool) for value in boolean_params)
    assert all(isinstance(value, int) and not isinstance(value, bool) for value in integer_params)
    assert any(value is False for value in boolean_params)
    assert any(value is True for value in boolean_params)
