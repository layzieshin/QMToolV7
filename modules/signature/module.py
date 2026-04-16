from __future__ import annotations

from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.sdk.module_contract import ModuleContract, SettingsContribution

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
        required_ports=["logger", "audit_logger", "event_bus", "settings_service", "usermanagement_service"],
        provided_ports=["signature_service", "signature_api"],
        required_capabilities=["auth.authenticate"],
        provided_capabilities=["signature.visual.sign", "signature.api.fixed_position"],
        settings_contribution=SIGNATURE_SETTINGS_CONTRIBUTION,
        license_tag="signature",
        register=register_signature_ports,
        start=start_signature_module,
        stop=stop_signature_module,
    )

