"""Settings sections package — split from settings_view.py (Track A SRP)."""
from .profile_section import ProfileWidget
from .module_settings_section import ModuleSettingsWidget
from .signature_settings_section import SignatureSettingsWidget
from .license_section import LicenseManagementWidget
from .planned_options_section import PlannedOptionsWidget
from .training_settings_section import TrainingSettingsWidget

__all__ = [
    "ProfileWidget",
    "ModuleSettingsWidget",
    "SignatureSettingsWidget",
    "LicenseManagementWidget",
    "PlannedOptionsWidget",
    "TrainingSettingsWidget",
]

