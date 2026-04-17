from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLineEdit, QVBoxLayout

from modules.documents.contracts import DocumentType



def transliterate_umlauts(raw: str) -> str:
    return (
        raw.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
        .replace("ß", "ss")
    )


def parse_document_id_and_title_from_filename(file_path: str) -> tuple[str, str]:
    stem = transliterate_umlauts(Path(file_path).stem.strip())
    if not stem or "_" not in stem:
        return "", ""
    document_id, title = stem.split("_", 1)
    document_id = document_id.strip()
    title = title.strip().replace("_", " ")
    return document_id, title


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

    def __init__(
        self,
        owner_ids: list[str],
        current_owner: str,
        *,
        profile_rules: dict[str, dict[str, object]] | None = None,
        can_override_profiles: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neues Dokument / Import")
        self._profile_rules = profile_rules or {}
        self._can_override_profiles = can_override_profiles
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
        self._workflow_profile = QComboBox()
        self._workflow_profile.addItem("long_release")
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
        form.addRow("Dokumentenkennung", self._document_id)
        form.addRow("Titel", self._title)
        form.addRow("Kurzbeschreibung", self._description)
        form.addRow("Owner", self._owner)
        form.addRow("Dokumenttyp", self._doc_type)
        form.addRow("Workflowprofil", self._workflow_profile)
        form.addRow("", self._draft_only)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._doc_type.currentIndexChanged.connect(self._apply_profile_rule_for_doc_type)
        self._apply_profile_rule_for_doc_type()

    def _apply_profile_rule_for_doc_type(self) -> None:
        doc_type = self._doc_type.currentData()
        if not isinstance(doc_type, DocumentType):
            return
        rule = self._profile_rules.get(doc_type.value, {})
        profile_id = str(rule.get("profile_id", "long_release") or "long_release")
        override_possible = bool(rule.get("override_possible", False))
        profile_ids_raw = rule.get("available_profiles", [profile_id])
        profile_ids = [str(v).strip() for v in profile_ids_raw if str(v).strip()]
        if profile_id not in profile_ids:
            profile_ids.insert(0, profile_id)
        self._workflow_profile.blockSignals(True)
        self._workflow_profile.clear()
        for pid in profile_ids:
            self._workflow_profile.addItem(pid)
        idx = self._workflow_profile.findText(profile_id)
        self._workflow_profile.setCurrentIndex(idx if idx >= 0 else 0)
        can_override = self._can_override_profiles and override_possible
        self._workflow_profile.setEnabled(can_override)
        self._workflow_profile.setToolTip(
            "Manuelle Profilauswahl erlaubt" if can_override else f"Fix zugewiesen: {profile_id}"
        )
        self._workflow_profile.blockSignals(False)

    def _pick_file(self) -> None:
        mode = self._mode.currentData()
        if mode == "template":
            path, _ = QFileDialog.getOpenFileName(self, "Vorlage", "", "Template (*.dotx *.doct)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "DOCX", "", "Word (*.docx)")
        if path:
            self._source.setText(path)
            parsed_id, parsed_title = parse_document_id_and_title_from_filename(path)
            if parsed_id and not self._document_id.text().strip():
                self._document_id.setText(parsed_id)
            if parsed_title and not self._title.text().strip():
                self._title.setText(parsed_title)

    def payload(self) -> DocumentCreatePayload:
        return DocumentCreatePayload(
            mode=self._mode.currentData(),
            source_path=self._source.text().strip(),
            document_id=self._document_id.text().strip(),
            title=self._title.text().strip(),
            description=self._description.text().strip(),
            owner_user_id=self._owner.currentText().strip(),
            doc_type=self._doc_type.currentData(),
            workflow_profile_id=self._workflow_profile.currentText().strip() or "long_release",
        )

    def create_draft_only(self) -> bool:
        return self._draft_only.isChecked()
