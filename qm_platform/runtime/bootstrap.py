from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules.documents.module import create_documents_module_contract
from modules.incident_management.module import create_incident_management_module_contract
from modules.registry.module import create_registry_module_contract
from modules.signature.module import create_signature_module_contract
from modules.training.module import create_training_module_contract
from modules.usermanagement.module import create_usermanagement_module_contract

from ..persistence.database_evolution import (
    DataValidationQuery,
    DatabaseEvolutionService,
    DatabaseSpec,
    MigrationStep,
)
from ..runtime.paths import resolve_home_path
from ..sdk.module_contract import ModuleContract
from ..settings.settings_service import SettingsService
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
        create_incident_management_module_contract(),
    ]


def core_license_tags() -> list[str]:
    tags = {contract.license_tag for contract in core_module_contracts() if contract.license_tag}
    return sorted(str(tag) for tag in tags)


def core_licensed_modules() -> list[tuple[str, str]]:
    return [
        (contract.module_id, str(contract.license_tag))
        for contract in core_module_contracts()
        if contract.license_tag
    ]


def register_core_modules(container: RuntimeContainer) -> LifecycleManager:
    lifecycle = prepare_core_modules(container)
    activate_core_modules(container, lifecycle)
    return lifecycle


def prepare_core_modules(container: RuntimeContainer) -> LifecycleManager:
    lifecycle = LifecycleManager(container)
    for contract in core_module_contracts():
        lifecycle.prepare(contract)
    return lifecycle


def core_database_specs(
    container: RuntimeContainer,
    lifecycle: LifecycleManager,
) -> tuple[DatabaseSpec, ...]:
    app_home = Path(container.get_port("app_home"))
    settings: SettingsService = container.get_port("settings_service")
    specs: list[DatabaseSpec] = []
    for contract in lifecycle.contracts():
        module_settings = settings.get_module_settings(contract.module_id)
        for contribution in contract.database_contributions:
            raw_path = str(
                module_settings.get(
                    contribution.setting_key,
                    contribution.default_path,
                )
            )
            specs.append(
                DatabaseSpec(
                    database_id=contribution.database_id,
                    path=resolve_home_path(app_home, raw_path),
                    migrations=tuple(
                        MigrationStep(
                            version=migration.version,
                            name=migration.name,
                            sql_path=migration.sql_path,
                        )
                        for migration in contribution.migrations
                    ),
                    validation_queries=tuple(
                        DataValidationQuery(
                            name=query.name,
                            sql=query.sql,
                        )
                        for query in contribution.validation_queries
                    ),
                )
            )
    return tuple(sorted(specs, key=lambda spec: spec.database_id))


def configure_database_evolution(
    container: RuntimeContainer,
    lifecycle: LifecycleManager,
) -> tuple[DatabaseEvolutionService, tuple[DatabaseSpec, ...]]:
    app_home = Path(container.get_port("app_home"))
    service = DatabaseEvolutionService(app_home=app_home)
    specs = core_database_specs(container, lifecycle)
    container.register_port("database_evolution_service", service)
    container.register_port("database_specs", specs)
    return service, specs


def activate_core_modules(
    container: RuntimeContainer,
    lifecycle: LifecycleManager,
) -> None:
    service, specs = configure_database_evolution(container, lifecycle)
    service.migrate(specs, reason="runtime_preflight")
    lifecycle.wire_all()

