from __future__ import annotations

from dataclasses import dataclass

from .license_service import LicenseService, ModuleNotLicensedError


@dataclass
class LicenseGuard:
    license_service: LicenseService

    def ensure_writable_operation_allowed(self, module_tag: str) -> None:
        if not self.license_service.is_module_allowed(module_tag):
            raise ModuleNotLicensedError(f"module not licensed: {module_tag}")

