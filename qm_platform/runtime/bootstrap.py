from __future__ import annotations

from dataclasses import dataclass

from modules.documents.module import create_documents_module_contract
from modules.registry.module import create_registry_module_contract
from modules.signature.module import create_signature_module_contract
from modules.training.module import create_training_module_contract
from modules.usermanagement.module import create_usermanagement_module_contract

from ..sdk.module_contract import ModuleContract
from .container import RuntimeContainer
from .lifecycle import LifecycleManager


@dataclass
class BootstrapResult:
    container: RuntimeContainer
    lifecycle: LifecycleManager


def core_module_contracts() -> list[ModuleContract]:
    return [
        create_usermanagement_module_contract(),
        create_signature_module_contract(),
        create_registry_module_contract(),
        create_documents_module_contract(),
        create_training_module_contract(),
    ]


def core_license_tags() -> list[str]:
    tags = {contract.license_tag for contract in core_module_contracts() if contract.license_tag}
    return sorted(str(tag) for tag in tags)


def register_core_modules(container: RuntimeContainer) -> LifecycleManager:
    lifecycle = LifecycleManager(container)
    for contract in core_module_contracts():
        lifecycle.register(contract)
    return lifecycle

