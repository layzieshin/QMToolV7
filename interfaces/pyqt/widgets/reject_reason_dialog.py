from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout

from modules.documents.contracts import RejectionReason


class RejectReasonDialog(QDialog):
    """Reusable rejection reason dialog with template + free text."""

    def __init__(self, title: str, template_label: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._template = QLineEdit()
        self._free_text = QLineEdit()
        form = QFormLayout()
        form.addRow(template_label, self._template)
        form.addRow("Optionaler Freitext", self._free_text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def reason(self) -> RejectionReason:
        return RejectionReason(
            template_text=self._template.text().strip() or None,
            free_text=self._free_text.text().strip() or None,
        )
