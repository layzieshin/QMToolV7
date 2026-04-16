"""
WorkflowTableModel — extracted from documents_workflow_view.py (Phase 3A).

A read-only QAbstractTableModel that backs the document workflow table.
"""
from __future__ import annotations

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class WorkflowTableModel(QAbstractTableModel):
    _HEADERS = ["Dokumentenkennung", "Titel", "Status", "Workflow aktiv", "Aktive Version"]

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[object] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, rows: list[object]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_object(self, row: int) -> object | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return len(self._HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> object:  # noqa: N802
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._HEADERS):
                return self._HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row_obj = self._rows[index.row()]
        col = index.column()
        try:
            if col == 0:
                return str(getattr(row_obj, "document_id", ""))
            if col == 1:
                return str(getattr(row_obj, "title", ""))
            if col == 2:
                return str(getattr(row_obj, "status", ""))
            if col == 3:
                return "Ja" if getattr(row_obj, "workflow_active", False) else "Nein"
            if col == 4:
                return str(getattr(row_obj, "active_version", ""))
        except Exception:
            return ""
        return None

