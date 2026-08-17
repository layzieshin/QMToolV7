"""Selection surfaces transport errors; headers use HTTP pool reads."""

from __future__ import annotations



import unittest

from types import SimpleNamespace

from unittest.mock import MagicMock



from interfaces.pyqt.contributions.documents_workflow.selection_mixin import DocumentsWorkflowSelectionMixin

from modules.documents.contracts import ArtifactType, DocumentStatus, SystemRole





class _AvailablePool:

    def get_header(self, document_id: str):

        return None





class _BrokenComments:

    def sync_docx_comments(self, *args, **kwargs):

        raise RuntimeError("comments transport failed")



    def list_workflow_comments(self, *args, **kwargs):

        raise RuntimeError("comments transport failed")





class _Probe(DocumentsWorkflowSelectionMixin):

    def __init__(self) -> None:

        self._pool = _AvailablePool()

        self._comments_api = _BrokenComments()

        self._seen_event_ids: dict[str, object] = {}

        self._history_tab_index = 0

        self._tab_overview = MagicMock()

        self._tab_roles = MagicMock()

        self._tab_history = MagicMock()

        self._tab_comments = MagicMock()

        self._detail_tabs = MagicMock()

        self._history_notice = MagicMock()

        self._comments_context_label = MagicMock()

        self._add_comment_btn = MagicMock()

        self._title = MagicMock()

        self._description = MagicMock()

        self._profile = MagicMock()

        self._editors = MagicMock()

        self._reviewers = MagicMock()

        self._approvers = MagicMock()

        self._department = MagicMock()

        self._site = MagicMock()

        self._regulatory_scope = MagicMock()

        self._extension_valid_from = MagicMock()

        self._extension_valid_until = MagicMock()

        self._extension_next_review = MagicMock()

        self._extension_count = MagicMock()

        self._extension_remaining_days = MagicMock()

        self._fill_two_col_table = MagicMock()

        self._fill_history_table = MagicMock()

        self._update_comment_action_state = MagicMock()

        self._show_error = MagicMock()

        self._sig_ops = MagicMock()

        self._append = MagicMock()

        self._inline_notice = MagicMock()

        self._presenter = MagicMock()
        self._presenter.visible_actions_for_context.return_value = set()
        self._um = MagicMock()
        self._um.get_current_user.return_value = SimpleNamespace(user_id="u1")
        self._can_current_user_create_documents = MagicMock(return_value=False)

        assignments = SimpleNamespace(editors=set(), reviewers=set(), approvers=set())

        self._state = SimpleNamespace(

            document_id="DOC-1",

            version=1,

            title="T",

            description="",

            workflow_profile_id="long_release",

            status=DocumentStatus.PLANNED,

            last_event_id="e1",

            assignments=assignments,

            valid_from=None,

            valid_until=None,

            next_review_at=None,

            extension_count=0,

            created_by=None,

            owner_user_id="u1",

            created_at=None,

            workflow_active=False,

            doc_type=SimpleNamespace(value="OTHER"),

            control_class=SimpleNamespace(value="CONTROLLED"),

            review_completed_at=None,

            review_completed_by=None,

            released_at=None,

            approval_completed_at=None,

            approval_completed_by=None,

            archived_at=None,

            archived_by=None,

            last_event_at=None,

            last_actor_user_id=None,

        )

        self._current_state = self._state



    def _state_from_selection(self):

        return self._state



    def _format_dt(self, dt: object) -> str:

        return "-"



    def _current_user_role(self):

        return SimpleNamespace(user_id="u1"), SystemRole.USER



    def _set_details_open(self, open_state: bool) -> None:

        return None



    def _open_details_from_table(self) -> None:

        return None





class SelectionErrorSurfacingTest(unittest.TestCase):

    def test_refresh_details_reads_header_and_surfaces_comment_errors(self) -> None:

        probe = _Probe()

        probe._refresh_details()

        probe._fill_two_col_table.assert_called()

        probe._department.setText.assert_not_called()

        probe._show_error.assert_called_once()

        self.assertIsInstance(probe._show_error.call_args[0][0], RuntimeError)

        probe._tab_comments.setRowCount.assert_any_call(0)



    def test_open_readable_artifact_shows_error_on_transport_failure(self) -> None:

        probe = _Probe()

        probe._sig_ops.open_artifact.side_effect = RuntimeError("artifact open failed")

        probe._open_readable_artifact([ArtifactType.RELEASED_PDF])

        probe._show_error.assert_called_once()

        self.assertIsInstance(probe._show_error.call_args[0][0], RuntimeError)





if __name__ == "__main__":
    unittest.main()