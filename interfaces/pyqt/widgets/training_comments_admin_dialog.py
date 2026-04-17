from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class TrainingCommentsAdminDialog(QDialog):
    def __init__(self, admin_api, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kommentarübersicht (QMB/Admin)")
        self.setMinimumSize(700, 400)
        self._admin = admin_api

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Dokumentenkennung", "Titel", "Benutzer", "Datum", "Kommentartext", "Status"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, stretch=1)

        row = QHBoxLayout()
        btn_refresh = QPushButton("Aktualisieren")
        btn_refresh.clicked.connect(self._load)
        btn_resolve = QPushButton("Als erledigt markieren")
        btn_resolve.clicked.connect(self._resolve)
        btn_inactive = QPushButton("Inaktiv setzen")
        btn_inactive.clicked.connect(self._inactivate)
        for btn in (btn_refresh, btn_resolve, btn_inactive):
            row.addWidget(btn)
        row.addStretch(1)
        layout.addLayout(row)

        self._comments: list = []
        self._load()

    def _load(self) -> None:
        try:
            self._comments = self._admin.list_active_comments()
            self._table.setRowCount(len(self._comments))
            for i, c in enumerate(self._comments):
                self._table.setItem(i, 0, QTableWidgetItem(c.document_id))
                self._table.setItem(i, 1, QTableWidgetItem(c.document_title_snapshot))
                self._table.setItem(i, 2, QTableWidgetItem(c.username_snapshot))
                self._table.setItem(i, 3, QTableWidgetItem(str(c.created_at)))
                self._table.setItem(i, 4, QTableWidgetItem(c.comment_text))
                self._table.setItem(i, 5, QTableWidgetItem(c.status.value))
            self._table.resizeColumnsToContents()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Kommentare", str(exc))

    def _selected_comment(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._comments):
            return self._comments[row]
        return None

    def _resolve(self) -> None:
        c = self._selected_comment()
        if c is None:
            return
        try:
            note, ok = QInputDialog.getText(self, "Erledigt", "Notiz (optional):")
            if not ok:
                return
            self._admin.resolve_comment(c.comment_id, "admin", note or None)
            self._load()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Kommentare", str(exc))

    def _inactivate(self) -> None:
        c = self._selected_comment()
        if c is None:
            return
        try:
            note, ok = QInputDialog.getText(self, "Inaktiv setzen", "Notiz (optional):")
            if not ok:
                return
            self._admin.inactivate_comment(c.comment_id, "admin", note or None)
            self._load()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Kommentare", str(exc))
