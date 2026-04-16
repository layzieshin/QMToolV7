"""§15.1 C: Quiz binding tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.training.errors import TrainingValidationError
from .conftest_helpers import make_full_stack, SAMPLE_QUIZ_JSON


class TestQuizBindingService(unittest.TestCase):
    def test_bind_quiz_to_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            result = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            binding = s["quiz_binding"].bind_quiz_to_document(result.import_id, "DOC-1", 1)
            self.assertTrue(binding.active)
            self.assertEqual(binding.document_id, "DOC-1")

    def test_pending_mappings_for_unbound(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            result = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            pending = s["quiz_binding"].list_pending_quiz_mappings()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0].import_id, result.import_id)

    def test_duplicate_binding_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            result = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            s["quiz_binding"].bind_quiz_to_document(result.import_id, "DOC-1", 1)
            with self.assertRaises(TrainingValidationError):
                s["quiz_binding"].bind_quiz_to_document(result.import_id, "DOC-1", 1)


if __name__ == "__main__":
    unittest.main()

