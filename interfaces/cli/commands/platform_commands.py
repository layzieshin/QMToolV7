from __future__ import annotations

import json

from qm_platform.licensing.license_guard import LicenseGuard
from qm_platform.licensing.license_service import (
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseMachineMismatchError,
    LicenseMissingError,
    LicenseTypeError,
    ModuleNotLicensedError,
)
from qm_platform.licensing.license_status import build_license_diagnostics
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.runtime.health import build_health_report

from interfaces.cli.bootstrap import build_container


def cmd_health() -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start(strict=False)
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


def cmd_license_check(module: str | None = None, *, verbose: bool = False) -> int:
    container = build_container()
    license_service = container.get_port("license_service")
    guard: LicenseGuard = container.get_port("license_guard")
    licensed = runtime_bootstrap.core_licensed_modules()
    known = set(runtime_bootstrap.core_license_tags())
    diagnostics = build_license_diagnostics(
        license_service,
        licensed_modules=licensed,
        known_tags=known,
    )
    if verbose:
        print(json.dumps(diagnostics, ensure_ascii=True, indent=2))
    if module:
        try:
            guard.ensure_module_allowed(module)
        except (
            LicenseMissingError,
            LicenseInvalidError,
            LicenseExpiredError,
            LicenseTypeError,
            LicenseMachineMismatchError,
            ModuleNotLicensedError,
            RuntimeError,
        ) as exc:
            print(f"BLOCKED: {exc}")
            return 2
        print(f"OK: module '{module}' is licensed")
        return 0
    ok = all(
        diagnostics.get(key) is True
        for key in (
            "license:signature_valid",
            "license:type_valid",
            "license:expiry_valid",
            "license:machine_id_match",
            "license:public_key_present",
        )
        if diagnostics.get("license:present")
    ) or not diagnostics.get("license:present")
    if diagnostics.get("license:unknown_modules"):
        print(f"WARN: unknown module tags: {diagnostics['license:unknown_modules']}")
    if not diagnostics.get("license:present"):
        print("WARN: no license file present (app may run; licensed modules blocked)")
        return 0
    if not ok:
        print("BLOCKED: license diagnostics failed")
        if not verbose:
            print(json.dumps(diagnostics, ensure_ascii=True, indent=2))
        return 2
    print("OK: license diagnostics passed")
    return 0


def cmd_logs_backup(actor: str = "cli-admin") -> int:
    container = build_container()
    backup_service = container.get_port("log_backup_service")
    result = backup_service.create_backup(actor=actor)
    print(f"OK: backup created at {result.zip_path}")
    print(f"Audit lines: {result.audit_lines}")
    print(f"Platform lines: {result.platform_lines}")
    print(f"Cutoff UTC: {result.cutoff_utc.isoformat()}")
    return 0
