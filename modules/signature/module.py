from __future__ import annotations

from pathlib import Path

from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.sdk.module_contract import (
    DatabaseContribution,
    DatabaseMigrationContribution,
    DatabaseValidationContribution,
    ModuleContract,
    SettingsContribution,
)

from .wiring import register_signature_ports


SIGNATURE_SETTINGS_CONTRIBUTION = SettingsContribution(
    module_id="signature",
    schema_version=1,
    schema={
        "type": "object",
        "properties": {
            "require_password": {"type": "boolean"},
            "default_mode": {"type": "string"},
            "templates_db_path": {"type": "string"},
            "assets_root": {"type": "string"},
            "master_key_path": {"type": "string"},
        },
        "required": ["require_password", "default_mode", "templates_db_path", "assets_root", "master_key_path"],
        "additionalProperties": False,
    },
    defaults={
        "require_password": True,
        "default_mode": "visual",
        "templates_db_path": "storage/signature/templates.db",
        "assets_root": "storage/signature/assets",
        "master_key_path": "storage/platform/signature_master.key",
    },
    scope="module_global",
    migrations=[],
)

SIGNATURE_DATABASE_CONTRIBUTION = DatabaseContribution(
    database_id="signature",
    module_id="signature",
    setting_key="templates_db_path",
    default_path="storage/signature/templates.db",
    migrations=(
        DatabaseMigrationContribution(
            version=1,
            name="initial",
            sql_path=Path(__file__).parent / "migrations" / "0001_initial.sql",
        ),
    ),
    validation_queries=(
        DatabaseValidationContribution(
            name="invalid signature template scope",
            sql=(
                "SELECT COUNT(*) FROM user_signature_templates "
                "WHERE scope NOT IN ('user', 'global')"
            ),
        ),
    ),
)




def start_signature_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("signature", "module started")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.signature.module.started.v1", "signature", {"status": "started"})
    )


def stop_signature_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("signature", "module stopped")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.signature.module.stopped.v1", "signature", {"status": "stopped"})
    )


def create_signature_module_contract() -> ModuleContract:
    return ModuleContract(
        module_id="signature",
        version="1.0.0",
        min_platform_version="1.0.0",
        max_platform_version=None,
        required_ports=[
            "logger",
            "audit_logger",
            "event_bus",
            "app_home",
            "settings_service",
            "usermanagement_service",
        ],
        provided_ports=["signature_service", "signature_api"],
        required_capabilities=["auth.authenticate"],
        provided_capabilities=["signature.visual.sign", "signature.api.fixed_position"],
        settings_contribution=SIGNATURE_SETTINGS_CONTRIBUTION,
        license_tag=None,
        register=register_signature_ports,
        start=start_signature_module,
        stop=stop_signature_module,
        database_contributions=(SIGNATURE_DATABASE_CONTRIBUTION,),
    )

