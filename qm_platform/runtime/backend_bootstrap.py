"""Slim Usermanagement wiring for the backend host (AP-028 M5).

Does not start Documents/Training/Registry/Incidents or run SQLite evolution.
Forces hardened seed_mode so the backend never auto-creates admin/admin.
"""
from __future__ import annotations

import os

from modules.usermanagement import api as um_api
from modules.usermanagement.api import ensure_postgres_schema_ready
from modules.usermanagement.module import create_usermanagement_module_contract

from .container import RuntimeContainer
from .lifecycle import LifecycleManager


class BackendUsermanagementBootstrapError(RuntimeError):
    """Raised when backend Usermanagement cannot start safely."""


def _force_hardened_usermanagement_settings(container: RuntimeContainer) -> None:
    from pathlib import Path

    from qm_platform.persistence.database_evolution import (
        DatabaseEvolutionService,
        DatabaseSpec,
        MigrationStep,
    )
    from qm_platform.persistence.path_resolver import resolve_platform_settings_db_path
    from qm_platform.persistence.platform_settings_contribution import (
        PLATFORM_SETTINGS_DATABASE_CONTRIBUTION,
    )
    from qm_platform.settings.actors import SYSTEM_BACKEND_BOOTSTRAP_ACTOR
    from qm_platform.settings.persistence_bootstrap import attach_settings_persistence

    app_home = Path(container.get_port("app_home"))
    contrib = PLATFORM_SETTINGS_DATABASE_CONTRIBUTION
    evolution = DatabaseEvolutionService(app_home=app_home)
    evolution.migrate(
        (
            DatabaseSpec(
                database_id=contrib.database_id,
                path=resolve_platform_settings_db_path(app_home),
                migrations=tuple(
                    MigrationStep(
                        version=item.version,
                        name=item.name,
                        sql_path=item.sql_path,
                    )
                    for item in contrib.migrations
                ),
            ),
        ),
        reason="backend_platform_settings",
    )
    attach_settings_persistence(container, app_home=app_home)

    settings = container.get_port("settings_service")
    settings.set_module_settings(
        "usermanagement",
        {"seed_mode": "hardened", "dev_mode": False},
        actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
        acknowledge_governance_change=True,
        reason="backend_bootstrap_hardened",
    )


def _ensure_users_or_bootstrap(container: RuntimeContainer) -> None:
    """Empty user table + explicit bootstrap credentials => first admin.

    If users already exist, bootstrap env vars are ignored. After data loss that
    empties the table, the same credentials can recreate the first admin — that
    is intentional without a separate one-shot marker.
    """
    service = um_api.get_usermanagement_service(container)
    if service.list_users():
        return

    username = os.environ.get("QMTOOL_BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = os.environ.get("QMTOOL_BOOTSTRAP_ADMIN_PASSWORD", "")
    if not username or password == "":
        raise BackendUsermanagementBootstrapError(
            "backend has no users; set QMTOOL_BOOTSTRAP_ADMIN_USERNAME and "
            "QMTOOL_BOOTSTRAP_ADMIN_PASSWORD for first-admin bootstrap on an "
            "empty user table (or provision a user before starting the backend)"
        )
    if username.lower() == "admin" and password == "admin":
        raise BackendUsermanagementBootstrapError(
            "refusing insecure bootstrap credentials admin/admin"
        )
    try:
        created = um_api.bootstrap_first_admin(container, username, password)
    except um_api.WeakPasswordError as exc:
        raise BackendUsermanagementBootstrapError(
            "bootstrap password does not meet password policy"
        ) from exc
    if created is None and not service.list_users():
        raise BackendUsermanagementBootstrapError("first-admin bootstrap produced no users")


def wire_backend_usermanagement(container: RuntimeContainer) -> LifecycleManager:
    """Prepare, wire, and start only the Usermanagement module contract."""
    if not container.has_port("usermanagement_postgres_dsn"):
        raise RuntimeError("backend requires usermanagement_postgres_dsn")

    ensure_postgres_schema_ready(container)

    lifecycle = LifecycleManager(container)
    lifecycle.prepare(create_usermanagement_module_contract())
    _force_hardened_usermanagement_settings(container)
    lifecycle.wire("usermanagement")
    _ensure_users_or_bootstrap(container)
    lifecycle.start(strict=True)
    return lifecycle


def wire_backend_documents(
    container: RuntimeContainer,
    lifecycle: LifecycleManager | None = None,
) -> LifecycleManager:
    """Wire signature, registry, and documents; backend is sole documents.db owner (J04-M0).

    When ``lifecycle`` is provided (typical after ``wire_backend_usermanagement``),
    capabilities such as ``auth.authenticate`` remain available for signature.
    """
    from pathlib import Path
    from types import MappingProxyType

    from modules.documents.module import create_documents_module_contract
    from modules.documents.api import ensure_postgres_schema_ready as ensure_documents_postgres_schema_ready
    from modules.registry.api import ensure_postgres_schema_ready as ensure_registry_postgres_schema_ready
    from modules.signature.api import ensure_postgres_schema_ready as ensure_signature_postgres_schema_ready
    from modules.registry.module import create_registry_module_contract
    from modules.signature.module import create_signature_module_contract
    from qm_platform.persistence.database_evolution import (
        DATABASE_PREFLIGHT_STATUSES_PORT,
        DataValidationQuery,
        DatabaseEvolutionService,
        DatabaseSpec,
        MigrationStep,
    )
    from qm_platform.persistence.path_resolver import (
        resolve_database_absolute_path,
        resolve_platform_settings_db_path,
    )
    from qm_platform.persistence.platform_settings_contribution import (
        PLATFORM_SETTINGS_DATABASE_CONTRIBUTION,
    )

    container.register_port("documents_runtime_owner", "backend")
    container.register_port("signature_runtime_owner", "backend")
    if lifecycle is None:
        lifecycle = LifecycleManager(container)
    contracts = (
        create_signature_module_contract(),
        create_registry_module_contract(),
        create_documents_module_contract(),
    )
    for contract in contracts:
        if contract.module_id not in {c.module_id for c in lifecycle.contracts()}:
            lifecycle.prepare(contract)

    app_home = Path(container.get_port("app_home"))
    evolution = DatabaseEvolutionService(app_home=app_home)

    def _spec_for(contribution) -> DatabaseSpec:
        if contribution.database_id == PLATFORM_SETTINGS_DATABASE_CONTRIBUTION.database_id:
            path = resolve_platform_settings_db_path(app_home)
        else:
            path = resolve_database_absolute_path(app_home, contribution)
        return DatabaseSpec(
            database_id=contribution.database_id,
            path=path,
            migrations=tuple(
                MigrationStep(
                    version=migration.version,
                    name=migration.name,
                    sql_path=migration.sql_path,
                )
                for migration in contribution.migrations
            ),
            validation_queries=tuple(
                DataValidationQuery(name=query.name, sql=query.sql)
                for query in contribution.validation_queries
            ),
        )

    use_registry_postgres = (
        container.has_port("registry_postgres_dsn")
        and bool(str(container.get_port("registry_postgres_dsn")).strip())
    )
    use_documents_postgres = (
        container.has_port("documents_postgres_dsn")
        and bool(str(container.get_port("documents_postgres_dsn")).strip())
    )
    use_signature_postgres = (
        container.has_port("signature_postgres_dsn")
        and bool(str(container.get_port("signature_postgres_dsn")).strip())
    )
    if use_registry_postgres:
        ensure_registry_postgres_schema_ready(container)
    if use_documents_postgres:
        ensure_documents_postgres_schema_ready(container)
    if use_signature_postgres:
        ensure_signature_postgres_schema_ready(container)

    # Include platform_settings so pre-migrate backups with residual archive are valid.
    contributions = (
        PLATFORM_SETTINGS_DATABASE_CONTRIBUTION,
        *(c for contract in contracts for c in contract.database_contributions),
    )
    if use_registry_postgres:
        contributions = tuple(
            contribution
            for contribution in contributions
            if contribution.database_id != "registry"
        )
    if use_documents_postgres:
        contributions = tuple(
            contribution
            for contribution in contributions
            if contribution.database_id != "documents"
        )
    if use_signature_postgres:
        contributions = tuple(
            contribution
            for contribution in contributions
            if contribution.database_id != "signature"
        )
    specs = tuple(sorted((_spec_for(item) for item in contributions), key=lambda spec: spec.database_id))

    if not container.has_port(DATABASE_PREFLIGHT_STATUSES_PORT):
        preflight = {status.database_id: status for status in evolution.statuses(specs)}
        container.register_port(DATABASE_PREFLIGHT_STATUSES_PORT, MappingProxyType(preflight))

    evolution.migrate(specs, reason="backend_documents")
    for contract in contracts:
        lifecycle.wire(contract.module_id)
    lifecycle.start(strict=True)
    return lifecycle
