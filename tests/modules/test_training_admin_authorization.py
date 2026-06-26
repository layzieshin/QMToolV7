from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

from modules.training.api import TrainingAdminApi
from modules.training.contracts import DocumentTagSet
from modules.training.errors import TrainingPermissionError


class _Noop:
    def __getattr__(self, _name):
        def _method(*_args, **_kwargs):
            return []

        return _method


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self._snapshot_repo = self

    def __getattr__(self, name: str):
        def _method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return f"{name}-result"

        return _method


class _DocTagService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def set_document_tags(self, document_id: str, tags: list[str]) -> DocumentTagSet:
        self.calls.append(("set_document_tags", (document_id, tags), {}))
        return DocumentTagSet(document_id=document_id, tags=frozenset(tags))

    def list_document_tags(self, document_id: str) -> DocumentTagSet:
        self.calls.append(("list_document_tags", (document_id,), {}))
        return DocumentTagSet(document_id=document_id, tags=frozenset())

    def list_all_document_tags(self) -> list[DocumentTagSet]:
        self.calls.append(("list_all_document_tags", (), {}))
        return []

    def list_tag_pool(self) -> list[str]:
        self.calls.append(("list_tag_pool", (), {}))
        return []


class _CatalogReader(_Recorder):
    def list_released_documents(self):
        self.calls.append(("list_released_documents", (), {}))
        return [SimpleNamespace(document_id="DOC-1", version=1, title="Document")]


class _QuizBindingService(_Recorder):
    def list_pending_quiz_mappings(self):
        self.calls.append(("list_pending_quiz_mappings", (), {}))
        return [
            SimpleNamespace(
                import_id="import-1",
                document_id="DOC-1",
                document_version=1,
                created_at=datetime.now(timezone.utc),
                question_count=3,
            )
        ]


@dataclass(frozen=True)
class _User:
    user_id: str
    username: str
    role: str
    is_qmb: bool = False


class _UserManagement:
    def __init__(self, user: _User | None) -> None:
        self._user = user

    def get_current_user(self):
        return self._user


def _make_admin_api(user: _User | None) -> tuple[TrainingAdminApi, dict[str, object]]:
    services = {
        "catalog": _CatalogReader(),
        "quiz_import": _Recorder(),
        "quiz_binding": _QuizBindingService(),
        "doc_tags": _DocTagService(),
        "user_tags": _Recorder(),
        "manual": _Recorder(),
        "exemption": _Recorder(),
        "projector": _Recorder(),
        "comments": _Recorder(),
        "report": _Recorder(),
    }
    doc_tags = _DocTagService()
    api = TrainingAdminApi(
        catalog_reader=services["catalog"],
        quiz_import=services["quiz_import"],
        quiz_binding=services["quiz_binding"],
        doc_tag_service=services["doc_tags"],
        user_tag_service=services["user_tags"],
        manual_service=services["manual"],
        exemption_service=services["exemption"],
        projector=services["projector"],
        comment_service=services["comments"],
        report_service=services["report"],
        usermanagement_service=_UserManagement(user),
    )
    return api, services


def _service_calls(services: dict[str, object]) -> list[tuple[str, tuple[object, ...], dict[str, object]]]:
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    for service in services.values():
        service_calls = getattr(service, "calls", None)
        if isinstance(service_calls, list):
            calls.extend(service_calls)
    return calls


PROTECTED_MUTATIONS = [
    ("import_quiz_json", (b"{}",), {"force": True}, "import_quiz_json"),
    ("bind_quiz_to_document", ("import-1", "DOC-1", 1), {}, "bind_quiz_to_document"),
    ("replace_quiz_binding", ("DOC-1", 1, "import-2", "admin"), {}, "replace_quiz_binding"),
    ("set_document_tags", ("DOC-1", ["safety"]), {}, "set_document_tags"),
    ("set_user_tags", ("user-1", ["quality"]), {}, "set_user_tags"),
    ("grant_manual_assignment", ("user-1", "DOC-1", "Pflicht", "admin"), {}, "grant_manual_assignment"),
    ("revoke_manual_assignment", ("assignment-1", "admin"), {}, "revoke_manual_assignment"),
    ("grant_exemption", ("user-1", "DOC-1", 1, "Grund", "admin"), {}, "grant_exemption"),
    ("revoke_exemption", ("exemption-1", "admin"), {}, "revoke_exemption"),
    ("rebuild_assignment_snapshots", (), {}, "rebuild_all"),
    ("resolve_comment", ("comment-1", "admin", None), {}, "resolve_comment"),
    ("inactivate_comment", ("comment-1", "admin", None), {}, "inactivate_comment"),
    ("export_training_matrix", (), {}, "export_training_matrix"),
]

PROTECTED_READS = [
    ("list_assignable_documents", (), {}, "list_released_documents"),
    ("inspect_quiz_json", (b"{}",), {}, "inspect_quiz_json"),
    ("list_pending_quiz_mappings", (), {}, "list_pending_quiz_mappings"),
    ("list_quiz_bindings", (), {}, "list_quiz_bindings"),
    ("check_quiz_replacement_conflict", ("DOC-1", 1, "import-1"), {}, "check_quiz_replacement_conflict"),
    ("list_document_tags", ("DOC-1",), {}, "list_document_tags"),
    ("list_all_document_tags", (), {}, "list_all_document_tags"),
    ("list_tag_pool", (), {}, "list_tag_pool"),
    ("list_user_tags", ("user-1",), {}, "list_user_tags"),
    ("list_all_user_tags", (), {}, "list_all_user_tags"),
    ("list_assignment_snapshots", (), {}, "list_snapshots"),
    ("list_active_comments", (), {}, "list_active_comments"),
    ("get_training_statistics", (), {}, "get_training_statistics"),
    ("list_training_audit_log", (), {}, "list_training_audit_log"),
]


class TrainingAdminAuthorizationTest(unittest.TestCase):
    def test_set_document_tags_allows_admin(self) -> None:
        api, services = _make_admin_api(_User("admin-1", "admin", "Admin"))

        result = api.set_document_tags("DOC-1", ["safety"])

        self.assertEqual(result.tags, frozenset({"safety"}))
        self.assertEqual(services["doc_tags"].calls, [("set_document_tags", ("DOC-1", ["safety"]), {})])

    def test_set_document_tags_allows_qmb(self) -> None:
        api, services = _make_admin_api(_User("qmb-1", "qmb", "QMB"))

        result = api.set_document_tags("DOC-1", ["quality"])

        self.assertEqual(result.tags, frozenset({"quality"}))
        self.assertEqual(services["doc_tags"].calls, [("set_document_tags", ("DOC-1", ["quality"]), {})])

    def test_set_document_tags_allows_effective_qmb(self) -> None:
        api, services = _make_admin_api(_User("user-qmb", "user-qmb", "User", is_qmb=True))

        result = api.set_document_tags("DOC-1", ["training"])

        self.assertEqual(result.tags, frozenset({"training"}))
        self.assertEqual(services["doc_tags"].calls, [("set_document_tags", ("DOC-1", ["training"]), {})])

    def test_set_document_tags_blocks_plain_user(self) -> None:
        api, services = _make_admin_api(_User("user-1", "user", "User"))

        with self.assertRaises(TrainingPermissionError):
            api.set_document_tags("DOC-1", ["blocked"])

        self.assertEqual(_service_calls(services), [])

    def test_set_document_tags_blocks_missing_user(self) -> None:
        api, services = _make_admin_api(None)

        with self.assertRaises(TrainingPermissionError):
            api.set_document_tags("DOC-1", ["blocked"])

        self.assertEqual(_service_calls(services), [])

    def test_set_document_tags_blocks_unknown_role(self) -> None:
        api, services = _make_admin_api(_User("guest-1", "guest", "Guest"))

        with self.assertRaises(TrainingPermissionError):
            api.set_document_tags("DOC-1", ["blocked"])

        self.assertEqual(_service_calls(services), [])

    def test_set_document_tags_blocks_missing_auth_context(self) -> None:
        doc_tags = _DocTagService()
        api = TrainingAdminApi(
            catalog_reader=_Noop(),
            quiz_import=_Noop(),
            quiz_binding=_Noop(),
            doc_tag_service=doc_tags,
            user_tag_service=_Noop(),
            manual_service=_Noop(),
            exemption_service=_Noop(),
            projector=_Noop(),
            comment_service=_Noop(),
            report_service=_Noop(),
        )

        with self.assertRaises(TrainingPermissionError):
            api.set_document_tags("DOC-1", ["blocked"])

        self.assertEqual(doc_tags.calls, [])

    def test_admin_mutations_allow_admin_qmb_and_effective_qmb(self) -> None:
        allowed_users = [
            _User("admin-1", "admin", "Admin"),
            _User("qmb-1", "qmb", "QMB"),
            _User("user-qmb", "user-qmb", "User", is_qmb=True),
        ]
        for user in allowed_users:
            for method_name, args, kwargs, delegated_method in PROTECTED_MUTATIONS:
                with self.subTest(user=user.user_id, method=method_name):
                    api, services = _make_admin_api(user)
                    getattr(api, method_name)(*args, **kwargs)

                    self.assertIn(delegated_method, [name for name, _args, _kwargs in _service_calls(services)])

    def test_admin_mutations_block_unauthorized_users_before_delegation(self) -> None:
        blocked_users = [
            _User("user-1", "user", "User"),
            None,
            _User("guest-1", "guest", "Guest"),
        ]
        for user in blocked_users:
            for method_name, args, kwargs, _delegated_method in PROTECTED_MUTATIONS:
                with self.subTest(user=getattr(user, "user_id", "none"), method=method_name):
                    api, services = _make_admin_api(user)

                    with self.assertRaises(TrainingPermissionError):
                        getattr(api, method_name)(*args, **kwargs)

                    self.assertEqual(_service_calls(services), [])

    def test_admin_reads_allow_admin_qmb_and_effective_qmb(self) -> None:
        allowed_users = [
            _User("admin-1", "admin", "Admin"),
            _User("qmb-1", "qmb", "QMB"),
            _User("user-qmb", "user-qmb", "User", is_qmb=True),
        ]
        for user in allowed_users:
            for method_name, args, kwargs, delegated_method in PROTECTED_READS:
                with self.subTest(user=user.user_id, method=method_name):
                    api, services = _make_admin_api(user)
                    getattr(api, method_name)(*args, **kwargs)

                    self.assertIn(delegated_method, [name for name, _args, _kwargs in _service_calls(services)])

    def test_admin_reads_block_unauthorized_users_before_delegation(self) -> None:
        blocked_users = [
            _User("user-1", "user", "User"),
            None,
            _User("guest-1", "guest", "Guest"),
        ]
        for user in blocked_users:
            for method_name, args, kwargs, _delegated_method in PROTECTED_READS:
                with self.subTest(user=getattr(user, "user_id", "none"), method=method_name):
                    api, services = _make_admin_api(user)

                    with self.assertRaises(TrainingPermissionError):
                        getattr(api, method_name)(*args, **kwargs)

                    self.assertEqual(_service_calls(services), [])


if __name__ == "__main__":
    unittest.main()
