"""J02 classification completeness: schema ∪ defaults must equal A ∪ B ∪ C."""

from __future__ import annotations

from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.settings.key_classification import (
    SettingKeyRef,
    all_classified_keys,
    assert_partitions_disjoint,
    unknown_keys,
)
from qm_platform.settings.residual_allowlist import assert_residual_allowlist_complete


def _contribution_keys() -> set[SettingKeyRef]:
    found: set[SettingKeyRef] = set()
    for contract in runtime_bootstrap.all_module_contracts():
        contribution = contract.settings_contribution
        if contribution is None:
            continue
        props = (contribution.schema or {}).get("properties") or {}
        for key in props:
            found.add(SettingKeyRef(contribution.module_id, str(key)))
        for key in contribution.defaults or {}:
            found.add(SettingKeyRef(contribution.module_id, str(key)))
    return found


def test_partitions_are_disjoint_and_residual_allowlist_matches() -> None:
    assert_partitions_disjoint()
    assert_residual_allowlist_complete()


def test_classification_covers_all_contribution_schema_and_default_keys() -> None:
    found = _contribution_keys()
    classified = all_classified_keys()
    missing = sorted((found - classified), key=lambda item: item.as_tuple())
    extra = sorted((classified - found), key=lambda item: item.as_tuple())
    assert not missing, f"unclassified contribution keys: {[k.as_tuple() for k in missing]}"
    assert not extra, f"classified keys absent from contributions: {[k.as_tuple() for k in extra]}"
    assert unknown_keys(found) == []
