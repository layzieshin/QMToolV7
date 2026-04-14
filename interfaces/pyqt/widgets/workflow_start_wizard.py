from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout


@dataclass
class WorkflowStartPayload:
    profile_id: str
    require_four_eyes: bool
    editors_csv: str
    reviewers_csv: str
    approvers_csv: str


class WorkflowStartWizard(QDialog):
    """Wizard-style workflow start input collector."""

    def __init__(self, current_profile: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workflow starten")
        self._profile = QComboBox()
        self._profile.addItem("long_release")
        if current_profile and self._profile.findText(current_profile) < 0:
            self._profile.addItem(current_profile)
        self._profile.setCurrentText(current_profile or "long_release")
        self._four_eyes = QCheckBox("4-Augen-Prinzip aktiv")
        self._editors = QLineEdit()
        self._reviewers = QLineEdit()
        self._approvers = QLineEdit()
        form = QFormLayout()
        form.addRow("Workflowprofil", self._profile)
        form.addRow("", self._four_eyes)
        form.addRow("Editoren (CSV)", self._editors)
        form.addRow("Prüfer (CSV)", self._reviewers)
        form.addRow("Freigeber (CSV)", self._approvers)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def payload(self) -> WorkflowStartPayload:
        return WorkflowStartPayload(
            profile_id=self._profile.currentText().strip() or "long_release",
            require_four_eyes=self._four_eyes.isChecked(),
            editors_csv=self._editors.text().strip(),
            reviewers_csv=self._reviewers.text().strip(),
            approvers_csv=self._approvers.text().strip(),
        )
