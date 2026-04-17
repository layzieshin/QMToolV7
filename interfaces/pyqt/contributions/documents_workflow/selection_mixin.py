"""Selection, details, comments (documents workflow)."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import QTableWidgetItem

from interfaces.pyqt.contributions.common import user_to_system_role
from interfaces.pyqt.logging_adapter import get_logger
from interfaces.pyqt.presenters.documents_detail_presenter import DocumentsDetailPresenter
from interfaces.pyqt.sections.action_bar import update_action_visibility
from interfaces.pyqt.widgets.comment_detail_dialog import CommentDetailDialog
from interfaces.pyqt.widgets.pdf_viewer_dialog import PdfViewerDialog, PdfViewerRequest
from modules.documents.contracts import ArtifactType, DocumentStatus, SystemRole, WorkflowCommentStatus


class DocumentsWorkflowSelectionMixin:
    def _on_table_selected(self) -> None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            self._current_state = None
            self._set_details_open(False)
            self._detail_tabs.setCurrentIndex(0)
            self._update_action_visibility()
            return
        self._current_state = self._model._rows[selected[0].row()]
        state = self._state_from_selection()
        self._doc_id.setText(state.document_id)
        self._version.setText(str(state.version))
        self._refresh_details()
        self._update_action_visibility()

    def _update_action_visibility(self) -> None:
        user = self._um.get_current_user()
        user_id = str(user.user_id) if user is not None else None
        user_role = user_to_system_role(user) if user is not None else None
        visible_for = self._presenter.visible_actions_for_context(
            self._current_state,
            user_id=user_id,
            user_role=user_role,
            can_create_new_documents=self._can_current_user_create_documents(),
        )
        update_action_visibility(
            self._workflow_actions["buttons"],
            self._top_actions["buttons"],
            visible_for,
            self._is_profile_manager_allowed(),
        )
        self._apply_editor_permissions()

    def _can_current_user_create_documents(self) -> bool:
        user = self._um.get_current_user()
        if user is None:
            return False
        try:
            role = user_to_system_role(user)
        except Exception as exc:  # noqa: BLE001
            self._log.exception("Cannot resolve current user role")
            return False
        if role == SystemRole.QMB:
            return True
        if not self._container.has_port("settings_service"):
            return False
        docs_settings = self._container.get_port("settings_service").get_module_settings("documents")
        mapping = docs_settings.get("can_create_new_documents", {})
        if not isinstance(mapping, dict):
            return False
        return bool(mapping.get(str(user.user_id), False))

    def _open_details_from_table(self) -> None:
        if self._current_state is None:
            return
        self._set_details_open(True)
        self._inline_notice.setText("Details geöffnet.")

    def _run_default_table_action(self) -> None:
        if self._current_state is None:
            return
        status = self._current_state.status
        priorities = self._presenter.default_artifact_priority(status)
        if priorities:
            self._open_readable_artifact(priorities)
        else:
            self._open_details_from_table()

    def _open_readable_artifact(self, preferred_types: list[ArtifactType]) -> None:
        state = self._state_from_selection()
        for artifact_type in preferred_types:
            if self._sig_ops.open_artifact(state, artifact_type):
                self._append("ARTEFAKT_GEOEFFNET", {"type": artifact_type.value})
                self._inline_notice.setText(f"Standardaktion ausgeführt: {artifact_type.value} geöffnet.")
                return
        self._open_details_from_table()
        self._inline_notice.setText("Keine lesbare Datei gefunden. Details wurden geöffnet.")

    def _refresh_details(self) -> None:
        if self._current_state is None:
            return
        state = self._state_from_selection()
        header = self._pool.get_header(state.document_id)
        dp = DocumentsDetailPresenter
        self._fill_two_col_table(self._tab_overview, dp.overview_rows(state, header))
        self._fill_two_col_table(self._tab_roles, dp.roles_rows(state))
        history_rows = dp.history_rows(state)
        self._fill_history_table(history_rows)
        state_key = f"{state.document_id}:{state.version}"
        old_event = self._seen_event_ids.get(state_key)
        new_event = state.last_event_id
        if old_event is not None and old_event != new_event:
            self._detail_tabs.setTabText(self._history_tab_index, "Verlauf *")
            self._history_notice.setText("Neuer Statuswechsel erkannt - Verlauf prüfen.")
        else:
            self._detail_tabs.setTabText(self._history_tab_index, "Verlauf")
            self._history_notice.setText("Verlauf ohne neue Änderungen.")
        self._seen_event_ids[state_key] = new_event
        self._title.setText(state.title or "")
        self._description.setText(state.description or "")
        self._profile.setText(state.workflow_profile_id or "")
        self._editors.setText(", ".join(sorted(state.assignments.editors)))
        self._reviewers.setText(", ".join(sorted(state.assignments.reviewers)))
        self._approvers.setText(", ".join(sorted(state.assignments.approvers)))
        if header is not None:
            self._department.setText(header.department or "")
            self._site.setText(header.site or "")
            self._regulatory_scope.setText(header.regulatory_scope or "")
        self._refresh_workflow_comments(state)
        self._extension_valid_from.setText(self._format_dt(state.valid_from))
        self._extension_valid_until.setText(self._format_dt(state.valid_until))
        self._extension_next_review.setText(self._format_dt(state.next_review_at))
        self._extension_count.setText(f"{state.extension_count}/3")
        if state.valid_until is not None:
            local_valid_until = DocumentsDetailPresenter._to_local(state.valid_until)
            if local_valid_until is None:
                self._extension_remaining_days.setText("-")
            else:
                now = datetime.now(local_valid_until.tzinfo)
                remaining_days = max((local_valid_until - now).days, 0)
                self._extension_remaining_days.setText(str(remaining_days))
        else:
            self._extension_remaining_days.setText("-")

    def _resolve_comment_context(self, state) -> object | None:
        if state.status in {DocumentStatus.PLANNED, DocumentStatus.IN_PROGRESS}:
            from modules.documents.contracts import WorkflowCommentContext

            return WorkflowCommentContext.DOCX_EDIT
        if state.status == DocumentStatus.IN_REVIEW:
            from modules.documents.contracts import WorkflowCommentContext

            return WorkflowCommentContext.PDF_REVIEW
        if state.status == DocumentStatus.IN_APPROVAL:
            from modules.documents.contracts import WorkflowCommentContext

            return WorkflowCommentContext.PDF_APPROVAL
        return None

    def _refresh_workflow_comments(self, state) -> None:
        self._tab_comments.setRowCount(0)
        context = self._resolve_comment_context(state)
        self._comments_context_label.setText(f"Kontext: {getattr(context, 'value', '-')}")
        self._add_comment_btn.setEnabled(context is not None and getattr(context, "value", "").startswith("PDF_"))
        if context is None or self._comments_api is None:
            return
        user, role = self._current_user_role()
        if getattr(context, "value", "") == "DOCX_EDIT":
            self._comments_api.sync_docx_comments(
                state,
                actor_user_id=user.user_id,
                actor_role=role,
            )
        rows = self._comments_api.list_workflow_comments(
            state,
            context=context,
            actor_user_id=user.user_id,
            actor_role=role,
        )
        self._tab_comments.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self._tab_comments.setItem(i, 0, QTableWidgetItem(row.ref_no))
            self._tab_comments.setItem(i, 1, QTableWidgetItem(row.status.value))
            self._tab_comments.setItem(i, 2, QTableWidgetItem(str(row.page_number or "")))
            self._tab_comments.setItem(i, 3, QTableWidgetItem(row.author_display or ""))
            self._tab_comments.setItem(i, 4, QTableWidgetItem(self._format_dt(row.created_at)))
            self._tab_comments.setItem(i, 5, QTableWidgetItem(row.preview_text))
            self._tab_comments.item(i, 0).setData(0x0100, row.comment_id)
            self._tab_comments.item(i, 1).setData(0x0101, row.status.value)
        self._update_comment_action_state()

    def _open_comment_detail(self, item) -> None:
        comment_id = item.data(0x0100) if item is not None else None
        if not comment_id or self._comments_api is None:
            return
        user, role = self._current_user_role()
        detail = self._comments_api.get_workflow_comment_detail(comment_id, actor_user_id=user.user_id, actor_role=role)
        dlg = CommentDetailDialog(title=detail.ref_no, content=detail.full_text, parent=self)
        dlg.exec()

    def _selected_comment_id(self) -> str | None:
        row_idx = self._tab_comments.currentRow()
        if row_idx < 0:
            return None
        item = self._tab_comments.item(row_idx, 0)
        if item is None:
            return None
        value = item.data(0x0100)
        return str(value) if value else None

    def _update_comment_action_state(self) -> None:
        row_idx = self._tab_comments.currentRow()
        if row_idx < 0:
            self._resolve_comment_btn.setEnabled(False)
            self._activate_comment_btn.setEnabled(False)
            return
        status_item = self._tab_comments.item(row_idx, 1)
        current_status = str(status_item.data(0x0101) if status_item is not None else "")
        self._resolve_comment_btn.setEnabled(current_status != WorkflowCommentStatus.RESOLVED.value)
        self._activate_comment_btn.setEnabled(current_status != WorkflowCommentStatus.ACTIVE.value)

    def _resolve_selected_comment(self) -> None:
        comment_id = self._selected_comment_id()
        if not comment_id or self._comments_api is None:
            return
        try:
            user, role = self._current_user_role()
            self._comments_api.set_workflow_comment_status(
                comment_id,
                new_status=WorkflowCommentStatus.RESOLVED,
                actor_user_id=user.user_id,
                actor_role=role,
                note="resolved in workflow details",
            )
            state = self._state_from_selection()
            self._refresh_workflow_comments(state)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _activate_selected_comment(self) -> None:
        comment_id = self._selected_comment_id()
        if not comment_id or self._comments_api is None:
            return
        try:
            user, role = self._current_user_role()
            self._comments_api.set_workflow_comment_status(
                comment_id,
                new_status=WorkflowCommentStatus.ACTIVE,
                actor_user_id=user.user_id,
                actor_role=role,
                note="re-activated in workflow details",
            )
            state = self._state_from_selection()
            self._refresh_workflow_comments(state)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _open_comment_viewer(self) -> None:
        state = self._state_from_selection()
        context = self._resolve_comment_context(state)
        path = self._sig_ops.resolve_openable_path_from_state(state)
        if path is None:
            return
        user, _role = self._current_user_role()
        mode = "WORKFLOW_REVIEW"
        if getattr(context, "value", "") == "PDF_APPROVAL":
            mode = "WORKFLOW_APPROVAL"
        dlg = PdfViewerDialog(
            request=PdfViewerRequest(
                document_id=state.document_id,
                version=state.version,
                artifact_path=path,
                artifact_id=None,
                actor_user_id=user.user_id,
                actor_role=_role.value,
                mode=mode,
                enable_comments=True,
                enable_read_tracking=False,
                enable_comment_creation=True,
                workflow_state=state,
            ),
            documents_comments_api=self._comments_api,
            parent=self,
        )
        dlg.exec()
        # Viewer may have created comments; refresh detail tab immediately.
        try:
            self._refresh_workflow_comments(state)
        except Exception:  # noqa: BLE001
            self._log.exception("Refreshing workflow comments after viewer failed")

