"""§15.1 C5/C6: Quiz replacement flow tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .conftest_helpers import make_full_stack, SAMPLE_QUIZ_JSON


class TestQuizReplacementFlow(unittest.TestCase):
    def _make_second_quiz(self):
        data = json.loads(SAMPLE_QUIZ_JSON)
        data["questions"][0]["text"] = "Updated question"
        return json.dumps(data).encode()

    def test_replacement_conflict_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            r1 = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            s["quiz_binding"].bind_quiz_to_document(r1.import_id, "DOC-1", 1)
            r2 = s["quiz_import"].import_quiz_json(self._make_second_quiz())
            check = s["quiz_binding"].check_quiz_replacement_conflict("DOC-1", 1, r2.import_id)
            self.assertTrue(check.has_conflict)
            self.assertIsNotNone(check.existing_binding)

    def test_no_conflict_when_no_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            check = s["quiz_binding"].check_quiz_replacement_conflict("DOC-1", 1, "any")
            self.assertFalse(check.has_conflict)

    def test_replacement_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            r1 = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            s["quiz_binding"].bind_quiz_to_document(r1.import_id, "DOC-1", 1)
            r2 = s["quiz_import"].import_quiz_json(self._make_second_quiz())
            result = s["quiz_binding"].replace_quiz_binding("DOC-1", 1, r2.import_id, "admin")
            self.assertNotEqual(result.old_binding_id, result.new_binding_id)
            # old deactivated, new active
            bindings = s["quiz_binding"].list_quiz_bindings()
            active = [b for b in bindings if b.active]
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].import_id, r2.import_id)

    def test_replacement_events_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            r1 = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            s["quiz_binding"].bind_quiz_to_document(r1.import_id, "DOC-1", 1)
            r2 = s["quiz_import"].import_quiz_json(self._make_second_quiz())
            s["quiz_binding"].check_quiz_replacement_conflict("DOC-1", 1, r2.import_id)
            s["quiz_binding"].replace_quiz_binding("DOC-1", 1, r2.import_id, "admin")
            names = s["bus"].event_names()
            self.assertIn("domain.training.quiz.replacement.detected.v1", names)
            self.assertIn("domain.training.quiz.replaced.v1", names)


if __name__ == "__main__":
    unittest.main()

