"""License issue presets for the internal issuer GUI."""
from __future__ import annotations

from dataclasses import dataclass

from tools.internal_license_issuer.validators import trial_expires_at_days


@dataclass(frozen=True)
class LicensePreset:
    preset_id: str
    label: str
    license_type: str
    expires_at: str | None
    enabled_modules: list[str] | None  # None = use all checked in UI


PRESETS: tuple[LicensePreset, ...] = (
    LicensePreset("empty", "Leer", "trial", None, None),
    LicensePreset("trial_30", "Trial 30 Tage", "trial", trial_expires_at_days(30), None),
    LicensePreset("trial_90", "Trial 90 Tage", "trial", trial_expires_at_days(90), None),
    LicensePreset("full", "Voll-Lizenz", "full", None, None),
    LicensePreset(
        "training_trial_30",
        "Nur Training Trial 30 Tage",
        "trial",
        trial_expires_at_days(30),
        ["training"],
    ),
)


def preset_by_id(preset_id: str) -> LicensePreset | None:
    for preset in PRESETS:
        if preset.preset_id == preset_id:
            return preset
    return None
