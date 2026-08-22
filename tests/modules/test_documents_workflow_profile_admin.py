from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from modules.documents.contracts import DocumentType
from modules.documents.errors import PermissionDeniedError, ValidationError
from modules.documents.workflow_profile_seed_reader import WorkflowProfileSeedReader
from modules.documents.workflow_profile_store import WorkflowProfileRelationalStore
from modules.usermanagement.api import UserContext
from modules.usermanagement.contracts import issue_user_context
from tests.database_helpers import make_docs_repository, make_documents_service_with_profiles
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID


def _actor(*, username: str, roles: tuple[str, ...], is_qmb: bool, **overrides) -> object:
    kwargs = {
        "user_id": f"{username}-id",
        "session_id": f"{username}-session",
        "request_id": f"{username}-request",
        "username": username,
        "global_roles": roles,
        "is_qmb": is_qmb,
        "authenticated_at": datetime.now(timezone.utc),
    }
    kwargs.update(overrides)
    return issue_user_context(**kwargs)


_VALID_TRANSITIONS = [
    {
        "transition_no": 1,
        "from_status": "DRAFT",
        "to_status": "IN_REVIEW",
        "required_role": "EDITOR",
        "decision_policy": "ONE_OF_POOL",
        "signature_required": True,
        "four_eyes_required": False,
    },
    {
        "transition_no": 2,
        "from_status": "IN_REVIEW",
        "to_status": "IN_APPROVAL",
        "required_role": "REVIEWER",
        "decision_policy": "ONE_OF_POOL",
        "signature_required": True,
        "four_eyes_required": False,
    },
    {
        "transition_no": 3,
        "from_status": "IN_APPROVAL",
        "to_status": "APPROVED",
        "required_role": "APPROVER",
        "decision_policy": "ONE_OF_POOL",
        "signature_required": True,
        "four_eyes_required": True,
    },
]


class DocumentsWorkflowProfileAdminTest(unittest.TestCase):
    def _service(self):
        root = Path(tempfile.mkdtemp(prefix="qmtool-docs-profiles-"))
        service, _store = make_documents_service_with_profiles(root / "documents.db")
        return service

    def test_admin_without_effective_qmb_is_rejected(self) -> None:
        service = self._service()
        with self.assertRaisesRegex(PermissionDeniedError, "effective QMB"):
            service.list_workflow_profile_definitions(
                actor=_actor(username="admin", roles=("Admin",), is_qmb=False)
            )

    def test_duck_typed_actor_is_rejected(self) -> None:
        service = self._service()
        fake = SimpleNamespace(
            is_confirmed=True,
            user_id="fake",
            session_id="s",
            request_id="r",
        organization_id=INSTALLATION_ORGANIZATION_ID,
            is_qmb=True,
            global_roles=frozenset({"QMB"}),
        )
        with self.assertRaisesRegex(PermissionDeniedError, "confirmed UserContext"):
            service.list_workflow_profile_definitions(actor=fake)

    def test_unconfirmed_context_is_rejected(self) -> None:
        service = self._service()
        unconfirmed = UserContext(
            user_id="u",
            session_id="s",
            request_id="r",
        organization_id=INSTALLATION_ORGANIZATION_ID,
            username="u",
            global_roles=frozenset({"QMB"}),
            is_qmb=True,
            authenticated_at=datetime.now(timezone.utc),
        )
        with self.assertRaisesRegex(PermissionDeniedError, "confirmed UserContext"):
            service.list_workflow_profile_definitions(actor=unconfirmed)

    def test_empty_ids_are_rejected(self) -> None:
        service = self._service()
        with self.assertRaises(Exception):
            _actor(username="qmb", roles=("QMB",), is_qmb=True, user_id="")

    def test_qmb_requires_change_reason_for_mutation(self) -> None:
        service = self._service()
        actor = _actor(username="qmb", roles=("QMB",), is_qmb=True)
        with self.assertRaisesRegex(ValidationError, "change_reason is required"):
            service.set_workflow_profile_active(
                "long_release",
                actor=actor,
                is_active=False,
                change_reason="",
            )

    def test_qmb_can_create_engine_compatible_profile(self) -> None:
        service = self._service()
        actor = _actor(username="qmb", roles=("QMB",), is_qmb=True)
        created = service.create_workflow_profile_definition(
            {
                "profile_code": "j03_admin_profile",
                "label": "J03 Admin Profile",
                "control_class": "CONTROLLED",
                "release_evidence_mode": "WORKFLOW",
                "requires_editors": True,
                "requires_reviewers": True,
                "requires_approvers": True,
                "allows_content_changes": True,
                "transitions": _VALID_TRANSITIONS,
            },
            actor=actor,
            change_reason="Create admin-managed profile",
        )
        self.assertEqual(created["profile_code"], "j03_admin_profile")
        listed = service.list_workflow_profile_versions("j03_admin_profile", actor=actor)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["source_kind"], "ADMIN")

    def test_all_assigned_decision_policy_is_rejected(self) -> None:
        service = self._service()
        actor = _actor(username="qmb", roles=("QMB",), is_qmb=True)
        with self.assertRaisesRegex(ValidationError, "unsupported decision_policy"):
            service.create_workflow_profile_definition(
                {
                    "profile_code": "bad_rule_profile",
                    "label": "Bad Rule",
                    "control_class": "CONTROLLED",
                    "transitions": [
                        {
                            "transition_no": 1,
                            "from_status": "DRAFT",
                            "to_status": "APPROVED",
                            "required_role": "EDITOR",
                            "decision_policy": "ALL_ASSIGNED",
                            "signature_required": False,
                            "four_eyes_required": False,
                        }
                    ],
                },
                actor=actor,
                change_reason="Reject unsupported engine rule",
            )

    def test_draft_to_in_progress_is_rejected(self) -> None:
        service = self._service()
        actor = _actor(username="qmb", roles=("QMB",), is_qmb=True)
        with self.assertRaisesRegex(ValidationError, "DRAFT"):
            service.create_workflow_profile_definition(
                {
                    "profile_code": "legacy_shape",
                    "label": "Legacy Shape",
                    "control_class": "CONTROLLED",
                    "transitions": [
                        {
                            "transition_no": 1,
                            "from_status": "DRAFT",
                            "to_status": "IN_PROGRESS",
                            "required_role": "EDITOR",
                            "decision_policy": "ONE_OF_POOL",
                            "signature_required": False,
                            "four_eyes_required": False,
                        },
                        {
                            "transition_no": 2,
                            "from_status": "IN_PROGRESS",
                            "to_status": "APPROVED",
                            "required_role": "APPROVER",
                            "decision_policy": "ONE_OF_POOL",
                            "signature_required": False,
                            "four_eyes_required": False,
                        },
                    ],
                },
                actor=actor,
                change_reason="Reject legacy IN_PROGRESS storage",
            )


class DocumentsWorkflowProfileImportTest(unittest.TestCase):
    def test_fresh_install_uses_bundled_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, store = make_documents_service_with_profiles(
                root / "documents.db",
                is_pre_j03_upgrade=False,
                legacy_profiles_path=root / "local.json",
            )
            profile = service.get_profile("long_release")
            self.assertEqual(profile.phases[0].value, "IN_PROGRESS")
            self.assertTrue(any(row.classification == "SEED" for row in store.last_import_report))

    def test_pre_j03_empty_db_uses_local_profiles_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "local_profiles.json"
            bundled = Path("modules/documents/workflow_profiles.json")
            payload = json.loads(bundled.read_text(encoding="utf-8"))
            # Local-only extra profile + modified label on long_release
            payload["profiles"][0]["label"] = "Local Long Release"
            payload["profiles"].append(
                {
                    "profile_id": "local_only",
                    "label": "Local Only",
                    "control_class": "CONTROLLED",
                    "phases": ["IN_PROGRESS", "APPROVED"],
                    "four_eyes_required": False,
                    "signature_required_transitions": [],
                    "requires_editors": True,
                    "requires_reviewers": False,
                    "requires_approvers": False,
                    "allows_content_changes": True,
                    "release_evidence_mode": "WORKFLOW",
                }
            )
            # Drop one package profile so package-only skip is visible
            payload["profiles"] = [p for p in payload["profiles"] if p["profile_id"] != "record_light"]
            local.write_text(json.dumps(payload), encoding="utf-8")
            _service, store = make_documents_service_with_profiles(
                root / "documents.db",
                is_pre_j03_upgrade=True,
                legacy_profiles_path=local,
                bundled_seed_path=bundled,
            )
            codes = {row.profile_id: row for row in store.last_import_report}
            self.assertEqual(codes["long_release"].classification, "MIGRATED")
            self.assertEqual(codes["local_only"].classification, "MIGRATED")
            self.assertEqual(codes["record_light"].import_status, "skipped_package_only")
            self.assertIn("local_only", {d["profile_code"] for d in store.list_definitions()})
            self.assertNotIn("record_light", {d["profile_code"] for d in store.list_definitions()})

    def test_invalid_local_profile_blocks_without_partial_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "bad.json"
            local.write_text(json.dumps({"profiles": [{"profile_id": "x"}]}), encoding="utf-8")
            repo = make_docs_repository(root / "documents.db")
            store = WorkflowProfileRelationalStore(
                repo,
                bundled_seed_path=Path("modules/documents/workflow_profiles.json"),
                legacy_profiles_path=local,
                is_pre_j03_upgrade=True,
            )
            with self.assertRaises(ValidationError):
                store.ensure_seeded(WorkflowProfileSeedReader())
            self.assertFalse(store.has_profiles())

    def test_idempotent_reseed_is_consistency_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, store = make_documents_service_with_profiles(root / "documents.db")
            first = store.list_definitions()
            store.ensure_seeded(WorkflowProfileSeedReader())
            self.assertEqual(store.list_definitions(), first)
            self.assertEqual(
                service.resolve_workflow_profile_for_document_type(DocumentType.EXT),
                "external_control",
            )
            self.assertEqual(
                service.resolve_workflow_profile_for_document_type(DocumentType.VA),
                "long_release",
            )


class DocumentsWorkflowProfileBindingTest(unittest.TestCase):
    def test_create_and_import_use_document_type_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _store = make_documents_service_with_profiles(root / "documents.db")
            va = service.create_document_version("VA-1", 1, doc_type=DocumentType.VA)
            self.assertEqual(va.workflow_profile_id, "long_release")
            pdf = root / "ext.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            from modules.documents.contracts import SystemRole
            from modules.documents.storage import FileSystemDocumentsStorage

            service_with_storage, _ = make_documents_service_with_profiles(
                root / "documents2.db",
                storage_port=FileSystemDocumentsStorage(root / "artifacts"),
            )
            imported = service_with_storage.import_existing_pdf(
                "EXT-1",
                1,
                pdf,
                actor_user_id="admin",
                actor_role=SystemRole.ADMIN,
            )
            self.assertEqual(imported.workflow_profile_id, "external_control")

    def test_override_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _store = make_documents_service_with_profiles(root / "documents.db")
            with self.assertRaisesRegex(ValidationError, "override is not allowed"):
                service.create_document_version(
                    "VA-2",
                    1,
                    doc_type=DocumentType.VA,
                    workflow_profile_id="Controlled_Short_woSig",
                )
            other = service.create_document_version(
                "OTHER-1",
                1,
                doc_type=DocumentType.OTHER,
                workflow_profile_id="long_release",
            )
            self.assertEqual(other.workflow_profile_id, "long_release")


class DocumentsWorkflowProfileFallbackTest(unittest.TestCase):
    def test_missing_store_is_configuration_error(self) -> None:
        from modules.documents.service import DocumentsService

        service = DocumentsService()
        with self.assertRaisesRegex(ValidationError, "not configured"):
            service.get_profile("long_release")


if __name__ == "__main__":
    unittest.main()
