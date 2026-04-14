from __future__ import annotations

GOVERNANCE_CRITICAL_KEYS: dict[str, frozenset[str]] = {
    "usermanagement": frozenset({"seed_mode"}),
    "documents": frozenset({"default_profile_id", "allow_custom_profiles", "profiles_file"}),
    "signature": frozenset({"require_password", "master_key_path"}),
    "training": frozenset({"quiz_master_key_path"}),
}


def get_governance_critical_keys(module_id: str) -> frozenset[str]:
    return GOVERNANCE_CRITICAL_KEYS.get(module_id, frozenset())
