from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from .contracts import OpenTrainingAssignmentItem, TrainingAssignment, TrainingAssignmentStatus, TrainingOverviewItem
from .errors import TrainingValidationError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrainingAssignmentUseCases:
    def __init__(self, service: object) -> None:
        self._service = service

    def sync_required_assignments(self) -> int:
        categories = self._service._repository.list_categories()
        approved = self._service.list_approved_documents()
        latest: dict[str, object] = {}
        for state in approved:
            existing = latest.get(state.document_id)
            if existing is None or state.version > existing.version:
                latest[state.document_id] = state
        created_or_updated = 0
        for category in categories:
            doc_ids = self._service._repository.list_document_ids_by_category(category.category_id)
            user_ids = self._service._repository.list_user_ids_by_category(category.category_id)
            for doc_id in doc_ids:
                target = latest.get(doc_id)
                if target is None:
                    continue
                for user_id in user_ids:
                    for old in self._service._repository.list_active_assignments_for_user_document(user_id, doc_id):
                        if old.version == target.version:
                            continue
                        superseded = replace(
                            old,
                            status=TrainingAssignmentStatus.SUPERSEDED,
                            active=False,
                            updated_at=_utcnow(),
                        )
                        self._service._repository.upsert_assignment(superseded)
                        created_or_updated += 1
                    current = self._service._repository.get_assignment(user_id, doc_id, target.version)
                    if current is None:
                        assignment = TrainingAssignment(
                            assignment_id=uuid4().hex,
                            user_id=user_id,
                            document_id=doc_id,
                            version=target.version,
                            category_id=category.category_id,
                            status=TrainingAssignmentStatus.ASSIGNED,
                            active=True,
                            created_at=_utcnow(),
                            updated_at=_utcnow(),
                        )
                        self._service._repository.upsert_assignment(assignment)
                        created_or_updated += 1
        return created_or_updated

    def list_open_assignments_for_user(self, user_id: str) -> list[OpenTrainingAssignmentItem]:
        items: list[OpenTrainingAssignmentItem] = []
        for assignment in self._service._repository.list_assignments_by_user(user_id):
            if not assignment.active:
                continue
            items.append(
                OpenTrainingAssignmentItem(
                    assignment_id=assignment.assignment_id,
                    user_id=assignment.user_id,
                    document_id=assignment.document_id,
                    version=assignment.version,
                    status=assignment.status,
                    active=assignment.active,
                    read_confirmed_at=assignment.read_confirmed_at,
                    quiz_passed_at=assignment.quiz_passed_at,
                    last_score=assignment.last_score,
                )
            )
        return items

    def list_training_overview_for_user(self, user_id: str) -> list[TrainingOverviewItem]:
        approved_pairs = {(doc.document_id, doc.version) for doc in self._service.list_approved_documents()}
        items: list[TrainingOverviewItem] = []
        for assignment in self._service._repository.list_assignments_by_user(user_id):
            if not assignment.active:
                continue
            items.append(
                TrainingOverviewItem(
                    document_id=assignment.document_id,
                    version=assignment.version,
                    read_confirmed=assignment.read_confirmed_at is not None,
                    quiz_available=(assignment.document_id, assignment.version) in approved_pairs,
                    quiz_passed=assignment.quiz_passed_at is not None,
                    last_action_at=assignment.updated_at,
                )
            )
        return items

    def confirm_read(
        self,
        *,
        user_id: str,
        document_id: str,
        version: int,
        last_page_seen: int,
        total_pages: int,
        scrolled_to_end: bool,
    ) -> TrainingAssignment:
        assignment = self._service._repository.get_assignment(user_id, document_id, version)
        if assignment is None:
            raise TrainingValidationError("no active assignment for this document version")
        if not scrolled_to_end or total_pages <= 0 or last_page_seen < total_pages:
            raise TrainingValidationError("read confirmation requires full progress to last page")
        updated = replace(
            assignment,
            status=TrainingAssignmentStatus.READ_CONFIRMED,
            read_confirmed_at=_utcnow(),
            updated_at=_utcnow(),
        )
        self._service._repository.upsert_assignment(updated)
        self._service._publish(
            "domain.training.read.confirmed.v1",
            {
                "user_id": user_id,
                "document_id": document_id,
                "version": version,
                "last_page_seen": last_page_seen,
                "total_pages": total_pages,
            },
            actor_user_id=user_id,
        )
        return updated
