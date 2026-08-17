from __future__ import annotations

from dataclasses import dataclass, field

from ..sdk.module_contract import ModuleContract
from ..settings.settings_service import SettingsService
from .capabilities import CapabilityRegistry
from .container import RuntimeContainer
from .lifecycle_checks import (
    ensure_license,
    ensure_provided_ports,
    ensure_required_capabilities,
    ensure_required_ports,
)
from .module_loader import validate_contract


@dataclass
class LifecycleManager:
    container: RuntimeContainer
    _contracts: dict[str, ModuleContract] = field(default_factory=dict)
    _started: list[str] = field(default_factory=list)
    _capabilities: CapabilityRegistry = field(default_factory=CapabilityRegistry)
    _failed: dict[str, str] = field(default_factory=dict)
    _wired: set[str] = field(default_factory=set)

    def register(self, contract: ModuleContract) -> None:
        self.prepare(contract)
        self.wire(contract.module_id)

    def prepare(self, contract: ModuleContract) -> None:
        validate_contract(contract)
        if contract.module_id in self._contracts:
            raise ValueError(f"duplicate module id: {contract.module_id}")
        self._contracts[contract.module_id] = contract
        self._capabilities.register(contract.module_id, contract.provided_capabilities)
        self._register_settings_contribution(contract)

    def wire(self, module_id: str) -> None:
        if module_id not in self._contracts:
            raise KeyError(f"module is not prepared: {module_id}")
        if module_id in self._wired:
            return
        self._contracts[module_id].register(self.container)
        self._wired.add(module_id)

    def wire_all(self) -> None:
        for module_id in self._contracts:
            self.wire(module_id)

    def start(self, *, strict: bool = True) -> None:
        for module_id in sorted(self._contracts.keys()):
            if module_id in self._started:
                continue
            contract = self._contracts[module_id]
            try:
                ensure_required_ports(self.container, contract)
                ensure_required_capabilities(self._capabilities, contract)
                ensure_license(self.container, contract)
                contract.start(self.container)
                ensure_provided_ports(self.container, contract)
                self._started.append(module_id)
            except Exception as exc:
                self._failed[module_id] = str(exc)
                if strict:
                    raise RuntimeError(f"module '{module_id}' failed to start: {exc}") from exc

    def stop(self) -> None:
        for module_id in reversed(self._started):
            self._contracts[module_id].stop(self.container)
        self._started.clear()

    def _register_settings_contribution(self, contract: ModuleContract) -> None:
        contribution = contract.settings_contribution
        if contribution is None:
            return
        if not self.container.has_port("settings_service"):
            raise RuntimeError(
                f"module '{contract.module_id}' defines settings_contribution but no settings_service exists"
            )
        settings: SettingsService = self.container.get_port("settings_service")
        settings.registry.validate_contribution(contribution)
        settings.registry.register(contribution)

    def registered_module_ids(self) -> list[str]:
        return sorted(self._contracts.keys())

    def contracts(self) -> tuple[ModuleContract, ...]:
        return tuple(self._contracts.values())

    def capability_map(self) -> dict[str, str]:
        return self._capabilities.all_capabilities()

    def failed_modules(self) -> dict[str, str]:
        return dict(self._failed)

