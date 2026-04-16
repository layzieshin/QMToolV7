"""§15.1 D: Quiz execution tests."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from modules.training.contracts import TrainingProgress
from modules.training.errors import TrainingValidationError
from .conftest_helpers import make_full_stack, SAMPLE_QUIZ_JSON


class TestQuizExecutionService(unittest.TestCase):
    def _setup(self, root):
        s = make_full_stack(root)
        s["manual_svc"].grant_manual_assignment("user", "DOC-1", "test", "admin")
        s["projector"].rebuild_all()
        s["snapshot_repo"].upsert_progress(TrainingProgress(
            user_id="user", document_id="DOC-1", version=1,
            read_confirmed_at=datetime.now(timezone.utc),
        ))
        result = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
        s["quiz_binding"].bind_quiz_to_document(result.import_id, "DOC-1", 1)
        return s

    def test_start_quiz(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = self._setup(Path(tmp))
            session, questions = s["quiz_exec"].start_quiz("user", "DOC-1", 1)
            self.assertEqual(len(questions), 3)
            self.assertIn("domain.training.quiz.started.v1", s["bus"].event_names())

    def test_correct_answers_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = self._setup(Path(tmp))
            session, questions = s["quiz_exec"].start_quiz("user", "DOC-1", 1)
            answers = [next(i for i, a in enumerate(q.answers) if a.answer_id == q.correct_answer_id) for q in questions]
            result = s["quiz_exec"].submit_quiz_answers(session.session_id, answers)
            self.assertTrue(result.passed)
            self.assertEqual(result.score, result.total)

    def test_wrong_answers_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = self._setup(Path(tmp))
            session, questions = s["quiz_exec"].start_quiz("user", "DOC-1", 1)
            # All wrong: pick index that is NOT correct
            answers = []
            for q in questions:
                correct_idx = next(i for i, a in enumerate(q.answers) if a.answer_id == q.correct_answer_id)
                answers.append((correct_idx + 1) % len(q.answers))
            result = s["quiz_exec"].submit_quiz_answers(session.session_id, answers)
            self.assertFalse(result.passed)
            self.assertEqual(result.score, 0)

    def test_quiz_requires_read_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            s["manual_svc"].grant_manual_assignment("user", "DOC-1", "test", "admin")
            s["projector"].rebuild_all()
            result = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            s["quiz_binding"].bind_quiz_to_document(result.import_id, "DOC-1", 1)
            with self.assertRaises(TrainingValidationError):
                s["quiz_exec"].start_quiz("user", "DOC-1", 1)


if __name__ == "__main__":
    unittest.main()

