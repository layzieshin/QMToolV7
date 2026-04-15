from __future__ import annotations

import unittest
from dataclasses import dataclass

from interfaces.pyqt.presenters.documents_workflow_filter_presenter import DocumentsWorkflowFilterPresenter
from interfaces.pyqt.presenters.documents_workflow_presenter import DocumentsWorkflowPresenter
from modules.documents.contracts import DocumentStatus, SystemRole


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
            active_version="true",
        )
        self.assertEqual([(r.document_id, r.version) for r in result], [("DOC-3", 2)])


class DocumentsWorkflowPresenterVisibilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.presenter = DocumentsWorkflowPresenter()

    def test_only_qmb_sees_new_without_selection(self) -> None:
        visible = self.presenter.visible_actions_for_context(None, user_id="u-qmb", user_role=SystemRole.QMB)
        self.assertEqual(visible, {"new"})

    def test_owner_can_start_when_workflow_not_active(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.PLANNED,
            workflow_active=False,
            assignments=_Assignments(editors=set(), reviewers=set(), approvers=set()),
        )
        visible = self.presenter.visible_actions_for_context(state, user_id="owner-1", user_role=SystemRole.USER)
        self.assertIn("start", visible)
        self.assertNotIn("abort", visible)

    def test_abort_visible_for_qmb_when_workflow_active(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.IN_PROGRESS,
            workflow_active=True,
            assignments=_Assignments(editors={"ed-1"}, reviewers=set(), approvers=set()),
        )
        visible = self.presenter.visible_actions_for_context(state, user_id="u-qmb", user_role=SystemRole.QMB)
        self.assertIn("new", visible)
        self.assertIn("abort", visible)

    def test_reviewer_sees_review_actions_in_review_phase(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.IN_REVIEW,
            workflow_active=True,
            assignments=_Assignments(editors={"ed-1"}, reviewers={"rev-1"}, approvers={"app-1"}),
        )
        visible = self.presenter.visible_actions_for_context(state, user_id="rev-1", user_role=SystemRole.USER)
        self.assertIn("edit", visible)
        self.assertIn("review_accept", visible)
        self.assertIn("review_reject", visible)
        self.assertNotIn("approval_accept", visible)

    def test_approver_sees_approval_actions_in_approval_phase(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.IN_APPROVAL,
            workflow_active=True,
            assignments=_Assignments(editors={"ed-1"}, reviewers={"rev-1"}, approvers={"app-1"}),
        )
        visible = self.presenter.visible_actions_for_context(state, user_id="app-1", user_role=SystemRole.USER)
        self.assertIn("edit", visible)
        self.assertIn("approval_accept", visible)
        self.assertIn("approval_reject", visible)

    def test_owner_does_not_get_start_outside_planned_status(self) -> None:
        state = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.IN_REVIEW,
            workflow_active=False,
            assignments=_Assignments(editors=set(), reviewers={"rev-1"}, approvers=set()),
        )
        visible = self.presenter.visible_actions_for_context(state, user_id="owner-1", user_role=SystemRole.USER)
        self.assertNotIn("start", visible)

    def test_editor_open_edit_depends_on_phase_assignment(self) -> None:
        in_progress = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.IN_PROGRESS,
            workflow_active=True,
            assignments=_Assignments(editors={"ed-1"}, reviewers={"rev-1"}, approvers={"app-1"}),
        )
        in_review = _State(
            owner_user_id="owner-1",
            status=DocumentStatus.IN_REVIEW,
            workflow_active=True,
            assignments=_Assignments(editors={"ed-1"}, reviewers={"rev-1"}, approvers={"app-1"}),
        )
        visible_in_progress = self.presenter.visible_actions_for_context(
            in_progress,
            user_id="ed-1",
            user_role=SystemRole.USER,
        )
        visible_in_review = self.presenter.visible_actions_for_context(
            in_review,
            user_id="ed-1",
            user_role=SystemRole.USER,
        )
        self.assertIn("edit", visible_in_progress)
        self.assertNotIn("edit", visible_in_review)


if __name__ == "__main__":
    unittest.main()
