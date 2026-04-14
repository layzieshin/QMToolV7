from __future__ import annotations

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class CopyFieldRow(QWidget):
    """Readonly line edit with copy button."""

    def __init__(self) -> None:
        super().__init__()
        self.field = QLineEdit()
        self.field.setReadOnly(True)
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(self._copy_value)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.field, stretch=1)
        layout.addWidget(copy_btn)

    def set_value(self, value: str) -> None:
        self.field.setText(value)

    def _copy_value(self) -> None:
        QGuiApplication.clipboard().setText(self.field.text())
