from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.training.contracts import TrainingProgress
from modules.training.errors import TrainingValidationError
from .conftest_helpers import SAMPLE_QUIZ_JSON, make_full_stack


class QuizExecutionPolicyFeaturesTest(unittest.TestCase):
    def _setup(self, root: Path):
        s = make_full_stack(root)
        s["manual_svc"].grant_manual_assignment("user", "DOC-1", "test", "admin")
        s["projector"].rebuild_all()
        s["snapshot_repo"].upsert_progress(
            TrainingProgress(
                user_id="user",
                document_id="DOC-1",
                version=1,
                read_confirmed_at=datetime.now(timezone.utc),
            )
        )
        imported = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
        s["quiz_binding"].bind_quiz_to_document(imported.import_id, "DOC-1", 1)
        return s

    def test_min_correct_answers_is_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            s = self._setup(Path(tmp))
            s["settings"]._modules["training"]["questions_per_quiz"] = 4
            s["settings"]._modules["training"]["min_correct_answers"] = 2
            session, questions = s["quiz_exec"].start_quiz("user", "DOC-1", 1)
            answers: list[str] = []
            for idx, q in enumerate(questions):
                if idx < 2:
                    answers.append(q.correct_answer_id)
                else:
                    answers.append(next(a.answer_id for a in q.answers if a.answer_id != q.correct_answer_id))
            result = s["quiz_exec"].submit_quiz_answers(session.session_id, answers)
            self.assertTrue(result.passed)
            self.assertEqual(result.score, 2)

    def test_cooldown_blocks_next_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            s = self._setup(Path(tmp))
            s["settings"]._modules["training"]["retry_cooldown_seconds"] = 600
            s["snapshot_repo"].upsert_progress(
                TrainingProgress(
                    user_id="user",
                    document_id="DOC-1",
                    version=1,
                    read_confirmed_at=datetime.now(timezone.utc),
                    last_failed_at=datetime.now(timezone.utc) - timedelta(seconds=60),
                )
            )
            with self.assertRaises(TrainingValidationError):
                s["quiz_exec"].start_quiz("user", "DOC-1", 1)

    def test_force_reread_resets_read_confirmation_after_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            s = self._setup(Path(tmp))
            s["settings"]._modules["training"]["force_reread_on_fail"] = True
            session, questions = s["quiz_exec"].start_quiz("user", "DOC-1", 1)
            wrong = [next(a.answer_id for a in q.answers if a.answer_id != q.correct_answer_id) for q in questions]
            result = s["quiz_exec"].submit_quiz_answers(session.session_id, wrong)
            self.assertFalse(result.passed)
            progress = s["snapshot_repo"].get_progress("user", "DOC-1", 1)
            self.assertIsNotNone(progress)
            self.assertIsNone(progress.read_confirmed_at)


if __name__ == "__main__":
    unittest.main()
