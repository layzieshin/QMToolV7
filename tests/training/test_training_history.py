"""§15.1 D9: Quiz history tests."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from modules.training.contracts import TrainingProgress
from .conftest_helpers import make_full_stack, SAMPLE_QUIZ_JSON


class TestTrainingHistory(unittest.TestCase):
    def test_quiz_attempts_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            s["manual_svc"].grant_manual_assignment("user", "DOC-1", "test", "admin")
            s["projector"].rebuild_all()
            s["snapshot_repo"].upsert_progress(TrainingProgress(
                user_id="user", document_id="DOC-1", version=1,
                read_confirmed_at=datetime.now(timezone.utc),
            ))
            result = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            s["quiz_binding"].bind_quiz_to_document(result.import_id, "DOC-1", 1)
            # Attempt 1: wrong answers
            session1, q1 = s["quiz_exec"].start_quiz("user", "DOC-1", 1)
            wrong = [(next(i for i, a in enumerate(q.answers) if a.answer_id == q.correct_answer_id) + 1) % 4 for q in q1]
            r1 = s["quiz_exec"].submit_quiz_answers(session1.session_id, wrong)
            self.assertFalse(r1.passed)
            # Attempt 2: correct answers
            session2, q2 = s["quiz_exec"].start_quiz("user", "DOC-1", 1)
            correct = [next(i for i, a in enumerate(q.answers) if a.answer_id == q.correct_answer_id) for q in q2]
            r2 = s["quiz_exec"].submit_quiz_answers(session2.session_id, correct)
            self.assertTrue(r2.passed)
            # History: 2 attempts in repo
            attempts = s["quiz_repo"].list_attempts_for_user("user")
            self.assertEqual(len(attempts), 2)
            # Progress updated
            progress = s["snapshot_repo"].get_progress("user", "DOC-1", 1)
            self.assertIsNotNone(progress.quiz_passed_at)
            self.assertEqual(progress.quiz_attempts_count, 2)


if __name__ == "__main__":
    unittest.main()

