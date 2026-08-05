from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


class WorkflowProfileSchemaConstraintTest(unittest.TestCase):
    def _connect(self) -> sqlite3.Connection:
        root = Path(tempfile.mkdtemp(prefix="qmtool-docs-schema-"))
        db_path = root / "documents.db"
        conn = sqlite3.connect(db_path)
        for migration in (
            Path("modules/documents/migrations/0001_initial.sql"),
            Path("modules/documents/migrations/0002_workflow_profiles.sql"),
        ):
            conn.executescript(migration.read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT INTO workflow_profile_definitions (
                profile_code, label, control_class, is_active, active_version,
                created_at, created_by, updated_at, updated_by
            ) VALUES ('p1', 'P1', 'CONTROLLED', 1, 1, datetime('now'), 't', datetime('now'), 't')
            """
        )
        conn.execute(
            """
            INSERT INTO workflow_profile_versions (
                profile_version_id, profile_code, version_no, source_kind, change_reason,
                definition_hash, effective_from, release_evidence_mode, four_eyes_required,
                requires_editors, requires_reviewers, requires_approvers, allows_content_changes,
                created_at, created_by
            ) VALUES (
                'pv1', 'p1', 1, 'SEED', 'seed', 'hash', datetime('now'), 'WORKFLOW',
                0, 1, 1, 1, 1, datetime('now'), 't'
            )
            """
        )
        conn.commit()
        return conn

    def test_rejects_invalid_source_kind(self) -> None:
        with closing(self._connect()) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO workflow_profile_versions (
                        profile_version_id, profile_code, version_no, source_kind, change_reason,
                        definition_hash, effective_from, release_evidence_mode, four_eyes_required,
                        requires_editors, requires_reviewers, requires_approvers, allows_content_changes,
                        created_at, created_by
                    ) VALUES (
                        'pv2', 'p1', 2, 'OTHER', 'x', 'h2', datetime('now'), 'WORKFLOW',
                        0, 1, 1, 1, 1, datetime('now'), 't'
                    )
                    """
                )

    def test_rejects_in_progress_status_in_transitions(self) -> None:
        with closing(self._connect()) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO workflow_profile_transitions (
                        profile_transition_id, profile_version_id, transition_no, from_status, to_status,
                        required_role, decision_policy, signature_required, four_eyes_required,
                        revoke_if_changed, deadline_seconds, is_enabled
                    ) VALUES (
                        'pt1', 'pv1', 1, 'DRAFT', 'IN_PROGRESS', 'EDITOR', 'ONE_OF_POOL',
                        0, 0, 0, NULL, 1
                    )
                    """
                )

    def test_rejects_duplicate_transition_no(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO workflow_profile_transitions (
                    profile_transition_id, profile_version_id, transition_no, from_status, to_status,
                    required_role, decision_policy, signature_required, four_eyes_required,
                    revoke_if_changed, deadline_seconds, is_enabled
                ) VALUES (
                    'pt1', 'pv1', 1, 'DRAFT', 'IN_REVIEW', 'EDITOR', 'ONE_OF_POOL',
                    0, 0, 0, NULL, 1
                )
                """
            )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO workflow_profile_transitions (
                        profile_transition_id, profile_version_id, transition_no, from_status, to_status,
                        required_role, decision_policy, signature_required, four_eyes_required,
                        revoke_if_changed, deadline_seconds, is_enabled
                    ) VALUES (
                        'pt2', 'pv1', 1, 'IN_REVIEW', 'APPROVED', 'APPROVER', 'ONE_OF_POOL',
                        0, 0, 0, NULL, 1
                    )
                    """
                )

    def test_versions_are_immutable(self) -> None:
        with closing(self._connect()) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE workflow_profile_versions SET change_reason = 'x' WHERE profile_version_id = 'pv1'"
                )


if __name__ == "__main__":
    unittest.main()
