"""Port wiring for the training module (clean-slate redesign)."""
from __future__ import annotations

from pathlib import Path

from .api import TrainingAdminApi, TrainingApi
from .document_tag_service import DocumentTagService
from .exemption_service import ExemptionService
from .manual_assignment_service import ManualAssignmentService
from .quiz_binding_service import QuizBindingService
from .quiz_execution_service import QuizExecutionService
from .quiz_import_service import QuizImportService
from .released_document_catalog_reader import ReleasedDocumentCatalogReader
from .secure_store import EncryptedTrainingBlobStore
from .training_comment_repository import TrainingCommentRepository
from .training_comment_service import TrainingCommentService
from .training_inbox_query_service import TrainingInboxQueryService
from .training_override_repository import TrainingOverrideRepository
from .training_quiz_repository import TrainingQuizRepository
from .training_report_repository import TrainingReportRepository
from .training_report_service import TrainingReportService
from .training_snapshot_projector import TrainingSnapshotProjector
from .training_snapshot_repository import TrainingSnapshotRepository
from .training_tag_repository import TrainingTagRepository
from .user_tag_service import UserTagService


def register_training_ports(container) -> None:
    settings_service = container.get_port("settings_service")
    app_home = container.get_port("app_home")
    cfg = settings_service.get_module_settings("training")

    db_path = app_home / cfg.get("training_db_path", "storage/training/training.db")
    schema_path = Path(__file__).parent / "schema.sql"

    # --- Repositories ---
    tag_repo = TrainingTagRepository(db_path, schema_path)
    override_repo = TrainingOverrideRepository(db_path, schema_path)
    snapshot_repo = TrainingSnapshotRepository(db_path, schema_path)
    quiz_repo = TrainingQuizRepository(db_path, schema_path)
    comment_repo = TrainingCommentRepository(db_path, schema_path)
    report_repo = TrainingReportRepository(db_path, schema_path)

    secure_store = EncryptedTrainingBlobStore(
        root=app_home / cfg.get("quiz_blob_root", "storage/training/quiz_blobs"),
        key_file=app_home / cfg.get("quiz_master_key_path", "storage/platform/training_quiz_master.key"),
    )

    event_bus = container.get_port("event_bus")
    documents_pool_api = container.get_port("documents_pool_api")
    documents_read_api = container.get_port("documents_read_api")
    usermanagement_service = container.get_port("usermanagement_service")

    # --- Services ---
    catalog_reader = ReleasedDocumentCatalogReader(documents_pool_api=documents_pool_api)
    doc_tag_service = DocumentTagService(tag_repo=tag_repo)
    user_tag_service = UserTagService(tag_repo=tag_repo)
    quiz_import_service = QuizImportService(quiz_repo=quiz_repo, secure_store=secure_store, event_bus=event_bus)
    quiz_binding_service = QuizBindingService(quiz_repo=quiz_repo, event_bus=event_bus)
    manual_service = ManualAssignmentService(override_repo=override_repo, event_bus=event_bus)
    exemption_service = ExemptionService(override_repo=override_repo, event_bus=event_bus)
    projector = TrainingSnapshotProjector(
        catalog_reader=catalog_reader,
        snapshot_repo=snapshot_repo,
        tag_repo=tag_repo,
        override_repo=override_repo,
        usermanagement_service=usermanagement_service,
        event_bus=event_bus,
    )
    inbox_query = TrainingInboxQueryService(
        snapshot_repo=snapshot_repo,
        quiz_repo=quiz_repo,
        catalog_reader=catalog_reader,
    )
    quiz_execution = QuizExecutionService(
        quiz_repo=quiz_repo,
        snapshot_repo=snapshot_repo,
        quiz_import_service=quiz_import_service,
        event_bus=event_bus,
    )
    comment_service = TrainingCommentService(comment_repo=comment_repo, event_bus=event_bus)
    report_service = TrainingReportService(report_repo=report_repo, event_bus=event_bus)

    # --- API ports ---
    training_api = TrainingApi(
        inbox_query=inbox_query,
        quiz_execution=quiz_execution,
        comment_service=comment_service,
    )
    training_admin_api = TrainingAdminApi(
        catalog_reader=catalog_reader,
        quiz_import=quiz_import_service,
        quiz_binding=quiz_binding_service,
        doc_tag_service=doc_tag_service,
        user_tag_service=user_tag_service,
        manual_service=manual_service,
        exemption_service=exemption_service,
        projector=projector,
        comment_service=comment_service,
        report_service=report_service,
    )

    container.register_port("training_api", training_api)
    container.register_port("training_admin_api", training_admin_api)

    # --- Event subscription: read confirmation from documents module ---
    def _on_read_confirmed(envelope) -> None:
        payload = envelope.payload
        user_id = payload.get("user_id")
        document_id = payload.get("document_id")
        version = payload.get("version")
        if not user_id or not document_id or version is None:
            return
        try:
            receipt = documents_read_api.get_read_receipt(user_id, document_id, int(version))
        except Exception:
            return
        if receipt is None:
            return
        if str(getattr(receipt, "user_id", "")) != str(user_id):
            return
        if str(getattr(receipt, "document_id", "")) != str(document_id):
            return
        if int(getattr(receipt, "version", -1)) != int(version):
            return
        from .contracts import TrainingProgress

        progress = snapshot_repo.get_progress(user_id, document_id, int(version))
        if progress is not None and progress.read_confirmed_at is not None:
            return  # already confirmed
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        new_progress = TrainingProgress(
            user_id=user_id,
            document_id=document_id,
            version=int(version),
            read_confirmed_at=now,
            quiz_passed_at=progress.quiz_passed_at if progress else None,
            last_score=progress.last_score if progress else None,
            quiz_attempts_count=progress.quiz_attempts_count if progress else 0,
        )
        snapshot_repo.upsert_progress(new_progress)

    subscribe = getattr(event_bus, "subscribe", None)
    if callable(subscribe):
        subscribe("domain.documents.read.confirmed.v1", _on_read_confirmed)
