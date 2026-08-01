from __future__ import annotations

from pathlib import Path

from qm_platform.persistence.database_evolution import (
    DatabaseEvolutionService,
    DatabaseSpec,
    MigrationStep,
)


_INITIAL_MIGRATIONS = {
    "documents": Path("modules/documents/migrations/0001_initial.sql"),
    "incidents": Path("modules/incident_management/migrations/0001_initial.sql"),
    "registry": Path("modules/registry/migrations/0001_initial.sql"),
    "signature": Path("modules/signature/migrations/0001_initial.sql"),
    "training": Path("modules/training/migrations/0001_initial.sql"),
    "users": Path("modules/usermanagement/migrations/0001_initial.sql"),
}

_USERS_MIGRATIONS = (
    MigrationStep(
        version=1,
        name="initial",
        sql_path=Path("modules/usermanagement/migrations/0001_initial.sql"),
    ),
    MigrationStep(
        version=2,
        name="deactivated_at",
        sql_path=Path("modules/usermanagement/migrations/0002_deactivated_at.sql"),
    ),
)


def prepare_test_database(database_id: str, db_path: Path) -> Path:
    service = DatabaseEvolutionService(
        app_home=db_path.parent,
        backup_root=db_path.parent / ".database-backups",
    )
    if database_id == "users":
        migrations = tuple(
            MigrationStep(
                version=step.version,
                name=step.name,
                sql_path=step.sql_path.resolve(),
            )
            for step in _USERS_MIGRATIONS
        )
    else:
        migrations = (
            MigrationStep(
                version=1,
                name="initial",
                sql_path=_INITIAL_MIGRATIONS[database_id].resolve(),
            ),
        )
    service.migrate(
        (
            DatabaseSpec(
                database_id=database_id,
                path=db_path,
                migrations=migrations,
            ),
        ),
        reason="test_setup",
    )
    return db_path


def make_docs_repository(db_path: Path):
    from modules.documents.sqlite_repository import SQLiteDocumentsRepository

    return SQLiteDocumentsRepository(prepare_test_database("documents", db_path))


def registry_repository(db_path: Path):
    from modules.registry.sqlite_repository import SQLiteRegistryRepository

    return SQLiteRegistryRepository(prepare_test_database("registry", db_path))


def user_repository(db_path: Path):
    from modules.usermanagement.sqlite_repository import SQLiteUserRepository

    return SQLiteUserRepository(prepare_test_database("users", db_path))


def signature_repository(db_path: Path):
    from modules.signature.sqlite_repository import SQLiteSignatureRepository

    return SQLiteSignatureRepository(prepare_test_database("signature", db_path))


def incident_repository(db_path: Path):
    from modules.incident_management.sqlite_repository import SQLiteIncidentRepository

    return SQLiteIncidentRepository(db_path=prepare_test_database("incidents", db_path))


def prepare_training_database(db_path: Path) -> Path:
    return prepare_test_database("training", db_path)
