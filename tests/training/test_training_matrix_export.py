"""§15.1 E: Training matrix export tests."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from modules.training.contracts import TrainingProgress
from .conftest_helpers import make_full_stack, SAMPLE_QUIZ_JSON


class TestTrainingMatrixExport(unittest.TestCase):
    def test_export_callable(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            result = s["report_svc"].export_training_matrix()
            self.assertIsNotNone(result.export_id)
            self.assertIn("domain.training.matrix.exported.v1", s["bus"].event_names())

    def test_export_sorted_by_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            s["manual_svc"].grant_manual_assignment("user", "DOC-1", "test", "admin")
            s["manual_svc"].grant_manual_assignment("admin", "DOC-1", "test", "admin")
            s["projector"].rebuild_all()
            s["snapshot_repo"].upsert_progress(TrainingProgress(
                user_id="admin", document_id="DOC-1", version=1,
                read_confirmed_at=datetime.now(timezone.utc),
                quiz_passed_at=datetime.now(timezone.utc), last_score=3, quiz_attempts_count=1,
            ))
            result = s["report_svc"].export_training_matrix()
            self.assertGreaterEqual(result.row_count, 2)
            users = [r["user_id"] for r in result.rows]
            self.assertEqual(users, sorted(users))


if __name__ == "__main__":
    unittest.main()

