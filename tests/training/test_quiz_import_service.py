"""§15.1 A: Quiz import tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from modules.training.errors import TrainingValidationError
from .conftest_helpers import make_full_stack, SAMPLE_QUIZ_JSON


class TestQuizImportService(unittest.TestCase):
    def test_import_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            result = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            self.assertEqual(result.document_id, "DOC-1")
            self.assertEqual(result.document_version, 1)
            self.assertEqual(result.question_count, 4)

    def test_import_missing_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            bad = json.dumps({"questions": []}).encode()
            with self.assertRaises(TrainingValidationError):
                s["quiz_import"].import_quiz_json(bad)

    def test_import_invalid_correct_answer_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            data = json.loads(SAMPLE_QUIZ_JSON)
            data["questions"][0]["correct_answer_id"] = "INVALID"
            with self.assertRaises(TrainingValidationError):
                s["quiz_import"].import_quiz_json(json.dumps(data).encode())

    def test_import_duplicate_question_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            data = json.loads(SAMPLE_QUIZ_JSON)
            data["questions"][1]["question_id"] = "Q1"
            with self.assertRaises(TrainingValidationError):
                s["quiz_import"].import_quiz_json(json.dumps(data).encode())

    def test_import_duplicate_answer_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            data = json.loads(SAMPLE_QUIZ_JSON)
            data["questions"][0]["answers"][1]["answer_id"] = "a1"
            with self.assertRaises(TrainingValidationError):
                s["quiz_import"].import_quiz_json(json.dumps(data).encode())

    def test_import_wrong_answer_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            data = json.loads(SAMPLE_QUIZ_JSON)
            data["questions"][0]["answers"] = data["questions"][0]["answers"][:3]
            with self.assertRaises(TrainingValidationError):
                s["quiz_import"].import_quiz_json(json.dumps(data).encode())


if __name__ == "__main__":
    unittest.main()

