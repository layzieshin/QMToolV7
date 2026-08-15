from __future__ import annotations

from qm_platform.persistence.path_resolver import resolve_bootstrap_absolute_path

from .api import ContainerApi
from .service import ContainerService
from .sqlite_repository import SQLiteContainerRepository
from .storage import FileSystemArtifactStorage


def register_container_ports(container) -> None:
    app_home = container.get_port("app_home")
    database_path = (
        container.get_port("container_db_path_override")
        if container.has_port("container_db_path_override")
        else resolve_bootstrap_absolute_path(app_home, "container", "container_db_path")
    )
    artifact_root = (
        container.get_port("container_artifact_files_root_override")
        if container.has_port("container_artifact_files_root_override")
        else resolve_bootstrap_absolute_path(app_home, "container", "artifact_files_root")
    )
    repository = SQLiteContainerRepository(database_path)
    storage = FileSystemArtifactStorage(artifact_root)
    service = ContainerService(repository, event_bus=container.get_port("event_bus"), artifact_storage=storage)
    container.register_port("container_api", ContainerApi(service))
