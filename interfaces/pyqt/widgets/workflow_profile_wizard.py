from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout

from modules.documents.api import ControlClass, DocumentStatus, DocumentType


@dataclass
class WorkflowProfileWizardPayload:
    operation: str
    profile_id: str
    label: str
    control_class: ControlClass
    doc_type: DocumentType
    phases: tuple[DocumentStatus, ...]
    signature_required_transitions: tuple[str, ...]
    four_eyes_required: bool
    requires_editors: bool
    requires_reviewers: bool
    requires_approvers: bool
    change_reason: str

    def as_json_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "label": self.label,
            "control_class": self.control_class.value,
            "phases": [phase.value for phase in self.phases],
            "four_eyes_required": self.four_eyes_required,
            "signature_required_transitions": list(self.signature_required_transitions),
            "requires_editors": self.requires_editors,
            "requires_reviewers": self.requires_reviewers,
            "requires_approvers": self.requires_approvers,
            "allows_content_changes": True,
            "release_evidence_mode": "WORKFLOW",
        }


class WorkflowProfileWizardDialog(QDialog):
    """Guided profile editor for existing workflow/profile model."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workflowprofil-Assistent")

        self._profile_id = QLineEdit()
        self._label = QLineEdit()
        self._operation = QComboBox()
        self._operation.addItem("Definition anlegen", "create")
        self._operation.addItem("Neue Version anlegen", "create_version")
        self._operation.addItem("Aktivieren", "activate")
        self._operation.addItem("Deaktivieren", "deactivate")
        self._operation.addItem("Dokumenttyp binden", "bind")
        self._change_reason = QLineEdit("PyQt workflow profile manager")
        self._control_class = QComboBox()
        for control_class in ControlClass:
            self._control_class.addItem(control_class.value, control_class)
        self._doc_type = QComboBox()
        for doc_type in DocumentType:
            self._doc_type.addItem(doc_type.value, doc_type)

        self._phase_review = QCheckBox("Phase Pruefung (IN_REVIEW)")
        self._phase_review.setChecked(True)
        self._phase_approval = QCheckBox("Phase Freigabe (IN_APPROVAL)")
        self._phase_approval.setChecked(True)

        self._sign_edit_to_review = QCheckBox("Signatur bei Bearbeitung -> Pruefung")
        self._sign_edit_to_review.setChecked(True)
        self._sign_approval_to_release = QCheckBox("Signatur bei Freigabe -> Freigegeben")
        self._sign_approval_to_release.setChecked(True)

        self._four_eyes = QCheckBox("Vier-Augen-Prinzip aktiv")
        self._four_eyes.setChecked(True)

        self._requires_editors = QCheckBox("Editoren erforderlich")
        self._requires_editors.setChecked(True)
        self._requires_reviewers = QCheckBox("Pruefer erforderlich")
        self._requires_reviewers.setChecked(True)
        self._requires_approvers = QCheckBox("Freigeber erforderlich")
        self._requires_approvers.setChecked(True)

        self._phase_review.toggled.connect(self._sync_phase_requirements)
        self._phase_approval.toggled.connect(self._sync_phase_requirements)
        self._sync_phase_requirements()

        form = QFormLayout()
        form.addRow("Aktion", self._operation)
        form.addRow("Profil-ID", self._profile_id)
        form.addRow("Bezeichnung", self._label)
        form.addRow("Änderungsgrund", self._change_reason)
        form.addRow("Kontrollklasse", self._control_class)
        form.addRow("Dokumenttyp", self._doc_type)
        form.addRow("", self._phase_review)
        form.addRow("", self._phase_approval)
        form.addRow("", self._sign_edit_to_review)
        form.addRow("", self._sign_approval_to_release)
        form.addRow("", self._four_eyes)
        form.addRow("", self._requires_editors)
        form.addRow("", self._requires_reviewers)
        form.addRow("", self._requires_approvers)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _sync_phase_requirements(self) -> None:
        review_enabled = self._phase_review.isChecked()
        approval_enabled = self._phase_approval.isChecked()

        self._sign_edit_to_review.setEnabled(review_enabled)
        self._requires_reviewers.setEnabled(review_enabled)
        if not review_enabled:
            self._sign_edit_to_review.setChecked(False)
            self._requires_reviewers.setChecked(False)

        self._sign_approval_to_release.setEnabled(approval_enabled)
        self._requires_approvers.setEnabled(approval_enabled)
        if not approval_enabled:
            self._sign_approval_to_release.setChecked(False)
            self._requires_approvers.setChecked(False)

    def payload(self) -> WorkflowProfileWizardPayload:
        phases = [DocumentStatus.IN_PROGRESS]
        if self._phase_review.isChecked():
            phases.append(DocumentStatus.IN_REVIEW)
        if self._phase_approval.isChecked():
            phases.append(DocumentStatus.IN_APPROVAL)
        phases.append(DocumentStatus.APPROVED)

        transitions: list[str] = []
        if self._sign_edit_to_review.isChecked() and self._phase_review.isChecked():
            transitions.append("IN_PROGRESS->IN_REVIEW")
        if self._sign_approval_to_release.isChecked() and self._phase_approval.isChecked():
            transitions.append("IN_APPROVAL->APPROVED")

        return WorkflowProfileWizardPayload(
            operation=str(self._operation.currentData()),
            profile_id=self._profile_id.text().strip(),
            label=self._label.text().strip() or self._profile_id.text().strip(),
            control_class=self._control_class.currentData(),
            doc_type=self._doc_type.currentData(),
            phases=tuple(phases),
            signature_required_transitions=tuple(transitions),
            four_eyes_required=self._four_eyes.isChecked(),
            requires_editors=self._requires_editors.isChecked(),
            requires_reviewers=self._requires_reviewers.isChecked(),
            requires_approvers=self._requires_approvers.isChecked(),
            change_reason=self._change_reason.text().strip() or "PyQt workflow profile manager",
        )

