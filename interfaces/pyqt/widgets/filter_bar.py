from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QWidget


class FilterBar(QWidget):
    """Common filter row with search/status/scope/density."""

    def __init__(self) -> None:
        super().__init__()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suche")
        self.status = QComboBox()
        self.scope = QComboBox()
        self.density = QComboBox()
        self.density.addItem("Kompakt", "compact")
        self.density.addItem("Komfortabel", "comfortable")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        form.addRow("Suche", self.search)
        form.addRow("Status", self.status)
        form.addRow("Scope", self.scope)
        form.addRow("Dichte", self.density)
        outer.addLayout(form)
