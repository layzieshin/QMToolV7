from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .license_codec import decode_license_code, encode_license_code
from .license_policy import LicensePolicy
from .license_schema import (
    LICENSE_TYPE_FULL,
    LICENSE_TYPE_TRIAL,
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    normalize_enabled_modules,
    unknown_module_tags,
)
from .license_status import LicenseStatusReport, ModuleLicenseState
from .license_verifier import LicenseVerifier
from .machine_id import get_machine_id, get_machine_id_source


class LicenseMissingError(RuntimeError):
    pass


class LicenseInvalidError(RuntimeError):
    pass


class LicenseExpiredError(RuntimeError):
    pass


class LicenseTypeError(RuntimeError):
    pass


class LicenseMachineMismatchError(RuntimeError):
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

    def reload(self) -> dict[str, Any]:
        self._payload = None
        if not self.license_file.exists():
            raise LicenseMissingError(f"missing license file: {self.license_file}")
        return self.load_license()

    def validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_structure(payload)
        try:
            self.policy.validate_license_type(payload)
            self.policy.validate_expiry_rules(payload)
        except ValueError as exc:
            raise LicenseTypeError(str(exc)) from exc
        if not self.verifier.verify_signature(payload):
            raise LicenseInvalidError("license signature verification failed")
        if not self.policy.machine_id_matches(payload):
            raise LicenseMachineMismatchError(
                f"machine_id mismatch: expected {payload.get('machine_id')}, local {self.policy.local_machine_id}"
            )
        if self.policy.is_expired(payload):
            raise LicenseExpiredError("license expired")
        return payload

    def validate(self) -> dict[str, Any]:
        payload = self._payload or self.load_license()
        return self.validate_payload(payload)

    def safe_validate(self) -> dict[str, Any] | None:
        try:
            return self.validate()
        except (LicenseMissingError, LicenseInvalidError, LicenseExpiredError, LicenseTypeError, LicenseMachineMismatchError):
            return None

    def is_module_allowed(self, module_tag: str) -> bool:
        try:
            payload = self.validate()
        except (
            LicenseMissingError,
            LicenseInvalidError,
            LicenseExpiredError,
            LicenseTypeError,
            LicenseMachineMismatchError,
        ):
            return False
        return self.policy.is_module_allowed(payload, module_tag)

    def block_reason_for_module(self, module_tag: str) -> str | None:
        try:
            payload = self.validate()
        except LicenseMissingError:
            return "Keine Lizenzdatei vorhanden"
        except LicenseInvalidError:
            return "Lizenzsignatur ungültig"
        except LicenseExpiredError:
            return "Lizenz abgelaufen"
        except LicenseTypeError as exc:
            return str(exc)
        except LicenseMachineMismatchError:
            return "Maschinen-ID stimmt nicht überein"
        if not self.policy.is_module_allowed(payload, module_tag):
            return f"Modul-Tag '{module_tag}' nicht freigeschaltet"
        return None

    def import_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        validated = self.validate_payload(payload)
        self.license_file.parent.mkdir(parents=True, exist_ok=True)
        self.license_file.write_text(json.dumps(validated, indent=2, ensure_ascii=True), encoding="utf-8")
        self._payload = validated
        return validated

    def import_code(self, code: str) -> dict[str, Any]:
        payload = decode_license_code(code)
        return self.import_payload(payload)

    def import_file(self, source: Path) -> dict[str, Any]:
        payload = json.loads(source.read_text(encoding="utf-8"))
        return self.import_payload(payload)

    def encode_current_code(self) -> str:
        payload = self.validate()
        return encode_license_code(payload)

    def has_public_key_for_payload(self) -> bool:
        try:
            payload = self._payload or self.load_license()
        except LicenseMissingError:
            return False
        key_id = str(payload.get("key_id", "")).strip()
        if not key_id:
            return False
        return self.verifier.keyring.has_key(key_id)

    def get_status_report(
        self,
        *,
        licensed_modules: list[tuple[str, str]],
        known_tags: set[str],
    ) -> LicenseStatusReport:
        local_id = get_machine_id()
        source = get_machine_id_source()
        errors: list[str] = []
        present = self.license_file.exists()
        payload: dict[str, Any] | None = None
        valid = False
        machine_match: bool | None = None
        enabled: list[str] = []
        unknown: list[str] = []

        if not present:
            errors.append("license file missing")
        else:
            try:
                payload = self.validate()
                valid = True
                machine_match = True
                enabled = list(payload.get("enabled_modules", []))
                unknown = unknown_module_tags(enabled, known_tags)
            except LicenseMissingError:
                errors.append("license file missing")
            except LicenseInvalidError as exc:
                errors.append(str(exc))
                try:
                    payload = self.load_license()
                    enabled = list(payload.get("enabled_modules", []))
                except Exception:
                    payload = None
            except LicenseMachineMismatchError as exc:
                errors.append(str(exc))
                machine_match = False
                try:
                    payload = self.load_license()
                    enabled = list(payload.get("enabled_modules", []))
                except Exception:
                    payload = None
            except LicenseExpiredError as exc:
                errors.append(str(exc))
                try:
                    payload = self.load_license()
                    enabled = list(payload.get("enabled_modules", []))
                except Exception:
                    payload = None
            except LicenseTypeError as exc:
                errors.append(str(exc))
                try:
                    payload = self.load_license()
                    enabled = list(payload.get("enabled_modules", []))
                except Exception:
                    payload = None

        module_states: list[ModuleLicenseState] = []
        for module_id, tag in licensed_modules:
            reason = self.block_reason_for_module(tag)
            module_states.append(
                ModuleLicenseState(
                    module_id=module_id,
                    license_tag=tag,
                    licensed=reason is None,
                    block_reason=reason,
                )
            )

        return LicenseStatusReport(
            present=present,
            valid=valid,
            license_type=str(payload.get("license_type")) if payload else None,
            issued_to=str(payload.get("issued_to")) if payload else None,
            customer_id=str(payload.get("customer_id")) if payload else None,
            expires_at=payload.get("expires_at") if payload else None,
            machine_id_local=local_id,
            machine_id_source=source,
            machine_id_match=machine_match,
            enabled_modules=enabled,
            unknown_modules=unknown,
            module_states=module_states,
            errors=errors,
        )

    @staticmethod
    def _validate_structure(payload: dict[str, Any]) -> None:
        missing = [k for k in REQUIRED_FIELDS if k not in payload]
        if missing:
            raise LicenseInvalidError(f"license payload missing fields: {missing}")
        if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
            raise LicenseInvalidError(f"unsupported schema_version: {payload.get('schema_version')}")
        if not isinstance(payload.get("enabled_modules"), list):
            raise LicenseInvalidError("enabled_modules must be a list")
        license_type = str(payload.get("license_type", "")).strip().lower()
        if license_type == LICENSE_TYPE_FULL and payload.get("expires_at") is None:
            return
        if license_type == LICENSE_TYPE_TRIAL and not str(payload.get("expires_at", "")).strip():
            raise LicenseInvalidError("trial license requires expires_at")
