from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RegistryRecoveryDrillTest(unittest.TestCase):
    def _prepare_docs_db(self, db_path: Path) -> None:
        schema = Path("modules/documents/schema.sql").read_text(encoding="utf-8")
        with sqlite3.connect(db_path) as conn:
            conn.executescript(schema)
            conn.execute(
                """
                INSERT INTO document_headers (
                    document_id, doc_type, control_class, workflow_profile_id, register_binding, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("DOC-DRILL-1", "VA", "CONTROLLED", "long_release", 1),
            )
            conn.execute(
                """
                INSERT INTO document_versions (
                    document_id, version, title, description, doc_type, control_class, workflow_profile_id, owner_user_id, status,
                    workflow_active, workflow_profile_json, editors_json, reviewers_json, approvers_json, reviewed_by_json, approved_by_json,
                    edit_signature_done, valid_from, valid_until, next_review_at, review_completed_at, review_completed_by,
                    approval_completed_at, approval_completed_by, released_at, archived_at, archived_by, superseded_by_version,
                    extension_count, custom_fields_json, last_event_id, last_event_at, last_actor_user_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    "DOC-DRILL-1",
                    1,
                    "Title",
                    None,
                    "VA",
                    "CONTROLLED",
                    "long_release",
                    "admin",
                    "APPROVED",
                    0,
                    "{}",
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    0,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    0,
                    "{}",
                    None,
                    None,
                    None,
                ),
            )
            conn.commit()

    def _prepare_bad_registry_db(self, db_path: Path) -> None:
        schema = Path("modules/registry/schema.sql").read_text(encoding="utf-8")
        with sqlite3.connect(db_path) as conn:
            conn.executescript(schema)
            conn.execute(
                """
                INSERT INTO document_registry (
                    document_id, active_version, release_note, release_evidence_mode, register_state, is_findable,
                    valid_from, valid_until, last_update_event_id, last_update_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                ("DOC-DRILL-1", 2, None, "WORKFLOW", "VALID", 1, None, None, "evt-bad"),
            )
            conn.commit()

    def test_registry_recovery_drill_reduces_drift_to_zero_in_rebuilt_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_db = root / "documents.db"
            bad_registry_db = root / "registry_bad.db"
            rebuilt_registry_db = root / "registry_rebuilt.db"
            evidence_dir = root / "evidence"
            self._prepare_docs_db(docs_db)
            self._prepare_bad_registry_db(bad_registry_db)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/registry_recovery_drill.py",
                    "--documents-db-path",
                    str(docs_db),
                    "--registry-db-path",
                    str(bad_registry_db),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--rebuilt-registry-db-path",
                    str(rebuilt_registry_db),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            payload = json.loads(result.stdout.strip() or "{}")
            self.assertTrue(payload.get("ok"), msg=result.stdout)
            before = payload.get("drift_before", {}).get("metrics", {}).get("drift_total", 0)
            after = payload.get("drift_after_rebuild", {}).get("metrics", {}).get("drift_total", 0)
            self.assertGreater(before, 0)
            self.assertEqual(after, 0)
            self.assertTrue((evidence_dir / "registry_recovery_drill_evidence.json").exists())


if __name__ == "__main__":
    unittest.main()
