from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from modules.documents.module import create_documents_module_contract
from modules.incident_management.module import create_incident_management_module_contract
from modules.registry.module import create_registry_module_contract
from modules.signature.module import create_signature_module_contract
from modules.training.module import create_training_module_contract
from modules.usermanagement.module import create_usermanagement_module_contract
from modules.container.module import create_container_module_contract

from ..persistence.database_evolution import (
    DataValidationQuery,
    DatabaseEvolutionService,
    DatabaseSpec,
    MigrationStep,
)
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


def backend_module_contracts() -> list[ModuleContract]:
    """Backend-only contracts; intentionally excluded from desktop composition."""
    return [create_container_module_contract()]


def all_module_contracts() -> list[ModuleContract]:
    return [*core_module_contracts(), *backend_module_contracts()]


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
    """Build all AP-027 specs from bootstrap path resolution — never SettingsService."""
    from qm_platform.persistence.path_resolver import resolve_database_absolute_path
    from qm_platform.persistence.platform_settings_contribution import (
        PLATFORM_SETTINGS_DATABASE_CONTRIBUTION,
    )

    app_home = Path(container.get_port("app_home"))
    contributions = []
    for contract in lifecycle.contracts():
        contributions.extend(contract.database_contributions)
    contributions.append(PLATFORM_SETTINGS_DATABASE_CONTRIBUTION)

    specs: list[DatabaseSpec] = []
    for contribution in contributions:
        specs.append(
            DatabaseSpec(
                database_id=contribution.database_id,
                path=resolve_database_absolute_path(app_home, contribution),
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


def capture_database_preflight_statuses(
    container: RuntimeContainer,
    service: DatabaseEvolutionService,
    specs: tuple[DatabaseSpec, ...],
) -> MappingProxyType:
    """Register immutable pre-migrate DatabaseStatus map for module wiring.

    Platform-only helper: no module-specific classification or Documents imports.
    Must run before migrate so freshly created DB files are not misread later.
    """
    from qm_platform.persistence.database_evolution import DATABASE_PREFLIGHT_STATUSES_PORT

    preflight = {status.database_id: status for status in service.statuses(specs)}
    mapping = MappingProxyType(preflight)
    container.register_port(DATABASE_PREFLIGHT_STATUSES_PORT, mapping)
    return mapping


def activate_core_modules(
    container: RuntimeContainer,
    lifecycle: LifecycleManager,
) -> None:
    service, specs = configure_database_evolution(container, lifecycle)
    capture_database_preflight_statuses(container, service, specs)
    service.migrate(specs, reason="runtime_preflight")
    from qm_platform.settings.persistence_bootstrap import (
        attach_settings_persistence,
        refresh_backup_reminder_from_settings,
    )

    attach_settings_persistence(container)
    refresh_backup_reminder_from_settings(container)
    lifecycle.wire_all()
