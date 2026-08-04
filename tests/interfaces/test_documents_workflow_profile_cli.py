from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from interfaces.cli.bootstrap import build_container
from interfaces.cli.commands import documents_commands
from modules.usermanagement.api import login_backend, resolve_session
from modules.usermanagement.memory_session_repository import InMemorySessionRepository
from modules.usermanagement.service import _ServiceUserByIdLookup
from modules.usermanagement.session_ops import SessionOps
from qm_platform.runtime import bootstrap as runtime_bootstrap


class _NoopLifecycle:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


def _prepare_container_with_sessions(tmp_path: Path):
    import os

    os.environ["QMTOOL_HOME"] = str(tmp_path / "home")
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    um = container.get_port("usermanagement_service")
    sessions = InMemorySessionRepository()
    um.session_repository = sessions
    um._session_ops = SessionOps(
        session_repository=sessions,
        users=_ServiceUserByIdLookup(um),
    )
    um.ensure_admin_credentials("admin", "adminpass01")
    try:
        um.create_user("qmb", "qmbpass001", role="QMB", is_qmb=True)
    except Exception:
        pass
    return container


def test_profile_admin_api_accepts_confirmed_backend_session(tmp_path: Path) -> None:
    container = _prepare_container_with_sessions(tmp_path)
    issued = login_backend(container, "qmb", "qmbpass001", request_id="cli-profile-positive")
    actor = resolve_session(container, issued.raw_token, request_id="cli-documents-workflow-profiles")
    api = container.get_port("documents_workflow_api")
    listed = api.list_workflow_profile_definitions(actor=actor)
    assert any(item["profile_code"] == "long_release" for item in listed)


def test_profile_admin_cli_command_uses_session_token(tmp_path: Path, monkeypatch, capsys) -> None:
    container = _prepare_container_with_sessions(tmp_path)
    issued = login_backend(container, "qmb", "qmbpass001", request_id="cli-profile-cli")
    monkeypatch.setenv("QMTOOL_SESSION_TOKEN", issued.raw_token)
    monkeypatch.setattr(documents_commands, "build_container", lambda: container)
    monkeypatch.setattr(documents_commands.runtime_bootstrap, "register_core_modules", lambda _c: _NoopLifecycle())

    args = SimpleNamespace(
        documents_command="profile-list",
        profile_id=None,
        include_inactive=True,
    )
    rc = documents_commands.cmd_documents(args)
    captured = capsys.readouterr()
    assert rc == 0, captured.out + captured.err
    assert "long_release" in captured.out


def test_profile_admin_cli_create_full_definition(tmp_path: Path, monkeypatch, capsys) -> None:
    container = _prepare_container_with_sessions(tmp_path)
    issued = login_backend(container, "qmb", "qmbpass001", request_id="cli-profile-create")
    monkeypatch.setenv("QMTOOL_SESSION_TOKEN", issued.raw_token)
    monkeypatch.setattr(documents_commands, "build_container", lambda: container)
    monkeypatch.setattr(documents_commands.runtime_bootstrap, "register_core_modules", lambda _c: _NoopLifecycle())

    definition = {
        "profile_code": "cli_created_profile",
        "label": "CLI Created",
        "control_class": "CONTROLLED",
        "requires_editors": True,
        "requires_reviewers": True,
        "requires_approvers": True,
        "allows_content_changes": True,
        "transitions": [
            {
                "transition_no": 1,
                "from_status": "DRAFT",
                "to_status": "IN_REVIEW",
                "required_role": "EDITOR",
                "decision_policy": "ONE_OF_POOL",
                "signature_required": False,
                "four_eyes_required": False,
            },
            {
                "transition_no": 2,
                "from_status": "IN_REVIEW",
                "to_status": "APPROVED",
                "required_role": "REVIEWER",
                "decision_policy": "ONE_OF_POOL",
                "signature_required": False,
                "four_eyes_required": False,
            },
        ],
    }
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(definition), encoding="utf-8")
    args = SimpleNamespace(
        documents_command="profile-create",
        definition_json=str(path),
        change_reason="cli create",
    )
    rc = documents_commands.cmd_documents(args)
    captured = capsys.readouterr()
    assert rc == 0, captured.out + captured.err
    assert "cli_created_profile" in captured.out


def test_workflow_start_cli_rejects_mismatched_profile_id(tmp_path: Path, monkeypatch, capsys) -> None:
    from modules.documents.contracts import SystemRole

    container = _prepare_container_with_sessions(tmp_path)
    um = container.get_port("usermanagement_service")
    logged_in = um.login("admin", "adminpass01")
    assert logged_in is not None
    monkeypatch.setattr(documents_commands, "build_container", lambda: container)
    monkeypatch.setattr(documents_commands.runtime_bootstrap, "register_core_modules", lambda _c: _NoopLifecycle())

    api = container.get_port("documents_workflow_api")
    current = um.get_current_user()
    assert current is not None
    state = api.create_document_version(
        "DOC-CLI-START-1",
        1,
        owner_user_id=current.user_id,
    )
    state = api.assign_workflow_roles(
        state,
        editors={current.user_id},
        reviewers={current.user_id},
        approvers={current.user_id},
        actor_user_id=current.user_id,
        actor_role=SystemRole.ADMIN,
    )
    args = SimpleNamespace(
        documents_command="workflow-start",
        document_id=state.document_id,
        version=state.version,
        profile_id="external_control",
    )
    rc = documents_commands.cmd_documents(args)
    captured = capsys.readouterr()
    assert rc != 0
    assert "does not match bound workflow_profile_id" in (captured.out + captured.err)
