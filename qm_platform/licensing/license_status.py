from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from typing import TYPE_CHECKING

from .license_schema import unknown_module_tags

if TYPE_CHECKING:
    from .license_service import LicenseService


@dataclass(frozen=True)
class ModuleLicenseState:
    module_id: str
    license_tag: str
    licensed: bool
    block_reason: str | None


@dataclass(frozen=True)
class LicenseStatusReport:
    present: bool
    valid: bool
    license_type: str | None
    issued_to: str | None
    customer_id: str | None
    expires_at: str | None
    machine_id_local: str
    machine_id_source: str
    machine_id_match: bool | None
    enabled_modules: list[str]
    unknown_modules: list[str]
    module_states: list[ModuleLicenseState]
    errors: list[str] = field(default_factory=list)


def build_license_diagnostics(
    license_service: "LicenseService",
    *,
    licensed_modules: list[tuple[str, str]],
    known_tags: set[str],
) -> dict[str, Any]:
    report = license_service.get_status_report(licensed_modules=licensed_modules, known_tags=known_tags)
    checks: dict[str, Any] = {
        "license:present": report.present,
        "license:signature_valid": report.valid and not any("signature" in e.lower() for e in report.errors),
        "license:type_valid": report.license_type in ("trial", "full") if report.valid else False,
        "license:expiry_valid": report.valid and not any("expired" in e.lower() for e in report.errors),
        "license:machine_id_match": report.machine_id_match is True,
        "license:public_key_present": license_service.has_public_key_for_payload(),
        "license:enabled_modules": list(report.enabled_modules),
        "license:unknown_modules": list(report.unknown_modules),
        "license:machine_id_local": report.machine_id_local,
        "license:machine_id_source": report.machine_id_source,
        "license:errors": list(report.errors),
    }
    for state in report.module_states:
        checks[f"license:module_{state.license_tag}"] = state.licensed
    return checks
