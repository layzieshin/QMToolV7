from __future__ import annotations

from types import SimpleNamespace

from interfaces.cli.commands import documents_commands
from modules.documents.contracts import DocumentVersionState
from modules.documents.errors import DocumentWorkflowError
from qm_platform.runtime.container import RuntimeContainer


class _NoopLifecycle:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class _FakeWorkflowApi:
    def list_workflow_profile_definitions(self, *, include_inactive: bool = True):
        return [{"profile_code": "long_release", "label": "Long Release", "is_active": True}]

    def start_workflow(self, state, profile=None, *, profile_id=None, actor_user_id=None, actor_role=None, actor=None):
        if profile_id and profile_id != state.workflow_profile_id:
            raise DocumentWorkflowError(
                f"profile_id {profile_id!r} does not match bound workflow_profile_id {state.workflow_profile_id!r}"
            )
        return state

    def create_workflow_profile_definition(self, payload, *, change_reason: str):
        return {"profile_code": payload["profile_code"], "change_reason": change_reason}


class _FakePoolApi:
    def get_document_version(self, document_id: str, version: int):
        return DocumentVersionState(document_id=document_id, version=version, workflow_profile_id="long_release")


def _fake_container() -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("documents_pool_api", _FakePoolApi())
    container.register_port("documents_workflow_api", _FakeWorkflowApi())
    container.register_port("registry_api", object())
    container.register_port("usermanagement_service", object())
    return container


def test_profile_admin_cli_command_uses_session_token(monkeypatch, capsys) -> None:
    monkeypatch.setenv("QMTOOL_SESSION_TOKEN", "token-123")
    monkeypatch.setattr(documents_commands, "build_container", _fake_container)
    monkeypatch.setattr(documents_commands.runtime_bootstrap, "register_core_modules", lambda _c: _NoopLifecycle())
    args = SimpleNamespace(documents_command="profile-list", profile_id=None, include_inactive=True)
    rc = documents_commands.cmd_documents(args)
    captured = capsys.readouterr()
    assert rc == 0, captured.out + captured.err
    assert "long_release" in captured.out


def test_profile_admin_cli_create_is_blocked_under_reduced_m0_scope(monkeypatch, capsys) -> None:
    """Mutating profile-create stays blocked at the reduced M0 CLI adapter entry."""
    monkeypatch.setenv("QMTOOL_SESSION_TOKEN", "token-123")

    def _must_not_build_container() -> RuntimeContainer:
        raise AssertionError("build_container must not run when profile-create is blocked at adapter entry")

    monkeypatch.setattr(documents_commands, "build_container", _must_not_build_container)
    monkeypatch.setattr(documents_commands.runtime_bootstrap, "register_core_modules", lambda _c: _NoopLifecycle())
    args = SimpleNamespace(documents_command="profile-create", definition_json="ignored.json", change_reason="x")
    rc = documents_commands.cmd_documents(args)
    captured = capsys.readouterr()
    assert rc == 6
    assert "BLOCKED" in captured.out
    assert "profile-create" in captured.out
    assert "outside the reduced J04-M0 transition-client scope" in captured.out


def test_profile_admin_cli_requires_session_token(monkeypatch, capsys) -> None:
    monkeypatch.delenv("QMTOOL_SESSION_TOKEN", raising=False)
    monkeypatch.setattr(documents_commands, "build_container", _fake_container)
    monkeypatch.setattr(documents_commands.runtime_bootstrap, "register_core_modules", lambda _c: _NoopLifecycle())
    args = SimpleNamespace(documents_command="profile-list", profile_id=None, include_inactive=True)
    rc = documents_commands.cmd_documents(args)
    captured = capsys.readouterr()
    assert rc == 6
    assert "QMTOOL_SESSION_TOKEN is required" in captured.out


def test_workflow_start_cli_rejects_mismatched_profile_id(monkeypatch, capsys) -> None:
    monkeypatch.setenv("QMTOOL_SESSION_TOKEN", "token-123")
    monkeypatch.setattr(documents_commands, "build_container", _fake_container)
    monkeypatch.setattr(documents_commands.runtime_bootstrap, "register_core_modules", lambda _c: _NoopLifecycle())
    args = SimpleNamespace(
        documents_command="workflow-start",
        document_id="DOC-CLI-START-1",
        version=1,
        profile_id="external_control",
    )
    rc = documents_commands.cmd_documents(args)
    captured = capsys.readouterr()
    assert rc == 6
    assert "does not match bound workflow_profile_id" in (captured.out + captured.err)
