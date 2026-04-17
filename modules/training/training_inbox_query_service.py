"""Training inbox query service (§3.11)."""
from __future__ import annotations

from .contracts import AssignmentSource, TrainingInboxItem
from .released_document_catalog_reader import ReleasedDocumentCatalogReader
from .training_quiz_repository import TrainingQuizRepository
from .training_snapshot_repository import TrainingSnapshotRepository


class TrainingInboxQueryService:
    def __init__(
        self,
        *,
        snapshot_repo: TrainingSnapshotRepository,
        quiz_repo: TrainingQuizRepository,
        catalog_reader: ReleasedDocumentCatalogReader,
    ) -> None:
        self._snapshot_repo = snapshot_repo
        self._quiz_repo = quiz_repo
        self._catalog = catalog_reader

    def list_training_inbox_for_user(self, user_id: str, open_only: bool = False) -> list[TrainingInboxItem]:
        snapshots = self._snapshot_repo.list_snapshots_for_user(user_id)
        # Build exact lookup by (document_id, version) so archived/superseded
        # versions are dropped immediately from the inbox view.
        doc_refs = {
            (d.document_id, d.version): d
            for d in self._catalog.list_released_documents()
        }
        items: list[TrainingInboxItem] = []
        for snap in snapshots:
            if snap.source == AssignmentSource.NOT_RELEVANT:
                continue
            doc_ref = doc_refs.get((snap.document_id, snap.version))
            if doc_ref is None:
                # Snapshot points to a non-released version (e.g. archived).
                continue
            progress = self._snapshot_repo.get_progress(snap.user_id, snap.document_id, snap.version)
            read_confirmed = progress is not None and progress.read_confirmed_at is not None
            quiz_passed = progress is not None and progress.quiz_passed_at is not None
            if open_only and quiz_passed:
                continue
            binding = self._quiz_repo.get_active_binding(snap.document_id, snap.version)
            items.append(
                TrainingInboxItem(
                    document_id=snap.document_id,
                    version=snap.version,
                    title=doc_ref.title if doc_ref else snap.document_id,
                    status="EXEMPTED" if snap.exempted else "APPROVED",
                    owner_user_id=doc_ref.owner_user_id if doc_ref else None,
                    released_at=doc_ref.released_at if doc_ref else None,
                    read_confirmed=read_confirmed,
                    quiz_available=binding is not None,
                    quiz_passed=quiz_passed,
                    source=snap.source,
                )
            )
        return items

