"""Shared test helpers for incident_management."""

from __future__ import annotations

import tempfile
from pathlib import Path

from modules.documents.module import create_documents_module_contract
from modules.incident_management.module import create_incident_management_module_contract
from modules.registry.module import create_registry_module_contract
from modules.signature.module import create_signature_module_contract
from modules.training.module import create_training_module_contract
from modules.usermanagement.module import create_usermanagement_module_contract
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.lifecycle import LifecycleManager
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore


class _LicenseAllowAll:
    def is_module_allowed(self, _: str) -> bool:
        return True


class _FakeUser:
    def __init__(self, user_id: str, role: str, *, is_qmb: bool = False) -> None:
        self.user_id = user_id
        self.role = role
        self.is_qmb = is_qmb


class _FakeUserManagement:
    def __init__(self, user: _FakeUser | None) -> None:
        self._user = user

    def get_current_user(self):
        return self._user


def _incident_api_service(container: RuntimeContainer) -> object:
    api = container.get_port("incident_management_api")
    inner = getattr(api, "_inner", api)
    return inner._service


def _install_fake_usermanagement(container: RuntimeContainer, user: _FakeUser | None) -> _FakeUserManagement:
    fake = _FakeUserManagement(user)
    container.register_port("usermanagement_service", fake)
    if container.has_port("incident_management_api"):
        _incident_api_service(container)._usermanagement = fake
    return fake


def switch_incident_user(container: RuntimeContainer, user: _FakeUser) -> None:
    """Switch current user for incident_management API calls without a public service port."""
    um = container.get_port("usermanagement_service")
    if isinstance(um, _FakeUserManagement):
        um._user = user
        return
    _install_fake_usermanagement(container, user)


def build_incident_test_container(*, user: _FakeUser | None = None) -> tuple[RuntimeContainer, Path]:
    tmp = tempfile.mkdtemp()
    root = Path(tmp)
    container = RuntimeContainer()
    container.register_port("logger", LoggerService(root / "logs.jsonl"))
    container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
    container.register_port("event_bus", EventBus())
    container.register_port(
        "settings_service",
        SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json")),
    )
    container.register_port("license_service", _LicenseAllowAll())
    container.register_port("app_home", root)
    container.register_port("resource_root", root)
    container.register_port("usermanagement_service", _FakeUserManagement(user))

    lifecycle = LifecycleManager(container)
    for contract in (
        create_usermanagement_module_contract(),
        create_signature_module_contract(),
        create_registry_module_contract(),
        create_documents_module_contract(),
        create_training_module_contract(),
        create_incident_management_module_contract(),
    ):
        lifecycle.prepare(contract)
    runtime_bootstrap.activate_core_modules(container, lifecycle)
    lifecycle.start()

    _install_fake_usermanagement(container, user)
    return container, root


def run_capa_to_closure_review(api, case) -> object:
    """Run CAPA workflow until incident reaches CLOSURE_REVIEW (effective review)."""
    from modules.incident_management.contracts import ActionType, CapaStatus

    api.create_root_cause_analysis(case.incident_id, root_causes="Gap")
    api.start_capa(case.incident_id)
    api.update_capa(case.incident_id, status=CapaStatus.IN_PROGRESS)
    act = api.create_action(case.incident_id, ActionType.CORRECTIVE_ACTION, "Fix")
    api.complete_action(act.action_id)
    api.plan_effectiveness_review(case.incident_id, "No repeat")
    api.complete_effectiveness_review(case.incident_id, effective=True, result="OK")
    return api.get_incident(case.incident_id)


def list_incident_timeline(container, incident_id: str):
    return container.get_port("incident_management_api").list_incident_timeline(incident_id)
