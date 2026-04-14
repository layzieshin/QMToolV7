from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


class MigrationGatesDocumentsScriptTest(unittest.TestCase):
    def _prepare_db(self, db_path: Path) -> None:
        schema = Path("modules/documents/schema.sql").read_text(encoding="utf-8")
        with closing(sqlite3.connect(db_path)) as conn:
            conn.executescript(schema)
            conn.commit()

    def _prepare_registry_db(self, db_path: Path) -> None:
        schema = Path("modules/registry/schema.sql").read_text(encoding="utf-8")
        with closing(sqlite3.connect(db_path)) as conn:
            conn.executescript(schema)
            conn.commit()

    def _run_script(
        self,
        db_path: Path,
        baseline_other_count: int | None = None,
        registry_db_path: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            "scripts/migration_gates_documents.py",
            "--documents-db-path",
            str(db_path),
            "--profiles-path",
            "modules/documents/workflow_profiles.json",
        ]
        if registry_db_path is not None:
            cmd.extend(["--registry-db-path", str(registry_db_path)])
        if baseline_other_count is not None:
            cmd.extend(["--baseline-other-count", str(baseline_other_count)])
        return subprocess.run(cmd, text=True, capture_output=True, check=False)

    def test_script_passes_for_valid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "documents.db"
            self._prepare_db(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO document_headers (
                        document_id, doc_type, control_class, workflow_profile_id, register_binding, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    ("DOC-1", "VA", "CONTROLLED", "long_release", 1),
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
                        "DOC-1",
                        1,
                        "Title",
                        None,
                        "VA",
                        "CONTROLLED",
                        "long_release",
                        "admin",
                        "PLANNED",
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
            result = self._run_script(db_path, baseline_other_count=0)
            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            payload = json.loads(result.stdout.strip() or "{}")
            self.assertTrue(payload.get("ok"), msg=result.stdout)

    def test_script_fails_for_invalid_profile_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "documents.db"
            self._prepare_db(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO document_headers (
                        document_id, doc_type, control_class, workflow_profile_id, register_binding, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    ("DOC-X", "VA", "CONTROLLED", "record_light", 1),
                )
                conn.commit()
            result = self._run_script(db_path, baseline_other_count=0)
            self.assertEqual(result.returncode, 2, msg=result.stderr + result.stdout)
            payload = json.loads(result.stdout.strip() or "{}")
            self.assertFalse(payload.get("ok"), msg=result.stdout)
            self.assertGreater(payload.get("metrics", {}).get("invalid_total", 0), 0)

    def test_script_reports_registry_drift_when_active_version_is_wrong(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_db = Path(tmp) / "documents.db"
            reg_db = Path(tmp) / "registry.db"
            self._prepare_db(docs_db)
            self._prepare_registry_db(reg_db)
            with closing(sqlite3.connect(docs_db)) as conn:
                conn.execute(
                    """
                    INSERT INTO document_headers (
                        document_id, doc_type, control_class, workflow_profile_id, register_binding, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    ("DOC-R", "VA", "CONTROLLED", "long_release", 1),
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
                        "DOC-R",
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
            with closing(sqlite3.connect(reg_db)) as conn:
                conn.execute(
                    """
                    INSERT INTO document_registry (
                        document_id, active_version, release_note, release_evidence_mode, register_state, is_findable,
                        valid_from, valid_until, last_update_event_id, last_update_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    ("DOC-R", 2, None, "WORKFLOW", "VALID", 1, None, None, "evt-1"),
                )
                conn.commit()

            result = self._run_script(docs_db, baseline_other_count=0, registry_db_path=reg_db)
            self.assertEqual(result.returncode, 2, msg=result.stderr + result.stdout)
            payload = json.loads(result.stdout.strip() or "{}")
            self.assertFalse(payload.get("ok"), msg=result.stdout)
            self.assertGreater(payload.get("registry_drift", {}).get("metrics", {}).get("drift_total", 0), 0)


if __name__ == "__main__":
    unittest.main()
