from __future__ import annotations


from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.sdk.module_contract import ModuleContract, SettingsContribution

from .wiring import register_training_ports


TRAINING_SETTINGS_CONTRIBUTION = SettingsContribution(
    module_id="training",
    schema_version=1,
    schema={
        "type": "object",
        "properties": {
            "training_db_path": {"type": "string"},
            "quiz_blob_root": {"type": "string"},
            "quiz_master_key_path": {"type": "string"},
        },
        "required": ["training_db_path", "quiz_blob_root", "quiz_master_key_path"],
        "additionalProperties": False,
    },
    defaults={
        "training_db_path": "storage/training/training.db",
        "quiz_blob_root": "storage/training/quiz_blobs",
        "quiz_master_key_path": "storage/platform/training_quiz_master.key",
    },
    scope="module_global",
    migrations=[],
)



def start_training_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("training", "module started")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.training.module.started.v1", "training", {"status": "started"})
    )


def stop_training_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("training", "module stopped")
    container.get_port("event_bus").publish(
        EventEnvelope.create("domain.training.module.stopped.v1", "training", {"status": "stopped"})
    )


def create_training_module_contract() -> ModuleContract:
    return ModuleContract(
        module_id="training",
        version="1.0.0",
        min_platform_version="1.0.0",
        max_platform_version=None,
        required_ports=[
            "logger",
            "audit_logger",
            "event_bus",
            "settings_service",
            "documents_pool_api",
            "usermanagement_service",
        ],
        provided_ports=["training_api", "training_admin_api"],
        required_capabilities=[],
        provided_capabilities=["training.assignment.manage", "training.quiz.execute"],
        settings_contribution=TRAINING_SETTINGS_CONTRIBUTION,
        license_tag=None,
        register=register_training_ports,
        start=start_training_module,
        stop=stop_training_module,
    )
