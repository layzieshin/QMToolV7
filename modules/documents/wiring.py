"""Port wiring for the documents module (SRP split B5)."""
from __future__ import annotations

from pathlib import Path

from .api import DocumentsCommentsApi, DocumentsPoolApi, DocumentsReadApi, DocumentsWorkflowApi
from .profile_store import WorkflowProfileStoreJSON
from .service import DocumentsService
from .sqlite_repository import SQLiteDocumentsRepository
from .storage import FileSystemDocumentsStorage


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
    schema_path = Path(__file__).parent / "schema.sql"
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
        audit_logger=container.get_port("audit_logger"),
    )
    container.register_port("documents_service", service)
    container.register_port("documents_pool_api", DocumentsPoolApi(service))
    container.register_port("documents_read_api", DocumentsReadApi(service))
    container.register_port("documents_comments_api", DocumentsCommentsApi(service))
    container.register_port("documents_workflow_api", DocumentsWorkflowApi(service))

