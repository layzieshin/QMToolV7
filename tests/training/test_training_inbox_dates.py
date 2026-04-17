"""Regression test: inbox should expose document release date."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from modules.training.contracts import AssignmentSource, TrainingAssignmentSnapshot, TrainingDocumentRef
from modules.training.training_inbox_query_service import TrainingInboxQueryService


class _SnapshotRepo:
    def __init__(self, snapshots):
        self._snapshots = snapshots

    def list_snapshots_for_user(self, _user_id):
        return self._snapshots

    def get_progress(self, _user_id, _document_id, _version):
        return None


class _QuizRepo:
    def get_active_binding(self, _document_id, _version):
        return None


class _Catalog:
    def __init__(self, docs):
        self._docs = docs

    def list_released_documents(self):
        return self._docs


class TestTrainingInboxDates(unittest.TestCase):
    def test_released_at_is_propagated_to_inbox(self):
        release_dt = datetime(2026, 4, 10, 8, 30, tzinfo=timezone.utc)
        snap = TrainingAssignmentSnapshot(
            snapshot_id="s1",
            user_id="user",
            document_id="DOC-1",
            version=1,
            source=AssignmentSource.SCOPE,
            exempted=False,
        )
        doc = TrainingDocumentRef(
            document_id="DOC-1",
            version=1,
            title="Doc",
            owner_user_id="admin",
            released_at=release_dt,
        )
        svc = TrainingInboxQueryService(
            snapshot_repo=_SnapshotRepo([snap]),
            quiz_repo=_QuizRepo(),
            catalog_reader=_Catalog([doc]),
        )
        items = svc.list_training_inbox_for_user("user")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].released_at, release_dt)

    def test_inbox_hides_snapshot_if_version_not_released_anymore(self):
        snap = TrainingAssignmentSnapshot(
            snapshot_id="s1",
            user_id="user",
            document_id="DOC-1",
            version=1,
            source=AssignmentSource.SCOPE,
            exempted=False,
        )
        # Catalog contains only v2, so v1 must not appear.
        doc = TrainingDocumentRef(
            document_id="DOC-1",
            version=2,
            title="Doc v2",
            owner_user_id="admin",
            released_at=datetime(2026, 4, 10, 8, 30, tzinfo=timezone.utc),
        )
        svc = TrainingInboxQueryService(
            snapshot_repo=_SnapshotRepo([snap]),
            quiz_repo=_QuizRepo(),
            catalog_reader=_Catalog([doc]),
        )
        items = svc.list_training_inbox_for_user("user")
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()

