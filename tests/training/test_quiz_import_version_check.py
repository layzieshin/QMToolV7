from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from modules.training.errors import TrainingValidationError
from .conftest_helpers import SAMPLE_QUIZ_JSON, make_full_stack


class QuizImportVersionCheckTest(unittest.TestCase):
    def test_import_requires_force_on_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            services = make_full_stack(Path(tmp))
            payload = json.loads(SAMPLE_QUIZ_JSON.decode("utf-8"))
            payload["document_version"] = 2
            raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")

            preview = services["quiz_import"].inspect_quiz_json(raw)
            self.assertFalse(preview.version_matches_active)
            self.assertEqual(preview.active_document_version, 1)

            with self.assertRaises(TrainingValidationError):
                services["quiz_import"].import_quiz_json(raw)

            forced = services["quiz_import"].import_quiz_json(raw, force=True)
            self.assertEqual(forced.document_version, 2)


if __name__ == "__main__":
    unittest.main()
