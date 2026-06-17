"""Open actions section."""
from __future__ import annotations

from PyQt6.QtWidgets import (
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
from modules.incident_management.contracts import ActionType
from qm_platform.runtime.container import RuntimeContainer


class ActionsSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="Offene Massnahmen")
        toolbar = QHBoxLayout()
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self.reload)
        toolbar.addWidget(refresh)
        toolbar.addStretch(1)
        self.layout().addLayout(toolbar)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Ereignis", "Massnahme", "Typ", "Status", "Frist"])
        self.layout().addWidget(self._table, stretch=1)

        create_form = QFormLayout()
        self._incident_id = QLineEdit()
        self._action_type = QComboBox()
        for action_type in ActionType:
            label = self._presenter.ACTION_TYPE_LABELS.get(action_type.value, action_type.value)
            self._action_type.addItem(label, action_type)
        self._description = QLineEdit()
        self._owner = QLineEdit()
        self._evidence = QLineEdit()
        create_form.addRow("Ereignis-ID", self._incident_id)
        create_form.addRow("Typ", self._action_type)
        create_form.addRow("Beschreibung", self._description)
        create_form.addRow("Verantwortlicher", self._owner)
        create_form.addRow("Nachweis", self._evidence)

        create_btn = QPushButton("Massnahme anlegen")
        create_btn.clicked.connect(self._on_create)
        complete_btn = QPushButton("Ausgewaehlte abschliessen")
        complete_btn.clicked.connect(self._on_complete)

        action_row = QHBoxLayout()
        action_row.addLayout(create_form)
        action_row.addWidget(create_btn)
        action_row.addWidget(complete_btn)
        self.layout().addLayout(action_row)

        self._status = QLabel("")
        self.layout().addWidget(self._status)

    def reload(self) -> None:
        try:
            actions = self._api().list_open_actions()
        except Exception as exc:  # noqa: BLE001
            self._table.setRowCount(0)
            self._status.setText(str(exc))
            return
        self._table.setRowCount(len(actions))
        for row, action in enumerate(actions):
            for col, value in enumerate(self._presenter.format_action_row(action)):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._status.setText(self._presenter.status_line(count=len(actions), label="Offene Massnahmen"))

    def _on_create(self) -> None:
        incident_id = self._incident_id.text().strip()
        description = self._description.text().strip()
        if not incident_id or not description:
            self.show_info(self, "Massnahme", "Ereignis-ID und Beschreibung erforderlich.")
            return
        owner = self._owner.text().strip() or None
        try:
            action = self._api().create_action(
                incident_id,
                self._action_type.currentData(),
                description,
                owner_user_id=owner,
            )
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Massnahme fehlgeschlagen", exc)
            return
        self._status.setText(f"Massnahme {action.action_id} angelegt.")
        self.reload()

    def _on_complete(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            self.show_info(self, "Abschliessen", "Bitte eine Massnahme auswaehlen.")
            return
        action_id_item = self._table.item(row, 1)
        if action_id_item is None:
            return
        try:
            self._api().complete_action(action_id_item.text())
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Abschliessen fehlgeschlagen", exc)
            return
        self._status.setText(f"Massnahme {action_id_item.text()} abgeschlossen.")
        self.reload()
