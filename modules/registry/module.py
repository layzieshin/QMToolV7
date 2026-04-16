from __future__ import annotations


from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.sdk.module_contract import ModuleContract, SettingsContribution

from .wiring import register_registry_ports


REGISTRY_SETTINGS_CONTRIBUTION = SettingsContribution(
    module_id="registry",
    schema_version=1,
    schema={
        "type": "object",
        "properties": {
            "registry_db_path": {"type": "string"},
        },
        "required": ["registry_db_path"],
        "additionalProperties": False,
    },
    defaults={"registry_db_path": "storage/documents/registry.db"},
    scope="module_global",
    migrations=[],
)



def start_registry_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("registry", "module started")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.registry.module.started.v1", "registry", {"status": "started"})
    )


def stop_registry_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("registry", "module stopped")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.registry.module.stopped.v1", "registry", {"status": "stopped"})
    )


def create_registry_module_contract() -> ModuleContract:
    return ModuleContract(
        module_id="registry",
        version="1.0.0",
        min_platform_version="1.0.0",
        max_platform_version=None,
        required_ports=["logger", "audit_logger", "event_bus", "settings_service"],
        provided_ports=["registry_service", "registry_api", "registry_projection_api"],
        required_capabilities=[],
        provided_capabilities=["documents.registry.read", "documents.registry.write"],
        settings_contribution=REGISTRY_SETTINGS_CONTRIBUTION,
        license_tag=None,
        register=register_registry_ports,
        start=start_registry_module,
        stop=stop_registry_module,
    )
