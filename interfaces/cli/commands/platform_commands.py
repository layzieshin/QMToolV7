from __future__ import annotations

from qm_platform.licensing.license_guard import LicenseGuard
from qm_platform.licensing.license_service import (
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseMissingError,
)
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.runtime.health import build_health_report

from interfaces.cli.bootstrap import build_container


def cmd_health() -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    report = build_health_report(lifecycle)
    logger: LoggerService = container.get_port("logger")
    logger.info("cli", "health check executed", {"ok": report.ok, "modules": report.modules})
    state = "OK" if report.ok else "FAILED"
    print(f"{state}: platform health")
    print(f"Modules: {', '.join(report.modules) if report.modules else '-'}")
    caps = ", ".join(sorted(report.capabilities.keys())) if report.capabilities else "-"
    print(f"Capabilities: {caps}")
    if report.failed_modules:
        print(f"FailedModules: {report.failed_modules}")
    return 0


def cmd_license_check(module: str) -> int:
    container = build_container()
    guard: LicenseGuard = container.get_port("license_guard")
    try:
        guard.ensure_writable_operation_allowed(module)
    except (LicenseMissingError, LicenseInvalidError, LicenseExpiredError, RuntimeError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"OK: module '{module}' is licensed")
    return 0

