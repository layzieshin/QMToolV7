"""Stable domain errors for J02 settings write/partition failures."""

from __future__ import annotations


class SettingsDomainError(ValueError):
    """Base class for settings domain failures with a stable code."""

    code: str = "settings_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BootstrapSettingImmutableError(SettingsDomainError):
    code = "bootstrap_setting_immutable"


class ResidualPolicyReadonlyError(SettingsDomainError):
    code = "residual_policy_readonly"


class UnknownSettingKeyError(SettingsDomainError):
    code = "unknown_setting_key"


class MissingRequiredSettingError(SettingsDomainError):
    code = "missing_required_setting"


class SettingsActorRequiredError(SettingsDomainError):
    code = "settings_actor_required"


class SettingsOverlapError(SettingsDomainError):
    code = "settings_db_residual_overlap"


class ResidualArchiveIntegrityError(SettingsDomainError):
    code = "residual_archive_integrity"


class ResidualArchiveMissingError(SettingsDomainError):
    code = "residual_archive_missing"


class ResidualPolicyMissingError(SettingsDomainError):
    code = "residual_policy_missing"


class ResidualPolicyUnknownError(SettingsDomainError):
    code = "residual_policy_unknown"


class ResidualPolicyInvalidError(SettingsDomainError):
    code = "residual_policy_invalid"


class SettingsCutoverIncompleteError(SettingsDomainError):
    code = "settings_cutover_incomplete"


class BucketBIncompleteError(SettingsDomainError):
    code = "settings_bucket_b_incomplete"


class SettingsSchemaInvalidError(SettingsDomainError):
    code = "settings_schema_invalid"
