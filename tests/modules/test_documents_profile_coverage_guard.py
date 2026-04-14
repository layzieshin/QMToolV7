from __future__ import annotations

import json
import unittest
from pathlib import Path


class DocumentsProfileCoverageGuardTest(unittest.TestCase):
    def test_each_workflow_profile_id_is_referenced_in_documents_tests(self) -> None:
        profiles_payload = json.loads(Path("modules/documents/workflow_profiles.json").read_text(encoding="utf-8"))
        profile_ids = [str(row["profile_id"]) for row in profiles_payload.get("profiles", [])]
        self.assertTrue(profile_ids, "workflow_profiles.json must define at least one profile")

        candidate_files = [
            *Path("tests/modules").glob("test_documents_*.py"),
            *Path("tests/e2e_cli").glob("test_documents_*.py"),
        ]
        corpus = "\n".join(path.read_text(encoding="utf-8") for path in candidate_files if path.exists())
        missing = [profile_id for profile_id in profile_ids if profile_id not in corpus]
        self.assertFalse(
            missing,
            msg=(
                "Each workflow_profile_id must have explicit module/e2e test coverage reference. "
                f"Missing references: {missing}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
