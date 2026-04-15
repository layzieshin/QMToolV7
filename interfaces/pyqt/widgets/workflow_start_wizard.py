from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout

from interfaces.pyqt.widgets.checkable_multiselect_combo import CheckableMultiSelectCombo


@dataclass
class WorkflowStartPayload:
    profile_id: str
    require_four_eyes: bool
    editors: set[str]
    reviewers: set[str]
    approvers: set[str]


class WorkflowStartWizard(QDialog):
    """Wizard-style workflow start input collector."""

    def __init__(
        self,
        current_profile: str,
        *,
        profile_ids: list[str] | None = None,
        available_user_ids: list[str],
        current_editors: set[str] | None = None,
        current_reviewers: set[str] | None = None,
        current_approvers: set[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workflow starten")
        self._profile = QComboBox()
        for profile_id in (profile_ids or ["long_release"]):
            if profile_id and self._profile.findText(profile_id) < 0:
                self._profile.addItem(profile_id)
        if self._profile.count() == 0:
            self._profile.addItem("long_release")
        if current_profile and self._profile.findText(current_profile) < 0:
            self._profile.addItem(current_profile)
        self._profile.setCurrentText(current_profile or "long_release")
        self._four_eyes = QCheckBox("4-Augen-Prinzip aktiv")
        self._editors = CheckableMultiSelectCombo()
        self._reviewers = CheckableMultiSelectCombo()
        self._approvers = CheckableMultiSelectCombo()
        self._editors.set_options(available_user_ids)
        self._reviewers.set_options(available_user_ids)
        self._approvers.set_options(available_user_ids)
        self._editors.set_selected_values(current_editors or set())
        self._reviewers.set_selected_values(current_reviewers or set())
        self._approvers.set_selected_values(current_approvers or set())
        form = QFormLayout()
        form.addRow("Workflowprofil", self._profile)
        form.addRow("", self._four_eyes)
        form.addRow("Editoren", self._editors)
        form.addRow("Pruefer", self._reviewers)
        form.addRow("Freigeber", self._approvers)
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
            editors=self._editors.selected_values(),
            reviewers=self._reviewers.selected_values(),
            approvers=self._approvers.selected_values(),
        )
