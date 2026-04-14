from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLineEdit, QVBoxLayout

from modules.documents.contracts import DocumentType


@dataclass
class DocumentCreatePayload:
    mode: str
    source_path: str
    document_id: str
    title: str
    description: str
    owner_user_id: str
    doc_type: DocumentType
    workflow_profile_id: str


class DocumentCreateWizard(QDialog):
    """Wizard-like dialog for new/import document creation."""

    def __init__(self, owner_ids: list[str], current_owner: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neues Dokument / Import")
        self._mode = QComboBox()
        self._mode.addItem("Aus Vorlage erstellen", "template")
        self._mode.addItem("Bestehendes Word-Dokument importieren", "docx")
        self._source = QLineEdit()
        self._document_id = QLineEdit()
        self._title = QLineEdit()
        self._description = QLineEdit()
        self._owner = QComboBox()
        self._owner.addItems(owner_ids)
        idx = self._owner.findText(current_owner)
        if idx >= 0:
            self._owner.setCurrentIndex(idx)
        self._doc_type = QComboBox()
        for dt in DocumentType:
            self._doc_type.addItem(dt.value, dt)
        self._workflow_profile = QLineEdit("long_release")
        self._draft_only = QCheckBox("Nur Entwurf anlegen")

        pick = QDialogButtonBox(QDialogButtonBox.StandardButton.Open)
        pick.accepted.connect(self._pick_file)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow("Startart", self._mode)
        form.addRow("Datei", self._source)
        form.addRow("", pick)
        form.addRow("Dokument-ID", self._document_id)
        form.addRow("Titel", self._title)
        form.addRow("Kurzbeschreibung", self._description)
        form.addRow("Owner", self._owner)
        form.addRow("Dokumenttyp", self._doc_type)
        form.addRow("Workflowprofil", self._workflow_profile)
        form.addRow("", self._draft_only)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _pick_file(self) -> None:
        mode = self._mode.currentData()
        if mode == "template":
            path, _ = QFileDialog.getOpenFileName(self, "Vorlage", "", "Template (*.dotx *.doct)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "DOCX", "", "Word (*.docx)")
        if path:
            self._source.setText(path)

    def payload(self) -> DocumentCreatePayload:
        return DocumentCreatePayload(
            mode=self._mode.currentData(),
            source_path=self._source.text().strip(),
            document_id=self._document_id.text().strip(),
            title=self._title.text().strip(),
            description=self._description.text().strip(),
            owner_user_id=self._owner.currentText().strip(),
            doc_type=self._doc_type.currentData(),
            workflow_profile_id=self._workflow_profile.text().strip() or "long_release",
        )

    def create_draft_only(self) -> bool:
        return self._draft_only.isChecked()
