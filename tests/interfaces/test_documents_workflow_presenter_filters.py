from __future__ import annotations

import unittest
from dataclasses import dataclass

from interfaces.pyqt.presenters.documents_workflow_filter_presenter import DocumentsWorkflowFilterPresenter
from modules.documents.contracts import DocumentStatus


@dataclass
class _Row:
    document_id: str
    version: int
    owner_user_id: str | None
    title: str
    status: DocumentStatus
    workflow_active: bool


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


if __name__ == "__main__":
    unittest.main()
