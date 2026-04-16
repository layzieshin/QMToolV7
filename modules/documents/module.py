from __future__ import annotations


from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.sdk.module_contract import ModuleContract, SettingsContribution

from .wiring import register_documents_ports


DOCUMENTS_SETTINGS_CONTRIBUTION = SettingsContribution(
    module_id="documents",
    schema_version=1,
    schema={
        "type": "object",
        "properties": {
            "default_profile_id": {"type": "string"},
            "allow_custom_profiles": {"type": "boolean"},
            "profiles_file": {"type": "string"},
            "documents_db_path": {"type": "string"},
            "artifacts_root": {"type": "string"},
        },
        "required": ["default_profile_id", "allow_custom_profiles", "profiles_file", "documents_db_path", "artifacts_root"],
        "additionalProperties": False,
    },
    defaults={
        "default_profile_id": "long_release",
        "allow_custom_profiles": True,
        "profiles_file": "modules/documents/workflow_profiles.json",
        "documents_db_path": "storage/documents/documents.db",
        "artifacts_root": "storage/documents/artifacts",
    },
    scope="module_global",
    migrations=[],
)



def start_documents_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("documents", "module started")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.documents.module.started.v1", "documents", {"status": "started"})
    )


def stop_documents_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("documents", "module stopped")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.documents.module.stopped.v1", "documents", {"status": "stopped"})
    )


def create_documents_module_contract() -> ModuleContract:
    return ModuleContract(
        module_id="documents",
        version="1.0.0",
        min_platform_version="1.0.0",
        max_platform_version=None,
        required_ports=[
            "logger",
            "audit_logger",
            "event_bus",
            "settings_service",
            "license_service",
            "signature_api",
            "registry_projection_api",
        ],
        provided_ports=["documents_service", "documents_pool_api", "documents_workflow_api"],
        required_capabilities=[],
        provided_capabilities=["documents.workflow.manage", "documents.version.manage"],
        settings_contribution=DOCUMENTS_SETTINGS_CONTRIBUTION,
        license_tag="documents",
        register=register_documents_ports,
        start=start_documents_module,
        stop=stop_documents_module,
    )

