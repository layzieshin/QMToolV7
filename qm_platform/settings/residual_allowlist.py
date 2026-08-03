"""Explicit residual Bucket-C allowlist: owner + follow-up package per key."""

from __future__ import annotations

from dataclasses import dataclass

from .key_classification import RESIDUAL_POLICY_KEYS, SettingKeyRef


@dataclass(frozen=True)
class ResidualAllowlistEntry:
    key: SettingKeyRef
    owner: str
    follow_up_package: str


RESIDUAL_ALLOWLIST: frozenset[ResidualAllowlistEntry] = frozenset(
    {
        ResidualAllowlistEntry(
            SettingKeyRef("documents", "doc_type_profile_rules"),
            "documents",
            "J03+",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("documents", "can_create_new_documents"),
            "documents",
            "J03+",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("documents", "default_profile_id"),
            "documents",
            "J03+",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("documents", "allow_custom_profiles"),
            "documents",
            "J03+",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("incident_management", "criticality_groups"),
            "incident_management",
            "J07/OQ-08",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("incident_management", "standard_deadlines"),
            "incident_management",
            "J07/OQ-08",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("incident_management", "effectiveness_delay"),
            "incident_management",
            "J07/OQ-08",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("incident_management", "capa_required_rules"),
            "incident_management",
            "J07/OQ-08",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("incident_management", "report_templates"),
            "incident_management",
            "J07/OQ-08",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("incident_management", "categories"),
            "incident_management",
            "J07/OQ-08",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("incident_management", "label_groups"),
            "incident_management",
            "J07/OQ-08",
        ),
        ResidualAllowlistEntry(
            SettingKeyRef("usermanagement", "password_policy"),
            "usermanagement",
            "security-policy-package",
        ),
    }
)


def residual_allowlist_keys() -> frozenset[SettingKeyRef]:
    return frozenset(entry.key for entry in RESIDUAL_ALLOWLIST)


def assert_residual_allowlist_complete() -> None:
    keys = residual_allowlist_keys()
    missing = RESIDUAL_POLICY_KEYS - keys
    extra = keys - RESIDUAL_POLICY_KEYS
    if missing or extra:
        raise AssertionError(
            "residual allowlist mismatch: "
            f"missing={sorted(k.as_tuple() for k in missing)} "
            f"extra={sorted(k.as_tuple() for k in extra)}"
        )


assert_residual_allowlist_complete()
