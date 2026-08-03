"""Expected Bucket-B / Bucket-C key sets from registry + classification."""

from __future__ import annotations

from typing import Any

from qm_platform.settings.key_classification import (
    SettingBucket,
    SettingKeyRef,
    TECHNICAL_KEYS,
    RESIDUAL_POLICY_KEYS,
    classify_key,
)
from qm_platform.settings.settings_registry import SettingsRegistry


def contribution_key_refs(registry: SettingsRegistry) -> set[SettingKeyRef]:
    found: set[SettingKeyRef] = set()
    for module_id in registry.list_module_ids():
        contribution = registry.get(module_id)
        if contribution is None:
            continue
        props = (contribution.schema or {}).get("properties") or {}
        for key in props:
            found.add(SettingKeyRef(module_id, str(key)))
        for key in contribution.defaults or {}:
            found.add(SettingKeyRef(module_id, str(key)))
    return found


def expected_technical_keys_by_module(registry: SettingsRegistry) -> dict[str, tuple[str, ...]]:
    """All Bucket-B keys for registered modules (schema ∪ defaults ∩ TECHNICAL)."""
    out: dict[str, list[str]] = {}
    for ref in TECHNICAL_KEYS:
        if registry.get(ref.module_id) is None:
            continue
        out.setdefault(ref.module_id, []).append(ref.setting_key)
    return {module_id: tuple(sorted(keys)) for module_id, keys in sorted(out.items())}


def expected_residual_keys_by_module(registry: SettingsRegistry) -> dict[str, tuple[str, ...]]:
    """All Bucket-C keys for registered modules (schema ∪ defaults ∩ RESIDUAL)."""
    out: dict[str, list[str]] = {}
    for ref in RESIDUAL_POLICY_KEYS:
        if registry.get(ref.module_id) is None:
            continue
        out.setdefault(ref.module_id, []).append(ref.setting_key)
    return {module_id: tuple(sorted(keys)) for module_id, keys in sorted(out.items())}


def build_complete_bucket_b_payloads(
    registry: SettingsRegistry,
    overrides_by_module: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Defaults ⊕ overrides for every registered module that has Bucket-B keys."""
    overrides_by_module = overrides_by_module or {}
    payloads: dict[str, dict[str, Any]] = {}
    for module_id, keys in expected_technical_keys_by_module(registry).items():
        contribution = registry.get(module_id)
        if contribution is None:
            continue
        defaults = contribution.defaults or {}
        complete: dict[str, Any] = {}
        for key in keys:
            if key in defaults and classify_key(module_id, key) is SettingBucket.TECHNICAL:
                complete[key] = defaults[key]
        complete.update(overrides_by_module.get(module_id) or {})
        missing = [key for key in keys if key not in complete]
        if missing:
            raise ValueError(
                f"incomplete Bucket-B seed for {module_id}: missing {missing}"
            )
        payloads[module_id] = complete
    return payloads


def build_complete_bucket_c_payloads_from_defaults(
    registry: SettingsRegistry,
) -> dict[str, dict[str, Any]]:
    """Fresh-install-only: all expected C keys from contribution defaults."""
    payloads: dict[str, dict[str, Any]] = {}
    for module_id, keys in expected_residual_keys_by_module(registry).items():
        contribution = registry.get(module_id)
        if contribution is None:
            continue
        defaults = contribution.defaults or {}
        blob: dict[str, Any] = {}
        missing: list[str] = []
        for key in keys:
            if key not in defaults:
                missing.append(key)
            else:
                blob[key] = defaults[key]
        if missing:
            raise ValueError(
                f"incomplete Bucket-C defaults for fresh residual seed of {module_id}: {missing}"
            )
        payloads[module_id] = blob
    return payloads
