from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextEdit, QVBoxLayout


class CommentDetailDialog(QDialog):
    def __init__(self, *, title: str, content: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Kommentar"))
        txt = QTextEdit(self)
        txt.setReadOnly(True)
        txt.setPlainText(content)
        layout.addWidget(txt)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        box.accepted.connect(self.accept)
        layout.addWidget(box)
