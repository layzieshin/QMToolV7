from __future__ import annotations

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class SimpleRowsTableModel(QAbstractTableModel):
    """Reusable read-only table model for tuple rows."""

    def __init__(self, headers: list[str]) -> None:
        super().__init__()
        self._headers = headers
        self._rows: list[tuple[object, ...]] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self._headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return str(section + 1)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        return str(self._rows[index.row()][index.column()])

    def load(self, rows: list[tuple[object, ...]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self) -> list[tuple[object, ...]]:
        return self._rows
