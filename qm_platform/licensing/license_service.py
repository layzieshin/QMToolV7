from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .license_policy import LicensePolicy
from .license_verifier import LicenseVerifier


class LicenseMissingError(RuntimeError):
    pass


class LicenseInvalidError(RuntimeError):
    pass


class LicenseExpiredError(RuntimeError):
    pass


class ModuleNotLicensedError(RuntimeError):
    pass


@dataclass
class LicenseService:
    license_file: Path
    verifier: LicenseVerifier
    policy: LicensePolicy
    _payload: dict[str, Any] | None = None

    def load_license(self) -> dict[str, Any]:
        if not self.license_file.exists():
            raise LicenseMissingError(f"missing license file: {self.license_file}")
        payload = json.loads(self.license_file.read_text(encoding="utf-8"))
        self._payload = payload
        return payload

    def validate(self) -> dict[str, Any]:
        payload = self._payload or self.load_license()
        self._validate_structure(payload)
        if not self.verifier.verify_signature(payload):
            raise LicenseInvalidError("license signature verification failed")
        if self.policy.is_expired(payload):
            raise LicenseExpiredError("license expired")
        return payload

    def is_module_allowed(self, module_tag: str) -> bool:
        payload = self.validate()
        return self.policy.is_module_allowed(payload, module_tag)

    @staticmethod
    def _validate_structure(payload: dict[str, Any]) -> None:
        required = (
            "license_id",
            "issued_to",
            "customer_id",
            "issued_at",
            "expires_at",
            "enabled_modules",
            "key_id",
            "signature",
        )
        missing = [k for k in required if k not in payload]
        if missing:
            raise LicenseInvalidError(f"license payload missing fields: {missing}")
        if not isinstance(payload.get("enabled_modules"), list):
            raise LicenseInvalidError("enabled_modules must be a list")

