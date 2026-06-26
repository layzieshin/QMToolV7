from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class TrainingInboxSection(QWidget):
    def __init__(
        self,
        *,
        training_api: object,
        presenter: object,
        current_user_provider: Callable[[], object | None],
        append_status_log: Callable[[str], None],
        show_error: Callable[[Exception], None],
        set_output_text: Callable[[str], None],
        clear_output: Callable[[], None],
        update_action_state: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._api = training_api
        self._presenter = presenter
        self._current_user_provider = current_user_provider
        self._append_status_log = append_status_log
        self._show_error = show_error
        self._set_output_text = set_output_text
        self._clear_output = clear_output
        self._update_action_state = update_action_state
        self._inbox_items: list = []
        self._selected_item = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            [
                "Dokumentenkennung",
                "Titel",
                "Status",
                "Owner",
                "Freigabe am",
                "Lesestatus",
                "Quizstatus",
            ]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table)

    def current_item(self):
        return self._selected_item

    def row_count(self) -> int:
        return self._table.rowCount()

    def load_inbox(self) -> None:
        user = self._current_user_provider()
        if user is None:
            self._inbox_items = []
            self._render_table()
            self._set_output_text("Anmeldung erforderlich.")
            return
        try:
            raw = self._api.list_training_inbox_for_user(user.user_id, open_only=False)
            self._inbox_items = self._presenter.filter_rows(raw, open_only=False)
            self._render_table()
            self._clear_output()
            self._append_status_log(self._presenter.status_line(rows=len(self._inbox_items), open_only=False))
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_selection_changed(self) -> None:
        row = self._table.currentRow()
        if 0 <= row < len(self._inbox_items):
            self._selected_item = self._inbox_items[row]
        else:
            self._selected_item = None
        self._update_action_state()

    def _render_table(self) -> None:
        self._table.setRowCount(len(self._inbox_items))
        for i, item in enumerate(self._inbox_items):
            self._table.setItem(i, 0, QTableWidgetItem(item.document_id))
            self._table.setItem(i, 1, QTableWidgetItem(item.title))
            self._table.setItem(i, 2, QTableWidgetItem(item.status))
            self._table.setItem(i, 3, QTableWidgetItem(item.owner_user_id or ""))
            self._table.setItem(i, 4, QTableWidgetItem(str(item.released_at or "")))
            read_text = "✓ gelesen" if item.read_confirmed else "offen"
            self._table.setItem(i, 5, QTableWidgetItem(read_text))
            quiz_text = "✓ bestanden" if item.quiz_passed else ("verfuegbar" if item.quiz_available else "-")
            self._table.setItem(i, 6, QTableWidgetItem(quiz_text))
        self._table.resizeColumnsToContents()
        self._selected_item = None
        self._update_action_state()
