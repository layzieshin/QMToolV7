from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class TagEditorWidget(QWidget):
    def __init__(self, *, selected_tags: list[str], suggestions: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected: list[str] = sorted({tag.strip() for tag in selected_tags if tag.strip()})
        self._suggestions: list[str] = sorted({tag.strip() for tag in suggestions if tag.strip()})

        self._input = QLineEdit()
        self._input.setPlaceholderText("Tag eingeben (Einzelwort)")
        self._add_btn = QPushButton("Hinzufuegen")
        self._add_btn.clicked.connect(self._on_add_clicked)

        self._selected_list = QListWidget()
        self._selected_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._selected_list.setAlternatingRowColors(True)

        self._suggestion_list = QListWidget()
        self._suggestion_list.itemClicked.connect(self._on_suggestion_clicked)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input, stretch=1)
        input_row.addWidget(self._add_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(input_row)
        layout.addWidget(QLabel("Aktive Tags"))
        layout.addWidget(self._selected_list)
        layout.addWidget(QLabel("Verfuegbare Tags (klicken zum Hinzufuegen)"))
        layout.addWidget(self._suggestion_list)
        self._refresh_selected_view()
        self._refresh_suggestion_view()

    def selected_tags(self) -> list[str]:
        return list(self._selected)

    def _on_add_clicked(self) -> None:
        raw = self._input.text().strip()
        if not raw:
            return
        if raw not in self._selected:
            self._selected.append(raw)
            self._selected.sort()
        if raw not in self._suggestions:
            self._suggestions.append(raw)
            self._suggestions.sort()
        self._input.clear()
        self._refresh_selected_view()
        self._refresh_suggestion_view()

    def _on_suggestion_clicked(self, item: QListWidgetItem) -> None:
        tag = item.text().strip()
        if not tag:
            return
        if tag not in self._selected:
            self._selected.append(tag)
            self._selected.sort()
        self._refresh_selected_view()

    def _remove_selected_tag(self, tag: str) -> None:
        self._selected = [value for value in self._selected if value != tag]
        self._refresh_selected_view()

    def _refresh_selected_view(self) -> None:
        self._selected_list.clear()
        for tag in self._selected:
            item = QListWidgetItem()
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 2, 4, 2)
            row_layout.setSpacing(6)
            label = QLabel(tag)
            remove_btn = QToolButton()
            remove_btn.setText("✕")
            remove_btn.setToolTip("Tag entfernen")
            remove_btn.clicked.connect(lambda _checked=False, value=tag: self._remove_selected_tag(value))
            row_layout.addWidget(label, stretch=1)
            row_layout.addWidget(remove_btn, alignment=Qt.AlignmentFlag.AlignRight)
            self._selected_list.addItem(item)
            self._selected_list.setItemWidget(item, row_widget)
            item.setSizeHint(row_widget.sizeHint())

    def _refresh_suggestion_view(self) -> None:
        self._suggestion_list.clear()
        for tag in self._suggestions:
            self._suggestion_list.addItem(tag)
