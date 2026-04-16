"""Snapshot projector – materializes assignment snapshots (§3.10)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import AssignmentSource, TrainingAssignmentSnapshot
from .released_document_catalog_reader import ReleasedDocumentCatalogReader
from .scope_resolver import ScopeResolver
from .training_assignment_resolver import TrainingAssignmentResolver
from .training_override_repository import TrainingOverrideRepository
from .training_snapshot_repository import TrainingSnapshotRepository
from .training_tag_repository import TrainingTagRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrainingSnapshotProjector:
    def __init__(
        self,
        *,
        catalog_reader: ReleasedDocumentCatalogReader,
        snapshot_repo: TrainingSnapshotRepository,
        tag_repo: TrainingTagRepository,
        override_repo: TrainingOverrideRepository,
        usermanagement_service: object,
        event_bus: object | None = None,
    ) -> None:
        self._catalog = catalog_reader
        self._snapshot_repo = snapshot_repo
        self._tag_repo = tag_repo
        self._override_repo = override_repo
        self._um = usermanagement_service
        self._event_bus = event_bus

    def rebuild_all(self) -> int:
        """Rebuild all assignment snapshots from scratch. Returns count of snapshots created."""
        docs = self._catalog.list_released_documents()
        users = self._um.list_users()
        all_doc_tags = {dt.document_id: dt.tags for dt in self._tag_repo.list_all_document_tags()}
        all_user_tags = {ut.user_id: ut.tags for ut in self._tag_repo.list_all_user_tags()}
        all_manual = self._override_repo.list_active_manual_assignments()
        all_exemptions = self._override_repo.list_active_exemptions()
        previous = {
            (s.user_id, s.document_id, s.version): s
            for s in self._snapshot_repo.list_snapshots()
        }

        manual_set: set[tuple[str, str]] = {(m.user_id, m.document_id) for m in all_manual}
        exemption_map: dict[tuple[str, str, int], bool] = {}
        now = _utcnow()
        for ex in all_exemptions:
            expired = ex.valid_until is not None and ex.valid_until < now
            key = (ex.user_id, ex.document_id, ex.version)
            exemption_map[key] = not expired

        self._snapshot_repo.delete_all_snapshots()
        count = 0
        for doc in docs:
            doc_tags = all_doc_tags.get(doc.document_id, frozenset())
            for user in users:
                uid = user.user_id
                user_tags = all_user_tags.get(uid, frozenset())
                scope_match = ScopeResolver.matches(
                    doc,
                    user_department=getattr(user, "department", None),
                    user_scope=getattr(user, "scope", None),
                    user_organization_unit=getattr(user, "organization_unit", None),
                )
                tag_match = bool(doc_tags & user_tags)
                manual_match = (uid, doc.document_id) in manual_set
                exempted = exemption_map.get((uid, doc.document_id, doc.version), False)

                source = TrainingAssignmentResolver.resolve(
                    doc,
                    scope_match=scope_match,
                    tag_match=tag_match,
                    manual_match=manual_match,
                    exempted=exempted,
                )
                if source == AssignmentSource.NOT_RELEVANT:
                    continue
                snap = TrainingAssignmentSnapshot(
                    snapshot_id=uuid4().hex,
                    user_id=uid,
                    document_id=doc.document_id,
                    version=doc.version,
                    source=source,
                    exempted=(source == AssignmentSource.EXEMPTED),
                    created_at=now,
                    updated_at=now,
                )
                self._snapshot_repo.upsert_snapshot(snap)
                key = (snap.user_id, snap.document_id, snap.version)
                if key in previous:
                    self._publish(
                        "domain.training.assignment.snapshot.updated.v1",
                        {
                            "user_id": snap.user_id,
                            "document_id": snap.document_id,
                            "version": snap.version,
                            "source": snap.source.value,
                            "exempted": snap.exempted,
                        },
                    )
                else:
                    self._publish(
                        "domain.training.assignment.snapshot.created.v1",
                        {
                            "user_id": snap.user_id,
                            "document_id": snap.document_id,
                            "version": snap.version,
                            "source": snap.source.value,
                            "exempted": snap.exempted,
                        },
                    )
                count += 1
        self._publish("domain.training.assignment.snapshot.rebuilt.v1", {"count": count})
        return count

    def _publish(self, name: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="training", payload=payload))

