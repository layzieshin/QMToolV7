from __future__ import annotations

from pathlib import Path

from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.sdk.module_contract import ModuleContract, SettingsContribution

from .api import DocumentsPoolApi, DocumentsWorkflowApi
from .profile_store import WorkflowProfileStoreJSON
from .service import DocumentsService
from .sqlite_repository import SQLiteDocumentsRepository
from .storage import FileSystemDocumentsStorage


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


def register_documents_ports(container) -> None:
    app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
    resource_root = container.get_port("resource_root") if container.has_port("resource_root") else app_home

    def _resolve_config_path(raw: str) -> Path:
        path = Path(raw)
        if path.is_absolute():
            return path
        return app_home / path

    def _resolve_profile_path(raw: str) -> Path:
        preferred = _resolve_config_path(raw)
        if preferred.exists():
            return preferred
        bundled = resource_root / raw
        return bundled if bundled.exists() else preferred

    settings_service = container.get_port("settings_service")
    docs_settings = settings_service.get_module_settings("documents")
    schema_path = Path(__file__).with_name("schema.sql")
    repository = SQLiteDocumentsRepository(
        db_path=_resolve_config_path(docs_settings.get("documents_db_path", "storage/documents/documents.db")),
        schema_path=schema_path,
    )
    profile_store = WorkflowProfileStoreJSON(
        _resolve_profile_path(docs_settings.get("profiles_file", "modules/documents/workflow_profiles.json"))
    )
    storage_port = FileSystemDocumentsStorage(
        _resolve_config_path(docs_settings.get("artifacts_root", "storage/documents/artifacts"))
    )
    service = DocumentsService(
        event_bus=container.get_port("event_bus"),
        repository=repository,
        profile_store=profile_store,
        signature_api=container.get_port("signature_api"),
        storage_port=storage_port,
        registry_projection_api=container.get_port("registry_projection_api"),
    )
    container.register_port("documents_service", service)
    container.register_port("documents_pool_api", DocumentsPoolApi(service))
    container.register_port("documents_workflow_api", DocumentsWorkflowApi(service))


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

