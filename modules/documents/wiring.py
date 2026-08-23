"""Port wiring for the documents module (SRP split B5)."""
from __future__ import annotations

from pathlib import Path

from qm_platform.persistence.path_resolver import (
    resolve_bootstrap_absolute_path,
    resolve_bootstrap_relative_path,
)

from .bootstrap_provenance import resolve_documents_bootstrap_provenance
from .docx_to_pdf import convert_docx_to_pdf
from .api import DocumentsArtifactsApi, DocumentsCommentsApi, DocumentsPoolApi, DocumentsReadApi, DocumentsWorkflowApi
from .workflow_profile_seed_reader import WorkflowProfileSeedReader
from .workflow_profile_store import WorkflowProfileRelationalStore
from .service import DocumentsService
from .postgres_repository import PostgresDocumentsRepository
from .sqlite_repository import SQLiteDocumentsRepository
from .storage import FileSystemDocumentsStorage

# Explicit in-process opt-in for tests/dev harnesses. Never a free product env var.
DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT = "documents_allow_inprocess_sqlite"


def _should_register_sqlite(container) -> bool:
    if container.has_port("documents_runtime_owner"):
        if container.get_port("documents_runtime_owner") == "backend":
            return True
    if container.has_port("documents_allow_inprocess_sqlite"):
        return bool(container.get_port("documents_allow_inprocess_sqlite"))
    return False


def register_documents_ports(container) -> None:
    """Register documents ports.

    Backend/in-process SQLite ownership uses ``_register_documents_sqlite_ports``.
    Client/HTTP ownership must be injected by the composition root via port
    ``documents_client_ports_registrar`` (callable). Domain code must never
    import adapter implementation packages.
    """
    if _should_register_sqlite(container):
        if (
            container.has_port("documents_postgres_dsn")
            and bool(str(container.get_port("documents_postgres_dsn")).strip())
        ):
            _register_documents_postgres_ports(container)
        else:
            _register_documents_sqlite_ports(container)
        return
    if not container.has_port("documents_client_ports_registrar"):
        raise RuntimeError(
            "documents client ports registrar missing; "
            "composition root must register documents_client_ports_registrar "
            "before activating the documents client module"
        )
    if container.has_port("documents_client_ports_registrar"):
        registrar = container.get_port("documents_client_ports_registrar")
    else:
        raise RuntimeError("documents client ports registrar missing")
    if not callable(registrar):
        raise RuntimeError("documents_client_ports_registrar must be callable")
    registrar(container)


def _register_documents_postgres_ports(container) -> None:
    _register_documents_backend_ports(container, postgres=True)


def _register_documents_sqlite_ports(container) -> None:
    _register_documents_backend_ports(container, postgres=False)


def _register_documents_backend_ports(container, *, postgres: bool) -> None:
    app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
    module_root = Path(__file__).resolve().parents[2]
    resource_root = container.get_port("resource_root") if container.has_port("resource_root") else module_root
    bundled_seed_path = resource_root / "modules" / "documents" / "workflow_profiles.json"
    if not bundled_seed_path.exists():
        bundled_seed_path = module_root / "modules" / "documents" / "workflow_profiles.json"

    def _resolve_legacy_runtime_profiles_path() -> Path:
        """Previously effective profiles_file path used only for pre-J03 upgrade import."""
        preferred = resolve_bootstrap_absolute_path(app_home, "documents", "profiles_file")
        if preferred.exists():
            return preferred
        raw = resolve_bootstrap_relative_path("documents", "profiles_file")
        bundled = resource_root / raw
        return bundled if bundled.exists() else preferred

    provenance = resolve_documents_bootstrap_provenance(container)

    artifacts_root = resolve_bootstrap_absolute_path(app_home, "documents", "artifacts_root")
    if postgres:
        repository = PostgresDocumentsRepository(str(container.get_port("documents_postgres_dsn")))
    else:
        db_path = resolve_bootstrap_absolute_path(app_home, "documents", "documents_db_path")
        repository = SQLiteDocumentsRepository(db_path=db_path)
    profile_store = WorkflowProfileRelationalStore(
        repository,
        bundled_seed_path=bundled_seed_path,
        legacy_profiles_path=_resolve_legacy_runtime_profiles_path(),
        bootstrap_provenance=provenance,
    )
    profile_store.ensure_seeded(WorkflowProfileSeedReader())
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
