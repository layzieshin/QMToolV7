from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .governance_critical_keys import get_governance_critical_keys
from .settings_registry import SettingsRegistry
from .settings_store import SettingsStore


@dataclass
class SettingsService:
    registry: SettingsRegistry
    store: SettingsStore

    def get_module_settings(self, module_id: str) -> dict[str, Any]:
        contribution = self.registry.get(module_id)
        defaults = contribution.defaults if contribution else {}
        all_data = self.store.load_all()
        module_data = all_data.get(module_id, {})
        result = dict(defaults)
        result.update(module_data)
        return result

    def set_module_settings(
        self,
        module_id: str,
        values: dict[str, Any],
        *,
        acknowledge_governance_change: bool = False,
    ) -> None:
        contribution = self.registry.get(module_id)
        if contribution is None:
            raise KeyError(f"unknown module settings contribution: {module_id}")
        self.registry.validate_contribution(contribution)
        governance_keys = get_governance_critical_keys(module_id)
        touched_governance_keys = sorted(set(values.keys()) & set(governance_keys))
        if touched_governance_keys and not acknowledge_governance_change:
            raise ValueError(
                "governance_critical settings require explicit acknowledge flag "
                "and release change-control"
            )
        all_data = self.store.load_all()
        all_data[module_id] = values
        self.store.save_all(all_data)

