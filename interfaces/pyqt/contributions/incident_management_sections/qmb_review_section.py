"""QMB review and assessment section."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from interfaces.pyqt.contributions.incident_management_sections.base import BaseIncidentArea
from interfaces.pyqt.presenters.incident_management_presenter import IncidentManagementPresenter
from modules.incident_management.contracts import IncidentAssessmentInput, IncidentClassification
from qm_platform.runtime.container import RuntimeContainer


class QmbReviewSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="QMB-Pruefung")
        self._queue = QComboBox()
        self._inquiry_question = QLineEdit()
        self._classification = QComboBox()
        for item in IncidentClassification:
            label = IncidentManagementPresenter.CLASSIFICATION_LABELS.get(item, item.value)
            self._classification.addItem(label, item)
        self._critical = QCheckBox("Kritisch")
        self._critical_reason = QLineEdit()
        self._repeated = QCheckBox("Wiederholt")
        self._capa_required = QCheckBox("CAPA manuell")
        self._capa_reason = QLineEdit()
        self._rca_required = QCheckBox("RCA erforderlich")
        self._patient_safety = QCheckBox("Patientensicherheit")
        self._system_risk = QCheckBox("Systemrisiko")
        self._formal_deviation = QCheckBox("Formale Abweichung")
        self._result_correctness = QCheckBox("Ergebnisrichtigkeit")
        self._escalation = QCheckBox("Eskalation")

        form = QFormLayout()
        form.addRow("Offene Faelle", self._queue)
        form.addRow("Rueckfrage", self._inquiry_question)
        form.addRow("Einstufung", self._classification)
        form.addRow("", self._critical)
        form.addRow("Kritikalitaetsgrund", self._critical_reason)
        form.addRow("", self._repeated)
        form.addRow("", self._capa_required)
        form.addRow("CAPA-Grund", self._capa_reason)
        form.addRow("", self._rca_required)
        form.addRow("", self._patient_safety)
        form.addRow("", self._system_risk)
        form.addRow("", self._formal_deviation)
        form.addRow("", self._result_correctness)
        form.addRow("", self._escalation)
        self.layout().addLayout(form)

        self._similar = QTableWidget(0, 3)
        self._similar.setHorizontalHeaderLabels(["ID", "Titel", "Kategorie"])
        self._similar.setMaximumHeight(120)
        self.layout().addWidget(QLabel("Aehnliche Ereignisse"))
        self.layout().addWidget(self._similar)

        row = QHBoxLayout()
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self.reload)
        inquiry = QPushButton("Rueckfrage stellen")
        inquiry.clicked.connect(self._on_inquiry)
        assess = QPushButton("Bewerten")
        assess.clicked.connect(self._on_assess)
        row.addWidget(refresh)
        row.addWidget(inquiry)
        row.addWidget(assess)
        self.layout().addLayout(row)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self.layout().addWidget(self._status, stretch=1)
        self._queue.currentIndexChanged.connect(self._load_similar)

    def reload(self) -> None:
        try:
            cases = self._api().list_qmb_review_queue()
        except Exception as exc:  # noqa: BLE001
            self._queue.clear()
            self._similar.setRowCount(0)
            self._status.setText(str(exc))
            return
        current = self._queue.currentData()
        self._queue.clear()
        for case in cases:
            self._queue.addItem(f"{case.incident_id} | {case.title}", case.incident_id)
        if current:
            idx = self._queue.findData(current)
            if idx >= 0:
                self._queue.setCurrentIndex(idx)
        self._status.setText(self._presenter.status_line(count=len(cases), label="Offene Pruefung"))
        self._load_similar()

    def _load_similar(self) -> None:
        incident_id = self._queue.currentData()
        if not incident_id:
            self._similar.setRowCount(0)
            return
        try:
            cases = self._api().list_similar_incident_candidates(incident_id)
        except Exception as exc:  # noqa: BLE001
            self._similar.setRowCount(0)
            self._status.setText(str(exc))
            return
        self._similar.setRowCount(len(cases))
        for row, case in enumerate(cases):
            for col, value in enumerate((case.incident_id, case.title, case.category)):
                self._similar.setItem(row, col, QTableWidgetItem(value))

    def _on_inquiry(self) -> None:
        incident_id = self._queue.currentData()
        if not incident_id:
            self.show_info(self, "Rueckfrage", "Kein Ereignis ausgewaehlt.")
            return
        question = self._inquiry_question.text().strip()
        if not question:
            self.show_info(self, "Rueckfrage", "Bitte eine Frage eingeben.")
            return
        try:
            self._api().open_inquiry(incident_id, question)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Rueckfrage fehlgeschlagen", exc)
            return
        self._inquiry_question.clear()
        self._status.setText(f"Rueckfrage fuer {incident_id} gestellt.")
        self.reload()

    def _on_assess(self) -> None:
        incident_id = self._queue.currentData()
        if not incident_id:
            self.show_info(self, "QMB-Pruefung", "Kein Ereignis ausgewaehlt.")
            return
        assessment = IncidentAssessmentInput(
            classification=self._classification.currentData(),
            is_critical=self._critical.isChecked(),
            criticality_reason=self._critical_reason.text().strip() or None,
            is_repeated=self._repeated.isChecked(),
            capa_required=self._capa_required.isChecked(),
            capa_reason=self._capa_reason.text().strip() or None,
            root_cause_required=self._rca_required.isChecked(),
            patient_safety_relevant=self._patient_safety.isChecked(),
            formal_deviation=self._formal_deviation.isChecked(),
            system_risk_relevant=self._system_risk.isChecked(),
            result_correctness_issue=self._result_correctness.isChecked(),
            escalation_required=self._escalation.isChecked(),
        )
        try:
            case = self._api().assess_incident(incident_id, assessment)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Bewertung fehlgeschlagen", exc)
            return
        self._status.setText(f"Bewertet: {case.incident_id} -> {case.status.value}")
        self.reload()
