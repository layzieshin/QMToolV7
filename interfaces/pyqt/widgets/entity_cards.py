from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QToolButton, QVBoxLayout, QWidget


class EntityCard(QWidget):
    """Clickable dashboard card with count and list."""

    def __init__(self, title: str, on_open: Callable[[], None]) -> None:
        super().__init__()
        self._count = QLabel("0")
        self._count.setObjectName("heroTitle")
        self._list = QListWidget()
        header = QToolButton()
        header.setText(title)
        header.clicked.connect(on_open)
        self._list.itemDoubleClicked.connect(lambda _item: on_open())
        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(self._count)
        layout.addWidget(self._list, stretch=1)

    def set_items(self, count: int, items: list[str]) -> None:
        self._count.setText(str(count))
        self._list.clear()
        for item in items:
            self._list.addItem(QListWidgetItem(item))
