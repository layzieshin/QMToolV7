from __future__ import annotations

from qm_platform.licensing.license_service import LicenseService
from qm_platform.runtime.capabilities import CapabilityRegistry
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.sdk.module_contract import ModuleContract


def ensure_required_ports(container: RuntimeContainer, contract: ModuleContract) -> None:
    missing = [port for port in contract.required_ports if not container.has_port(port)]
    if missing:
        raise RuntimeError(f"module '{contract.module_id}' missing ports: {missing}")


def ensure_required_capabilities(capabilities: CapabilityRegistry, contract: ModuleContract) -> None:
    missing = [cap for cap in contract.required_capabilities if not capabilities.has(cap)]
    if missing:
        raise RuntimeError(f"module '{contract.module_id}' missing capabilities: {missing}")


def ensure_provided_ports(container: RuntimeContainer, contract: ModuleContract) -> None:
    missing = [port for port in contract.provided_ports if not container.has_port(port)]
    if missing:
        raise RuntimeError(f"module '{contract.module_id}' did not provide ports: {missing}")


def ensure_license(container: RuntimeContainer, contract: ModuleContract) -> None:
    if not contract.license_tag:
        return
    if not container.has_port("license_service"):
        raise RuntimeError(
            f"module '{contract.module_id}' requires license_tag but no license_service is registered"
        )
    license_service: LicenseService = container.get_port("license_service")
    if not license_service.is_module_allowed(contract.license_tag):
        raise RuntimeError(
            f"module '{contract.module_id}' blocked by license tag '{contract.license_tag}'"
        )
