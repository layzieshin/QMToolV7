from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem, QVBoxLayout


class QuizBindingDialog(QDialog):
    def __init__(self, pending: list[object], parent=None) -> None:
        super().__init__(parent)
        self._pending = list(pending)
        self.setWindowTitle("Quiz zuordnen")
        self.resize(860, 420)
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Dokument-Code", "Version", "Titel", "Fragen", "Importiert am", "Import-ID"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemDoubleClicked.connect(lambda _item: self.accept())
        self._table.setRowCount(len(self._pending))
        for idx, row in enumerate(self._pending):
            self._table.setItem(idx, 0, QTableWidgetItem(str(getattr(row, "document_id", ""))))
            self._table.setItem(idx, 1, QTableWidgetItem(str(getattr(row, "document_version", ""))))
            self._table.setItem(idx, 2, QTableWidgetItem(str(getattr(row, "document_title", "") or "-")))
            self._table.setItem(idx, 3, QTableWidgetItem(str(getattr(row, "question_count", 0))))
            self._table.setItem(idx, 4, QTableWidgetItem(str(getattr(row, "created_at", ""))))
            import_id = str(getattr(row, "import_id", ""))
            shown = f"{import_id[:8]}..." if len(import_id) > 8 else import_id
            item = QTableWidgetItem(shown)
            item.setToolTip(import_id)
            self._table.setItem(idx, 5, item)
        self._table.resizeColumnsToContents()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addWidget(buttons)
        if self._table.rowCount() > 0:
            self._table.selectRow(0)
            self._table.setFocus(Qt.FocusReason.OtherFocusReason)

    def selected(self) -> object | None:
        row = self._table.currentRow()
        if 0 <= row < len(self._pending):
            return self._pending[row]
        return None

