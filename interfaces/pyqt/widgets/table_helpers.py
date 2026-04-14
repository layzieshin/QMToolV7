from __future__ import annotations

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem


def configure_readonly_table(table: QTableWidget, headers: list[str]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)


def fill_table(table: QTableWidget, rows: list[tuple[str, ...]]) -> None:
    table.setRowCount(len(rows))
    for row_idx, row in enumerate(rows):
        for col_idx, value in enumerate(row):
            table.setItem(row_idx, col_idx, QTableWidgetItem(value))
    table.resizeColumnsToContents()
