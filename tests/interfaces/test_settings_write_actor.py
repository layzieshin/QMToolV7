"""Settings write-path actor rules (no legacy current_user as actor)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from interfaces.settings_actor import resolve_confirmed_settings_actor
from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
from modules.usermanagement.contracts import issue_user_context
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.errors import (
    ResidualPolicyReadonlyError,
    SettingsActorRequiredError,
)
from qm_platform.settings.testing import build_settings_service_for_tests


def _confirmed_actor():
    return issue_user_context(
        user_id="actor-1",
        session_id="sess-1",
        request_id="req-1",
        username="admin",
        global_roles=["Admin"],
        is_qmb=False,
        authenticated_at=datetime.now(timezone.utc),
    )


def test_resolve_confirmed_settings_actor_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_SESSION_TOKEN", raising=False)
    container = RuntimeContainer()
    with pytest.raises(SettingsActorRequiredError):
        resolve_confirmed_settings_actor(container)


def test_resolve_confirmed_settings_actor_uses_resolve_session(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_SESSION_TOKEN", raising=False)
    container = RuntimeContainer()
    container.register_port("session_token", "opaque-token")
    expected = _confirmed_actor()

    def _fake_resolve(container_arg, token, *, request_id):
        assert token == "opaque-token"
        assert request_id == "settings-write"
        return expected

    monkeypatch.setattr(
        "interfaces.settings_actor.um_api.resolve_session",
        _fake_resolve,
    )
    assert resolve_confirmed_settings_actor(container) is expected


def test_resolve_confirmed_settings_actor_rejects_unresolvable_legacy_runtime(
    monkeypatch,
) -> None:
    monkeypatch.delenv("QMTOOL_SESSION_TOKEN", raising=False)
    container = RuntimeContainer()
    container.register_port("session_token", "opaque-token")

    def _unconfigured(*_args, **_kwargs):
        raise RuntimeError("opaque session repository is not configured")

    monkeypatch.setattr(
        "interfaces.settings_actor.um_api.resolve_session",
        _unconfigured,
    )
    with pytest.raises(SettingsActorRequiredError):
        resolve_confirmed_settings_actor(container)


def test_settings_adapter_resolves_actor_and_writes_without_local_session_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("QMTOOL_SESSION_TOKEN", raising=False)
    container = RuntimeContainer()
    container.register_port("session_token", "opaque-token")
    actor = _confirmed_actor()
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)

    def _fake_resolve(container_arg, token, *, request_id):
        assert container_arg is container
        assert token == "opaque-token"
        assert request_id == "settings-adapter-test"
        return actor

    monkeypatch.setattr(
        "interfaces.settings_actor.um_api.resolve_session",
        _fake_resolve,
    )
    resolved = resolve_confirmed_settings_actor(
        container,
        request_id="settings-adapter-test",
    )
    service.set_module_settings(
        "signature",
        {"require_password": False, "default_mode": "visual"},
        actor=resolved,
        acknowledge_governance_change=True,
    )

    assert service.get_module_settings("signature")["require_password"] is False
    assert not (tmp_path / "storage/platform/users.db").exists()
    assert not (tmp_path / "storage/platform/session/current_user.json").exists()


def test_settings_service_rejects_unconfirmed_actor_object(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)

    class LegacyUser:
        user_id = "legacy"
        is_confirmed = False

    with pytest.raises(SettingsActorRequiredError):
        service.set_module_settings(
            "signature",
            {"require_password": True, "default_mode": "visual"},
            actor=LegacyUser(),
            acknowledge_governance_change=True,
        )


def test_settings_service_rejects_forged_is_confirmed_actor(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)

    class ForgedConfirmed:
        user_id = "forged"
        session_id = "s"
        request_id = "r"
        is_confirmed = True  # public flag only — no _server_confirmed

    with pytest.raises(SettingsActorRequiredError):
        service.set_module_settings(
            "signature",
            {"require_password": True, "default_mode": "visual"},
            actor=ForgedConfirmed(),
            acknowledge_governance_change=True,
        )


def test_settings_service_rejects_direct_user_context_construction(tmp_path: Path) -> None:
    from modules.usermanagement.contracts import UserContext

    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
    unconfirmed = UserContext(
        user_id="u1",
        session_id="s1",
        request_id="r1",
        username="admin",
        global_roles=frozenset({"Admin"}),
        is_qmb=False,
        authenticated_at=datetime.now(timezone.utc),
    )
    assert unconfirmed.is_confirmed is False
    with pytest.raises(SettingsActorRequiredError):
        service.set_module_settings(
            "signature",
            {"require_password": True, "default_mode": "visual"},
            actor=unconfirmed,
            acknowledge_governance_change=True,
        )


def test_settings_service_rejects_classname_fake_user_context(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)

    class UserContext:  # noqa: N801 — intentional classname spoof
        user_id = "spoof"
        session_id = "s"
        request_id = "r"
        _server_confirmed = True

    with pytest.raises(SettingsActorRequiredError):
        service.set_module_settings(
            "signature",
            {"require_password": True, "default_mode": "visual"},
            actor=UserContext(),
            acknowledge_governance_change=True,
        )


def test_settings_service_rejects_missing_session_or_request_id(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
    missing_session = issue_user_context(
        user_id="actor-1",
        session_id="sess-1",
        request_id="req-1",
        username="admin",
        global_roles=["Admin"],
        is_qmb=False,
        authenticated_at=datetime.now(timezone.utc),
    )
    object.__setattr__(missing_session, "session_id", "")
    missing_request = issue_user_context(
        user_id="actor-1",
        session_id="sess-1",
        request_id="req-1",
        username="admin",
        global_roles=["Admin"],
        is_qmb=False,
        authenticated_at=datetime.now(timezone.utc),
    )
    object.__setattr__(missing_request, "request_id", "")
    for actor in (missing_session, missing_request):
        with pytest.raises(SettingsActorRequiredError):
            service.set_module_settings(
                "signature",
                {"require_password": True, "default_mode": "visual"},
                actor=actor,
                acknowledge_governance_change=True,
            )


def test_settings_service_accepts_allowed_system_actors(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
    for actor in ("migration:j02-settings-import", "system:backend_bootstrap"):
        service.set_module_settings(
            "signature",
            {"require_password": True, "default_mode": "visual"},
            actor=actor,
            acknowledge_governance_change=True,
        )


def test_settings_service_rejects_unknown_string_actor(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
    with pytest.raises(SettingsActorRequiredError):
        service.set_module_settings(
            "signature",
            {"require_password": True, "default_mode": "visual"},
            actor="system:someone_else",
            acknowledge_governance_change=True,
        )


def test_bucket_c_write_blocked_even_with_confirmed_actor(tmp_path: Path) -> None:
    from qm_platform.sdk.module_contract import SettingsContribution

    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(
        SettingsContribution(
            module_id="incident_management",
            schema_version=1,
            schema={
                "type": "object",
                "properties": {"effectiveness_delay": {"type": "integer"}},
                "additionalProperties": False,
            },
            defaults={"effectiveness_delay": 30},
            scope="module_global",
            migrations=[],
        )
    )
    with pytest.raises(ResidualPolicyReadonlyError):
        service.set_module_settings(
            "incident_management",
            {"effectiveness_delay": 45},
            actor=_confirmed_actor(),
            acknowledge_governance_change=True,
        )


def test_bucket_b_write_with_confirmed_actor(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
    service.set_module_settings(
        "signature",
        {"require_password": False, "default_mode": "visual"},
        actor=_confirmed_actor(),
        acknowledge_governance_change=True,
    )
    assert service.get_module_settings("signature")["require_password"] is False
