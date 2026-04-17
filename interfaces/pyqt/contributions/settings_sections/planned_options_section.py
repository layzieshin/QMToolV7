"""Read-only roadmap / planned options table (extracted from settings_view.py)."""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QPlainTextEdit, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from interfaces.pyqt.contributions.common import as_json_text


class PlannedOptionsWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Bereich", "Option", "Priorität", "Status", "Abhängigkeit vom API-Vertrag"]
        )
        rows = [
            ("Profil", "Anzeigename bearbeiten", "hoch", "in pruefung", "usermanagement_service: kein Feld"),
            ("Profil", "E-Mail bearbeiten", "hoch", "in pruefung", "usermanagement_service: kein Feld"),
            ("Profil", "Abteilung bearbeiten", "mittel", "geplant", "usermanagement_service: kein Feld"),
            ("Benutzerverwaltung", "Status aktiv/inaktiv", "mittel", "geplant", "user status API fehlt"),
            ("Benutzerverwaltung", "Abteilung pro Benutzer", "mittel", "geplant", "department field API fehlt"),
            ("Benutzerverwaltung", "Rolle bestehender Benutzer ändern", "hoch", "in pruefung", "update-role API fehlt"),
        ]
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(value))
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()

        out = QPlainTextEdit()
        out.setReadOnly(True)
        out.setPlainText(
            as_json_text(
                {
                    "hinweis": "Geplante Optionen sind bewusst readonly und inventarisieren moegliche Erweiterungen ohne neue Fachlogik.",
                    "prioritaet_erklaerung": {"hoch": "relevant fuer naechste Iteration", "mittel": "nachrangig"},
                }
            )
        )
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Geplante Optionen (readonly, priorisiert)"))
        layout.addWidget(table, stretch=1)
        layout.addWidget(out, stretch=1)
