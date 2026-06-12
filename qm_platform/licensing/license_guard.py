from __future__ import annotations

from dataclasses import dataclass

from .license_service import LicenseService, ModuleNotLicensedError


@dataclass
class LicenseGuard:
    license_service: LicenseService

    def ensure_module_allowed(self, module_tag: str) -> None:
        if not self.license_service.is_module_allowed(module_tag):
            reason = self.license_service.block_reason_for_module(module_tag)
            raise ModuleNotLicensedError(reason or f"module not licensed: {module_tag}")

    def ensure_writable_operation_allowed(self, module_tag: str) -> None:
        """Deprecated alias — module lock applies to all operations."""
        self.ensure_module_allowed(module_tag)

    def block_reason_for_module(self, module_tag: str) -> str | None:
        return self.license_service.block_reason_for_module(module_tag)
