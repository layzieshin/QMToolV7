from __future__ import annotations

from pathlib import Path

from qm_platform.sdk.module_contract import DatabaseContribution, DatabaseMigrationContribution, ModuleContract, SettingsContribution

from .wiring import register_container_ports


CONTAINER_SETTINGS_CONTRIBUTION = SettingsContribution(module_id="container", schema_version=1, schema={"type": "object", "properties": {"container_db_path": {"type": "string"}, "artifact_files_root": {"type": "string"}}, "required": ["container_db_path", "artifact_files_root"], "additionalProperties": False}, defaults={"container_db_path": "storage/container/container.db", "artifact_files_root": "storage/container/artifacts"}, scope="module_global", migrations=[])
CONTAINER_DATABASE_CONTRIBUTION = DatabaseContribution(database_id="container", module_id="container", setting_key="container_db_path", default_path="storage/container/container.db", migrations=(DatabaseMigrationContribution(version=1, name="initial", sql_path=Path(__file__).parent / "migrations" / "0001_initial.sql"),))


def start_container_module(container) -> None: return None
def stop_container_module(container) -> None: return None


def create_container_module_contract() -> ModuleContract:
    return ModuleContract(module_id="container", version="1.0.0", min_platform_version="1.0.0", max_platform_version=None, required_ports=["logger", "audit_logger", "event_bus", "settings_service", "usermanagement_service", "app_home"], provided_ports=["container_api"], required_capabilities=[], provided_capabilities=["container.object.manage", "container.artifact.manage", "container.reference.manage", "container.export.manage", "container.blueprint.manage"], settings_contribution=CONTAINER_SETTINGS_CONTRIBUTION, license_tag=None, register=register_container_ports, start=start_container_module, stop=stop_container_module, database_contributions=(CONTAINER_DATABASE_CONTRIBUTION,))
