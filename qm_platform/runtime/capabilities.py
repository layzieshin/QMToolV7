from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapabilityRegistry:
    _providers: dict[str, str] = field(default_factory=dict)

    def register(self, module_id: str, capabilities: list[str]) -> None:
        for cap in capabilities:
            if cap in self._providers and self._providers[cap] != module_id:
                raise ValueError(f"capability '{cap}' already provided by '{self._providers[cap]}'")
            self._providers[cap] = module_id

    def has(self, capability: str) -> bool:
        return capability in self._providers

    def provider_of(self, capability: str) -> str | None:
        return self._providers.get(capability)

    def all_capabilities(self) -> dict[str, str]:
        return dict(self._providers)

