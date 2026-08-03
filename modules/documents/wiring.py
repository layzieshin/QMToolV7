"""Port wiring for the documents module (SRP split B5)."""
from __future__ import annotations

from pathlib import Path

from qm_platform.persistence.path_resolver import (
    resolve_bootstrap_absolute_path,
    resolve_bootstrap_relative_path,
)

from .docx_to_pdf import convert_docx_to_pdf
from .api import DocumentsArtifactsApi, DocumentsCommentsApi, DocumentsPoolApi, DocumentsReadApi, DocumentsWorkflowApi
from .profile_store import WorkflowProfileStoreJSON
from .service import DocumentsService
from .sqlite_repository import SQLiteDocumentsRepository
from .storage import FileSystemDocumentsStorage


def register_documents_ports(container) -> None:
    app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
    resource_root = container.get_port("resource_root") if container.has_port("resource_root") else app_home

    def _resolve_profile_path() -> Path:
        raw = resolve_bootstrap_relative_path("documents", "profiles_file")
        preferred = resolve_bootstrap_absolute_path(app_home, "documents", "profiles_file")
        if preferred.exists():
            return preferred
        bundled = resource_root / raw
        return bundled if bundled.exists() else preferred

    artifacts_root = resolve_bootstrap_absolute_path(app_home, "documents", "artifacts_root")
    repository = SQLiteDocumentsRepository(
        db_path=resolve_bootstrap_absolute_path(app_home, "documents", "documents_db_path"),
    )
    profile_store = WorkflowProfileStoreJSON(_resolve_profile_path())
    storage_port = FileSystemDocumentsStorage(artifacts_root)
    service = DocumentsService(
        event_bus=container.get_port("event_bus"),
        repository=repository,
        profile_store=profile_store,
        signature_api=container.get_port("signature_api"),
        storage_port=storage_port,
        registry_projection_api=container.get_port("registry_projection_api"),
        audit_logger=container.get_port("audit_logger"),
        docx_to_pdf_converter=convert_docx_to_pdf,
    )
    container.register_port("documents_service", service)
    container.register_port("documents_pool_api", DocumentsPoolApi(service))
    container.register_port(
        "documents_artifacts_api",
        DocumentsArtifactsApi(
            service,
            app_home=app_home,
            artifacts_root=artifacts_root,
        ),
    )
    container.register_port("documents_read_api", DocumentsReadApi(service))
    container.register_port("documents_comments_api", DocumentsCommentsApi(service))
    container.register_port("documents_workflow_api", DocumentsWorkflowApi(service))
