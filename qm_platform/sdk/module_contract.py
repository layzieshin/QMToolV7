from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]
LifecycleFn = Callable[[Any], None]


@dataclass(frozen=True)
class SettingsContribution:
    module_id: str
    schema_version: int
    schema: dict[str, Any]
    defaults: dict[str, Any]
    scope: str  # global | module_global | user | user_module
    migrations: list[MigrationFn]


@dataclass(frozen=True)
class ModuleContract:
    module_id: str
    version: str
    min_platform_version: str
    max_platform_version: str | None
    required_ports: list[str]
    provided_ports: list[str]
    required_capabilities: list[str]
    provided_capabilities: list[str]
    settings_contribution: Optional[SettingsContribution]
    license_tag: Optional[str]
    register: LifecycleFn
    start: LifecycleFn
    stop: LifecycleFn

