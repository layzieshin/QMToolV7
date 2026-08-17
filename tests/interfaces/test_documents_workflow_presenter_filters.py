from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from interfaces.pyqt.presenters.documents_workflow_filter_presenter import DocumentsWorkflowFilterPresenter
from interfaces.pyqt.presenters.documents_workflow_presenter import DocumentsWorkflowPresenter
from modules.documents.contracts import ArtifactType, DocumentStatus, SystemRole


@dataclass
class _Row:
    document_id: str
    version: int
    owner_user_id: str | None
    title: str
    status: DocumentStatus
    workflow_active: bool


@dataclass
class _Assignments:
    editors: set[str]
    reviewers: set[str]
    approvers: set[str]


@dataclass
class _State:
    owner_user_id: str
    status: DocumentStatus
    workflow_active: bool
    assignments: _Assignments
    available_actions: frozenset[str] | None = field(default=None)


class DocumentsWorkflowFilterPresenterTest(unittest.TestCase):
    def test_quick_filter_presets(self) -> None:
        presenter = DocumentsWorkflowFilterPresenter()
        self.assertEqual(presenter.preset("tasks").scope, "tasks")
        self.assertEqual(presenter.preset("review").status_filter, DocumentStatus.IN_REVIEW)
        self.assertEqual(presenter.preset("approval").status_filter, DocumentStatus.IN_APPROVAL)

    def test_filter_rows_combines_scope_and_advanced_filters(self) -> None:
        presenter = DocumentsWorkflowFilterPresenter()
        rows = [
            _Row("DOC-1", 1, "u1", "Safety", DocumentStatus.IN_REVIEW, True),
            _Row("DOC-2", 1, "u2", "Training", DocumentStatus.ARCHIVED, False),
            _Row("DOC-3", 2, "u1", "Workflow", DocumentStatus.IN_PROGRESS, True),
        ]
        result = presenter.filter_rows(
            rows,
            scope="mine",
            user_id="u1",
            owner_contains="u1",
            title_contains="w",
            workflow_active="true",
            active_version="all",
        )
        typed_result = [r for r in result if isinstance(r, _Row)]
        self.assertEqual([(r.document_id, r.version) for r in typed_result], [("DOC-3", 2)])


class DocumentsWorkflowPresenterVisibilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.presenter = DocumentsWorkflowPresenter()

    def test_create_only_from_backend_capability(self) -> None:
        visible = self.presenter.visible_actions_for_context(
            None,
            user_id="u-qmb",
            user_role=SystemRole.QMB,
            can_create_new_documents=True,
        )
        self.assertEqual(visible, {"new"})
        denied = self.presenter.visible_actions_for_context(
            None,
            user_id="u-admin",
            user_role=SystemRole.ADMIN,
            can_create_new_documents=False,
        )
        self.assertNotIn("new", denied)

    def test_missing_available_actions_is_fail_closed(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.PLANNED,
            workflow_active=False,
            assignments=_Assignments(editors=set(), reviewers=set(), approvers=set()),
            available_actions=None,
        )
        visible = self.presenter.visible_actions_for_context(
            state, user_id="owner-1", user_role=SystemRole.USER
        )
        self.assertEqual(visible, set())

    def test_empty_available_actions_is_fail_closed(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.IN_PROGRESS,
            workflow_active=True,
            assignments=_Assignments(editors={"ed-1"}, reviewers=set(), approvers=set()),
            available_actions=frozenset(),
        )
        visible = self.presenter.visible_actions_for_context(
            state, user_id="ed-1", user_role=SystemRole.USER, can_create_new_documents=True
        )
        self.assertEqual(visible, {"new"})

    def test_known_backend_actions_map_to_ui_keys(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.IN_REVIEW,
            workflow_active=True,
            assignments=_Assignments(editors={"ed-1"}, reviewers={"rev-1"}, approvers={"app-1"}),
            available_actions=frozenset(
                {"open_source", "review_accept", "review_reject", "abort", "comments"}
            ),
        )
        visible = self.presenter.visible_actions_for_context(state, user_id="rev-1", user_role=SystemRole.USER)
        self.assertEqual(
            visible,
            {"edit", "review_accept", "review_reject", "abort", "comments"},
        )

    def test_unknown_backend_actions_are_ignored(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.PLANNED,
            workflow_active=False,
            assignments=_Assignments(editors=set(), reviewers=set(), approvers=set()),
            available_actions=frozenset({"start", "not_a_real_action"}),
        )
        visible = self.presenter.visible_actions_for_context(state, user_id="owner-1")
        self.assertEqual(visible, {"start"})

    def test_local_role_does_not_unlock_mutations_without_actions(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.IN_PROGRESS,
            workflow_active=True,
            assignments=_Assignments(editors={"ed-1"}, reviewers=set(), approvers=set()),
            available_actions=None,
        )
        visible = self.presenter.visible_actions_for_context(
            state, user_id="u-qmb", user_role=SystemRole.QMB, can_create_new_documents=True
        )
        self.assertEqual(visible, {"new"})
        self.assertNotIn("abort", visible)
        self.assertNotIn("edit", visible)

    def test_default_artifact_priority_prefers_signed_pdf_in_review_and_approval(self) -> None:
        review_order = self.presenter.default_artifact_priority(DocumentStatus.IN_REVIEW)
        approval_order = self.presenter.default_artifact_priority(DocumentStatus.IN_APPROVAL)
        self.assertEqual(review_order[:2], [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF])
        self.assertEqual(approval_order[:2], [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF])

    def test_presenter_module_does_not_import_compute_available_actions(self) -> None:
        import interfaces.pyqt.presenters.documents_workflow_presenter as mod
        import inspect

        source = inspect.getsource(mod)
        self.assertNotIn("compute_available_actions", source)


if __name__ == "__main__":
    unittest.main()
