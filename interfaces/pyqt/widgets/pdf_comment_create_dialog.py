from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QTextEdit


class PdfCommentCreateDialog(QDialog):
    def __init__(self, *, max_page: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kommentar erstellen")
        layout = QFormLayout(self)
        self.page = QSpinBox(self)
        self.page.setRange(1, max(1, max_page))
        self.text = QTextEdit(self)
        layout.addRow("Seite", self.page)
        layout.addRow("Kommentar", self.text)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addRow(box)
