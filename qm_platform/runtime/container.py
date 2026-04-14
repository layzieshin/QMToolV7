from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeContainer:
    _ports: dict[str, Any] = field(default_factory=dict)

    def register_port(self, port_name: str, implementation: Any) -> None:
        if not port_name or not port_name.strip():
            raise ValueError("port_name must be non-empty")
        self._ports[port_name] = implementation

    def has_port(self, port_name: str) -> bool:
        return port_name in self._ports

    def get_port(self, port_name: str) -> Any:
        if port_name not in self._ports:
            raise KeyError(f"missing port: {port_name}")
        return self._ports[port_name]

