from __future__ import annotations

from ..sdk.module_contract import ModuleContract
from .versions import is_platform_compatible


def validate_contract(contract: ModuleContract) -> None:
    if not contract.module_id or not contract.module_id.strip():
        raise ValueError("module_id must be non-empty")
    if contract.module_id.lower() != contract.module_id:
        raise ValueError("module_id must be lowercase")
    if not contract.version or not contract.version.strip():
        raise ValueError("version must be non-empty")
    if not contract.min_platform_version or not contract.min_platform_version.strip():
        raise ValueError("min_platform_version must be non-empty")
    compat = is_platform_compatible(contract.min_platform_version, contract.max_platform_version)
    if not compat.ok:
        raise ValueError(f"incompatible module contract '{contract.module_id}': {compat.reason}")

