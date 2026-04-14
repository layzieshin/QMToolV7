from __future__ import annotations

from dataclasses import dataclass, field

from ..sdk.module_contract import SettingsContribution


@dataclass
class SettingsRegistry:
    _contributions: dict[str, SettingsContribution] = field(default_factory=dict)

    def register(self, contribution: SettingsContribution) -> None:
        if contribution.module_id in self._contributions:
            raise ValueError(f"settings contribution already exists: {contribution.module_id}")
        self._contributions[contribution.module_id] = contribution

    def get(self, module_id: str) -> SettingsContribution | None:
        return self._contributions.get(module_id)

    def list_module_ids(self) -> list[str]:
        return sorted(self._contributions.keys())

    def validate_contribution(self, contribution: SettingsContribution) -> None:
        if not contribution.schema:
            raise ValueError("settings schema must not be empty")
        if not isinstance(contribution.defaults, dict):
            raise ValueError("settings defaults must be a dict")

