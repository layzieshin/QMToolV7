from __future__ import annotations

from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.sdk.module_contract import ModuleContract, SettingsContribution

from .wiring import register_incident_management_ports


INCIDENT_SETTINGS_CONTRIBUTION = SettingsContribution(
    module_id="incident_management",
    schema_version=1,
    schema={
        "type": "object",
        "properties": {
            "incident_db_path": {"type": "string"},
            "artifacts_root": {"type": "string"},
            "categories": {"type": "array", "items": {"type": "string"}},
            "label_groups": {"type": "object"},
            "criticality_groups": {"type": "object"},
            "standard_deadlines": {"type": "object"},
            "effectiveness_delay": {"type": "integer", "minimum": 1},
            "capa_required_rules": {"type": "object"},
            "report_templates": {"type": "object"},
        },
        "required": [
            "incident_db_path",
            "artifacts_root",
            "categories",
            "label_groups",
            "criticality_groups",
            "standard_deadlines",
            "effectiveness_delay",
            "capa_required_rules",
            "report_templates",
        ],
        "additionalProperties": False,
    },
    defaults={
        "incident_db_path": "storage/incident_management/incidents.db",
        "artifacts_root": "storage/incident_management/artifacts",
        "categories": ["Prozess", "Gerät", "Dokumentation", "Patientensicherheit", "Sonstiges"],
        "label_groups": {},
        "criticality_groups": {"default": "standard", "critical": "elevated"},
        "standard_deadlines": {
            "assessment_days": 5,
            "action_days": 30,
            "immediate_action_days": 7,
            "corrective_action_days": 30,
            "preventive_action_days": 60,
            "qmb_review_days": 5,
        },
        "effectiveness_delay": 30,
        "capa_required_rules": {
            "critical": True,
            "repeated": True,
            "patient_safety": True,
            "system_risk": True,
            "formal_deviation": True,
            "result_correctness": True,
            "escalation": True,
        },
        "report_templates": {"case": "default", "register": "default", "management_review": "default"},
    },
    scope="module_global",
    migrations=[],
)


def start_incident_management_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("incident_management", "module started")
    container.get_port("event_bus").publish(
        EventEnvelope.create(
            "domain.incident_management.module.started.v1",
            "incident_management",
            {"status": "started"},
        )
    )


def stop_incident_management_module(container) -> None:
    logger = container.get_port("logger")
    logger.info("incident_management", "module stopped")
    container.get_port("event_bus").publish(
        EventEnvelope.create(
            "domain.incident_management.module.stopped.v1",
            "incident_management",
            {"status": "stopped"},
        )
    )


def create_incident_management_module_contract() -> ModuleContract:
    return ModuleContract(
        module_id="incident_management",
        version="1.0.0",
        min_platform_version="1.0.0",
        max_platform_version=None,
        required_ports=[
            "logger",
            "audit_logger",
            "event_bus",
            "settings_service",
            "usermanagement_service",
            "app_home",
        ],
        provided_ports=["incident_management_api"],
        required_capabilities=[],
        provided_capabilities=[
            "incident_management.incident.manage",
            "incident_management.capa.manage",
            "incident_management.review.manage",
        ],
        settings_contribution=INCIDENT_SETTINGS_CONTRIBUTION,
        license_tag="incident_management",
        register=register_incident_management_ports,
        start=start_incident_management_module,
        stop=stop_incident_management_module,
    )
