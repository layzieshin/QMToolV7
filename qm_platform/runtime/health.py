from __future__ import annotations

from dataclasses import dataclass

from .lifecycle import LifecycleManager


@dataclass(frozen=True)
class HealthReport:
    ok: bool
    modules: list[str]
    required_ports: list[str]
    capabilities: dict[str, str]
    failed_modules: dict[str, str]


def build_health_report(lifecycle: LifecycleManager) -> HealthReport:
    module_ids = lifecycle.registered_module_ids()
    required_ports = ["logger", "audit_logger", "event_bus", "settings_service", "license_service"]
    container = lifecycle.container
    ok = all(container.has_port(p) for p in required_ports)
    return HealthReport(
        ok=ok,
        modules=module_ids,
        required_ports=required_ports,
        capabilities=lifecycle.capability_map(),
        failed_modules=lifecycle.failed_modules(),
    )

