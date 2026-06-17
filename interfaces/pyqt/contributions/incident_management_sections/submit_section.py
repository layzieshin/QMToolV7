"""Submit / report incident section."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PyQt6.QtCore import QDate, QTime
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTimeEdit,
)

from interfaces.pyqt.contributions.incident_management_sections.base import BaseIncidentArea
from modules.incident_management.contracts import ArtifactType, IncidentSubmission
from qm_platform.runtime.container import RuntimeContainer


class ReportEventSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="Ereignis melden")
        form = QFormLayout()
        self._title = QLineEdit()
        self._description = QPlainTextEdit()
        self._description.setMinimumHeight(100)
        self._category = QComboBox()
        self._labels = QLineEdit()
        self._labels.setPlaceholderText("Kommagetrennt, z. B. prozess, geraet")
        self._area = QLineEdit()
        self._process = QLineEdit()
        self._device = QLineEdit()
        self._reported_date = QDateEdit()
        self._reported_date.setCalendarPopup(True)
        self._reported_date.setDate(QDate.currentDate())
        self._reported_time = QTimeEdit()
        self._reported_time.setTime(QTime.currentTime())
        self._attachment_path: Path | None = None
        self._attachment_label = QLabel("Kein Anhang")
        pick_attachment = QPushButton("Anhang waehlen")
        pick_attachment.clicked.connect(self._pick_attachment)

        form.addRow("Titel", self._title)
        form.addRow("Beschreibung", self._description)
        form.addRow("Kategorie", self._category)
        form.addRow("Labels", self._labels)
        form.addRow("Bereich", self._area)
        form.addRow("Prozess", self._process)
        form.addRow("Geraet", self._device)
        form.addRow("Feststellungsdatum", self._reported_date)
        form.addRow("Feststellungszeit", self._reported_time)
        attachment_row = QHBoxLayout()
        attachment_row.addWidget(pick_attachment)
        attachment_row.addWidget(self._attachment_label, stretch=1)
        form.addRow("Anhang", attachment_row)
        self.layout().addLayout(form)

        buttons = QHBoxLayout()
        preview = QPushButton("Vorschau")
        preview.clicked.connect(self._on_preview)
        submit = QPushButton("Melden")
        submit.clicked.connect(self._on_submit)
        buttons.addWidget(preview)
        buttons.addWidget(submit)
        self.layout().addLayout(buttons)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self.layout().addWidget(self._status, stretch=1)

    def _pick_attachment(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Anhang waehlen")
        if not path:
            return
        self._attachment_path = Path(path)
        self._attachment_label.setText(self._attachment_path.name)

    def _reported_at(self) -> datetime:
        date = self._reported_date.date()
        time = self._reported_time.time()
        return datetime(
            date.year(),
            date.month(),
            date.day(),
            time.hour(),
            time.minute(),
            time.second(),
            tzinfo=UTC,
        )

    def reload(self) -> None:
        try:
            settings = self._api().get_module_settings()
            categories = list(settings.get("categories") or [])
        except Exception:
            categories = ["Prozess", "Gerät", "Dokumentation", "Patientensicherheit", "Sonstiges"]
        current = self._category.currentText()
        self._category.clear()
        self._category.addItems(categories)
        if current:
            idx = self._category.findText(current)
            if idx >= 0:
                self._category.setCurrentIndex(idx)

    def _submission(self) -> IncidentSubmission:
        return IncidentSubmission(
            title=self._title.text(),
            description=self._description.toPlainText(),
            category=self._category.currentText(),
            reported_at=self._reported_at(),
            labels=self._presenter.parse_labels(self._labels.text()),
            area=self._area.text().strip() or None,
            process_name=self._process.text().strip() or None,
            device=self._device.text().strip() or None,
        )

    def _on_preview(self) -> None:
        text = self._presenter.preview_submission(
            title=self._title.text(),
            description=self._description.toPlainText(),
            category=self._category.currentText(),
            reported_at=self._reported_at(),
            labels=self._presenter.parse_labels(self._labels.text()),
            area=self._area.text().strip() or None,
            process_name=self._process.text().strip() or None,
            device=self._device.text().strip() or None,
            attachment_name=self._attachment_path.name if self._attachment_path else None,
        )
        self.show_info(self, "Melde-Vorschau", text)

    def _on_submit(self) -> None:
        try:
            case = self._api().submit_incident(self._submission())
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Meldung fehlgeschlagen", exc)
            return
        if self._attachment_path is not None:
            try:
                self._api().attach_artifact(case.incident_id, self._attachment_path, ArtifactType.ATTACHMENT)
            except Exception as exc:  # noqa: BLE001
                self._status.setText(
                    f"Ereignis gemeldet: {case.incident_id} (Anhang fehlgeschlagen: {exc})"
                )
                return
        self._status.setText(f"Ereignis gemeldet: {case.incident_id}")
        self._title.clear()
        self._description.clear()
        self._labels.clear()
        self._area.clear()
        self._process.clear()
        self._device.clear()
        self._attachment_path = None
        self._attachment_label.setText("Kein Anhang")
