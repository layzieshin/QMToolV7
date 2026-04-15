from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QComboBox


class CheckableMultiSelectCombo(QComboBox):
    """Compact multi-select combo based on checkable items."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setModel(QStandardItemModel(self))
        self.view().pressed.connect(self._toggle_item)

    def set_options(self, values: list[str]) -> None:
        model = self.model()
        model.clear()
        for value in sorted({v.strip() for v in values if v.strip()}):
            item = QStandardItem(value)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
            model.appendRow(item)
        self._refresh_caption()

    def set_selected_values(self, selected: set[str]) -> None:
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is None:
                continue
            checked = item.text() in selected
            item.setData(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked,
                Qt.ItemDataRole.CheckStateRole,
            )
        self._refresh_caption()

    def selected_values(self) -> set[str]:
        values: set[str] = set()
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                values.add(item.text())
        return values

    def _toggle_item(self, index) -> None:
        model = self.model()
        item = model.itemFromIndex(index)
        if item is None:
            return
        next_state = Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked
        item.setCheckState(next_state)
        self._refresh_caption()

    def _refresh_caption(self) -> None:
        selected = sorted(self.selected_values())
        label = ", ".join(selected) if selected else "-"
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setText(label)

