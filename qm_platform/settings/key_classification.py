"""Machine-complete J02 settings key partition: bootstrap / technical / residual policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class SettingBucket(str, Enum):
    BOOTSTRAP = "bootstrap"
    TECHNICAL = "technical"
    RESIDUAL_POLICY = "residual_policy"


@dataclass(frozen=True)
class SettingKeyRef:
    module_id: str
    setting_key: str

    def as_tuple(self) -> tuple[str, str]:
        return (self.module_id, self.setting_key)


# Bucket A — bootstrap paths / start parameters (never platform_settings, never residual).
BOOTSTRAP_KEYS: frozenset[SettingKeyRef] = frozenset(
    {
        SettingKeyRef("usermanagement", "users_db_path"),
        SettingKeyRef("documents", "documents_db_path"),
        SettingKeyRef("documents", "artifacts_root"),
        SettingKeyRef("documents", "profiles_file"),
        SettingKeyRef("registry", "registry_db_path"),
        SettingKeyRef("signature", "templates_db_path"),
        SettingKeyRef("signature", "assets_root"),
        SettingKeyRef("signature", "master_key_path"),
        SettingKeyRef("training", "training_db_path"),
        SettingKeyRef("training", "quiz_blob_root"),
        SettingKeyRef("training", "quiz_master_key_path"),
        SettingKeyRef("incident_management", "incident_db_path"),
        SettingKeyRef("incident_management", "artifacts_root"),
    }
)

# Bucket B — technical / flexible settings imported into platform_settings.
TECHNICAL_KEYS: frozenset[SettingKeyRef] = frozenset(
    {
        SettingKeyRef("usermanagement", "seed_mode"),
        SettingKeyRef("usermanagement", "dev_mode"),
        SettingKeyRef("signature", "require_password"),
        SettingKeyRef("signature", "default_mode"),
        SettingKeyRef("training", "questions_per_quiz"),
        SettingKeyRef("training", "min_correct_answers"),
        SettingKeyRef("training", "shuffle_answers"),
        SettingKeyRef("training", "retry_cooldown_seconds"),
        SettingKeyRef("training", "force_reread_on_fail"),
        SettingKeyRef("documents", "logs_backup_reminder_days"),
    }
)

# Bucket C — fachliche policies; residual JSON allowlist only until owner packages.
RESIDUAL_POLICY_KEYS: frozenset[SettingKeyRef] = frozenset(
    {
        SettingKeyRef("documents", "doc_type_profile_rules"),
        SettingKeyRef("documents", "can_create_new_documents"),
        SettingKeyRef("documents", "default_profile_id"),
        SettingKeyRef("documents", "allow_custom_profiles"),
        SettingKeyRef("incident_management", "criticality_groups"),
        SettingKeyRef("incident_management", "standard_deadlines"),
        SettingKeyRef("incident_management", "effectiveness_delay"),
        SettingKeyRef("incident_management", "capa_required_rules"),
        SettingKeyRef("incident_management", "report_templates"),
        SettingKeyRef("incident_management", "categories"),
        SettingKeyRef("incident_management", "label_groups"),
        SettingKeyRef("usermanagement", "password_policy"),
    }
)


def all_classified_keys() -> frozenset[SettingKeyRef]:
    return BOOTSTRAP_KEYS | TECHNICAL_KEYS | RESIDUAL_POLICY_KEYS


def classify_key(module_id: str, setting_key: str) -> SettingBucket | None:
    ref = SettingKeyRef(module_id, setting_key)
    if ref in BOOTSTRAP_KEYS:
        return SettingBucket.BOOTSTRAP
    if ref in TECHNICAL_KEYS:
        return SettingBucket.TECHNICAL
    if ref in RESIDUAL_POLICY_KEYS:
        return SettingBucket.RESIDUAL_POLICY
    return None


def assert_partitions_disjoint() -> None:
    overlap_ab = BOOTSTRAP_KEYS & TECHNICAL_KEYS
    overlap_ac = BOOTSTRAP_KEYS & RESIDUAL_POLICY_KEYS
    overlap_bc = TECHNICAL_KEYS & RESIDUAL_POLICY_KEYS
    if overlap_ab or overlap_ac or overlap_bc:
        raise AssertionError(
            "settings key partitions overlap: "
            f"A∩B={sorted(r.as_tuple() for r in overlap_ab)} "
            f"A∩C={sorted(r.as_tuple() for r in overlap_ac)} "
            f"B∩C={sorted(r.as_tuple() for r in overlap_bc)}"
        )


def unknown_keys(keys: Iterable[SettingKeyRef]) -> list[SettingKeyRef]:
    classified = all_classified_keys()
    return sorted(
        (key for key in keys if key not in classified),
        key=lambda item: item.as_tuple(),
    )


assert_partitions_disjoint()
