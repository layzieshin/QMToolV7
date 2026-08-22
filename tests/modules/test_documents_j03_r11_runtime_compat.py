"""J03-R1.1: runtime IN_PROGRESS compatibility + workflow-start binding."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from modules.documents.contracts import (
    ControlClass,
    DocumentStatus,
    DocumentType,
    RejectionReason,
    SystemRole,
    WorkflowProfile,
)
from modules.documents.errors import ValidationError
from modules.documents.sqlite_repository import SQLiteDocumentsRepository
from modules.documents.workflow_profile_runtime_adapter import (
    normalize_legacy_status_for_storage,
    runtime_status_from_relational,
    runtime_transition_key_from_relational,
)
from modules.usermanagement.contracts import issue_user_context
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from tests.database_helpers import make_documents_service_with_profiles


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


def _qmb():
    return issue_user_context(
        user_id="qmb-id",
        session_id="qmb-session",
        request_id="qmb-request",
        organization_id=INSTALLATION_ORGANIZATION_ID,
        username="qmb",
        global_roles=("QMB",),
        is_qmb=True,
        authenticated_at=datetime.now(timezone.utc),
    )


class DocumentsJ03R11RuntimeCompatTest(unittest.TestCase):
    def test_adapter_maps_draft_and_in_progress_at_single_boundary(self) -> None:
        self.assertEqual(normalize_legacy_status_for_storage("IN_PROGRESS"), "DRAFT")
        self.assertEqual(runtime_status_from_relational("DRAFT"), DocumentStatus.IN_PROGRESS)
        self.assertEqual(
            runtime_transition_key_from_relational("DRAFT", "IN_REVIEW"),
            "IN_PROGRESS->IN_REVIEW",
        )

    def test_relational_draft_profile_reconstructs_runtime_in_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, store = make_documents_service_with_profiles(
                Path(tmp) / "documents.db",
                signature_api=_FakeSignatureApi(),
            )
            definition = store.get_active_definition("long_release")
            self.assertEqual(definition.transitions[0].from_status, "DRAFT")
            runtime = definition.to_runtime_profile()
            self.assertEqual(runtime.phases[0], DocumentStatus.IN_PROGRESS)
            self.assertIn("IN_PROGRESS->IN_REVIEW", runtime.signature_required_transitions)
            loaded = service.get_profile("long_release")
            self.assertEqual(loaded.phases[0], DocumentStatus.IN_PROGRESS)

    def test_legacy_snapshot_with_in_progress_loads_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "documents.db"
            service, _ = make_documents_service_with_profiles(db_path, signature_api=_FakeSignatureApi())
            state = service.create_document_version("DOC-SNAP-1", 1, owner_user_id="owner-1")
            state = service.assign_workflow_roles(
                state,
                editors={"editor-1"},
                reviewers={"reviewer-1"},
                approvers={"approver-1"},
            )
            started = service.start_workflow(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            self.assertEqual(started.status, DocumentStatus.IN_PROGRESS)
            snapshot_before = started.workflow_profile
            self.assertIsNotNone(snapshot_before)
            self.assertEqual(snapshot_before.phases[0], DocumentStatus.IN_PROGRESS)

            repo = SQLiteDocumentsRepository(db_path)
            raw_before = None
            with repo._connect() as conn:
                row = conn.execute(
                    "SELECT workflow_profile_json FROM document_versions WHERE document_id=? AND version=?",
                    ("DOC-SNAP-1", 1),
                ).fetchone()
                raw_before = row["workflow_profile_json"]
                payload = json.loads(raw_before)
                self.assertEqual(payload["phases"][0], "IN_PROGRESS")
                # Simulate an older snapshot that already existed with IN_PROGRESS.
                conn.execute(
                    "UPDATE document_versions SET workflow_profile_json=? WHERE document_id=? AND version=?",
                    (raw_before, "DOC-SNAP-1", 1),
                )
                conn.commit()

            reloaded = service.get_document_version("DOC-SNAP-1", 1)
            self.assertEqual(reloaded.status, DocumentStatus.IN_PROGRESS)
            self.assertEqual(reloaded.workflow_profile.phases[0], DocumentStatus.IN_PROGRESS)
            with repo._connect() as conn:
                row = conn.execute(
                    "SELECT workflow_profile_json FROM document_versions WHERE document_id=? AND version=?",
                    ("DOC-SNAP-1", 1),
                ).fetchone()
                self.assertEqual(row["workflow_profile_json"], raw_before)

            continued = service.complete_editing(
                reloaded,
                sign_request={"step": "edit_complete"},
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            )
            self.assertEqual(continued.status, DocumentStatus.IN_REVIEW)

    def test_reject_returns_to_in_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_documents_service_with_profiles(
                Path(tmp) / "documents.db",
                signature_api=_FakeSignatureApi(),
            )
            state = service.create_document_version("DOC-REJ-1", 1, owner_user_id="owner-1")
            state = service.assign_workflow_roles(
                state,
                editors={"editor-1"},
                reviewers={"reviewer-1"},
                approvers={"approver-1"},
            )
            state = service.start_workflow(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            state = service.complete_editing(state, sign_request={"step": "edit"})
            rejected = service.reject_review(
                state,
                "reviewer-1",
                RejectionReason(template_text="fix"),
            )
            self.assertEqual(rejected.status, DocumentStatus.IN_PROGRESS)

    def test_upgrade_does_not_rewrite_existing_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "documents.db"
            service, _ = make_documents_service_with_profiles(db_path, signature_api=_FakeSignatureApi())
            state = service.create_document_version("DOC-UPG-1", 1, owner_user_id="owner-1")
            state = service.assign_workflow_roles(
                state,
                editors={"e"},
                reviewers={"r"},
                approvers={"a"},
            )
            started = service.start_workflow(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            repo = SQLiteDocumentsRepository(db_path)
            with repo._connect() as conn:
                before = conn.execute(
                    "SELECT workflow_profile_json FROM document_versions WHERE document_id=? AND version=?",
                    ("DOC-UPG-1", 1),
                ).fetchone()["workflow_profile_json"]

            # Re-open service against same DB (upgrade/idempotent seed path).
            service2, _ = make_documents_service_with_profiles(db_path, signature_api=_FakeSignatureApi())
            reloaded = service2.get_document_version("DOC-UPG-1", 1)
            self.assertEqual(reloaded.status, DocumentStatus.IN_PROGRESS)
            with repo._connect() as conn:
                after = conn.execute(
                    "SELECT workflow_profile_json FROM document_versions WHERE document_id=? AND version=?",
                    ("DOC-UPG-1", 1),
                ).fetchone()["workflow_profile_json"]
            self.assertEqual(before, after)
            self.assertEqual(started.workflow_profile_id, reloaded.workflow_profile_id)


class DocumentsJ03R11WorkflowStartBindingTest(unittest.TestCase):
    def test_start_uses_bound_profile_and_keeps_workflow_profile_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_documents_service_with_profiles(
                Path(tmp) / "documents.db",
                signature_api=_FakeSignatureApi(),
            )
            state = service.create_document_version(
                "DOC-BIND-1",
                1,
                owner_user_id="owner-1",
                doc_type=DocumentType.VA,
            )
            self.assertEqual(state.workflow_profile_id, "long_release")
            state = service.assign_workflow_roles(
                state,
                editors={"e"},
                reviewers={"r"},
                approvers={"a"},
            )
            started = service.start_workflow(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            self.assertEqual(started.workflow_profile_id, "long_release")
            self.assertEqual(started.workflow_profile.profile_id, "long_release")
            self.assertEqual(started.workflow_profile.phases[0], DocumentStatus.IN_PROGRESS)

    def test_matching_compat_profile_id_does_not_change_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_documents_service_with_profiles(
                Path(tmp) / "documents.db",
                signature_api=_FakeSignatureApi(),
            )
            state = service.create_document_version("DOC-BIND-2", 1, owner_user_id="owner-1")
            state = service.assign_workflow_roles(
                state,
                editors={"e"},
                reviewers={"r"},
                approvers={"a"},
            )
            started = service.start_workflow(
                state,
                profile_id="long_release",
                actor_user_id="owner-1",
                actor_role=SystemRole.USER,
            )
            self.assertEqual(started.workflow_profile_id, "long_release")

    def test_mismatched_api_profile_id_is_rejected_for_va(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_documents_service_with_profiles(
                Path(tmp) / "documents.db",
                signature_api=_FakeSignatureApi(),
            )
            state = service.create_document_version(
                "DOC-BIND-3",
                1,
                owner_user_id="owner-1",
                doc_type=DocumentType.VA,
            )
            state = service.assign_workflow_roles(
                state,
                editors={"e"},
                reviewers={"r"},
                approvers={"a"},
            )
            with self.assertRaisesRegex(ValidationError, "does not match bound workflow_profile_id"):
                service.start_workflow(
                    state,
                    profile_id="external_control",
                    actor_user_id="owner-1",
                    actor_role=SystemRole.USER,
                )
            unchanged = service.get_document_version("DOC-BIND-3", 1)
            self.assertEqual(unchanged.status, DocumentStatus.PLANNED)
            self.assertEqual(unchanged.workflow_profile_id, "long_release")

    def test_allowed_override_at_document_create_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_documents_service_with_profiles(
                Path(tmp) / "documents.db",
                signature_api=_FakeSignatureApi(),
            )
            service.create_workflow_profile_definition(
                {
                    "profile_code": "alt_release",
                    "label": "Alt",
                    "control_class": "CONTROLLED",
                    "requires_editors": True,
                    "requires_reviewers": True,
                    "requires_approvers": True,
                    "allows_content_changes": True,
                    "release_evidence_mode": "WORKFLOW",
                    "transitions": [
                        {
                            "transition_no": 1,
                            "from_status": "DRAFT",
                            "to_status": "APPROVED",
                            "required_role": "EDITOR",
                            "decision_policy": "ONE_OF_POOL",
                            "signature_required": False,
                            "four_eyes_required": False,
                        }
                    ],
                },
                actor=_qmb(),
                change_reason="override fixture",
            )
            state = service.create_document_version(
                "DOC-BIND-4",
                1,
                owner_user_id="owner-1",
                doc_type=DocumentType.OTHER,
                workflow_profile_id="alt_release",
            )
            self.assertEqual(state.workflow_profile_id, "alt_release")
            state = service.assign_workflow_roles(
                state,
                editors={"e"},
                reviewers={"r"},
                approvers={"a"},
            )
            started = service.start_workflow(state, actor_user_id="owner-1", actor_role=SystemRole.USER)
            self.assertEqual(started.workflow_profile_id, "alt_release")
            self.assertEqual(started.status, DocumentStatus.IN_PROGRESS)

    def test_cli_and_pyqt_start_paths_do_not_transmit_free_profile(self) -> None:
        from interfaces.cli.commands import documents_commands as docs_cmd
        from interfaces.pyqt.contributions.documents_workflow import actions_mixin

        with tempfile.TemporaryDirectory() as tmp:
            service, _ = make_documents_service_with_profiles(
                Path(tmp) / "documents.db",
                signature_api=_FakeSignatureApi(),
            )
            state = service.create_document_version(
                "DOC-BIND-5",
                1,
                owner_user_id="owner-1",
                doc_type=DocumentType.VA,
            )
            state = service.assign_workflow_roles(
                state,
                editors={"e"},
                reviewers={"r"},
                approvers={"a"},
            )

            # CLI command path: optional profile_id only.
            api = MagicMock()
            api.start_workflow.side_effect = lambda st, **kwargs: service.start_workflow(st, **kwargs)
            current_user = MagicMock(user_id="owner-1")
            # Simulate the command body.
            with self.assertRaisesRegex(ValidationError, "does not match bound workflow_profile_id"):
                api.start_workflow(
                    state,
                    profile_id="external_control",
                    actor_user_id=current_user.user_id,
                    actor_role=SystemRole.USER,
                )

            started = api.start_workflow(
                state,
                profile_id=None,
                actor_user_id=current_user.user_id,
                actor_role=SystemRole.USER,
            )
            self.assertEqual(started.workflow_profile_id, "long_release")

            # PyQt adapter now calls start_workflow without a free profile argument.
            source = Path(actions_mixin.__file__).read_text(encoding="utf-8")
            self.assertIn("self._wf.start_workflow(", source)
            self.assertNotIn("get_profile(cfg.profile_id)", source)
            self.assertNotIn("self._wf.start_workflow(state, profile,", source)
            # documents CLI no longer resolves a free profile before start.
            cli_source = Path(docs_cmd.__file__).read_text(encoding="utf-8")
            self.assertIn("profile_id=args.profile_id", cli_source)
            self.assertNotIn("get_profile(args.profile_id)", cli_source)


if __name__ == "__main__":
    unittest.main()
