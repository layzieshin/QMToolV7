"""Top filter bar and advanced filter dialog for documents workflow.

Extracted from documents_workflow_view.py (Phase 3A).
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def build_top_filter_bar(
    *,
    on_refresh: Callable[[], None],
    on_advanced_filter: Callable[[], None],
    on_apply_filter: Callable[[], None],
    on_profile_manager: Callable[[], None],
) -> dict[str, object]:
    """Build the top filter/action button row. Returns {"layout": QHBoxLayout, "buttons": dict}."""
    row = QHBoxLayout()
    buttons: dict[str, QPushButton] = {}
    for key, label, handler in [
        ("refresh", "Aktualisieren", on_refresh),
        ("filter_advanced", "Erweiterter Filter", on_advanced_filter),
        ("filter", "Filter anwenden", on_apply_filter),
        ("profile_manager", "Workflowprofil-Manager", on_profile_manager),
    ]:
        btn = QPushButton(label)
        btn.clicked.connect(handler)
        buttons[key] = btn
        row.addWidget(btn)
    row.addStretch(1)
    return {"layout": row, "buttons": buttons}


def open_advanced_filter_dialog(
    parent: QWidget,
    current_filters: dict[str, object],
) -> dict[str, object] | None:
    """Show advanced filter dialog. Returns new filter dict or None if cancelled."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Erweiterter Filter")
    owner = QLineEdit(str(current_filters["owner_contains"]))
    title = QLineEdit(str(current_filters["title_contains"]))
    workflow_active = QComboBox()
    workflow_active.addItems(["all", "true", "false"])
    workflow_active.setCurrentText(str(current_filters["workflow_active"]))
    active_version = QComboBox()
    active_version.addItems(["all", "true", "false"])
    active_version.setCurrentText(str(current_filters["active_version"]))
    form = QFormLayout()
    form.addRow("Owner enthält", owner)
    form.addRow("Titel enthält", title)
    form.addRow("Workflow aktiv", workflow_active)
    form.addRow("Aktive Version", active_version)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Erweiterte Kriterien ergänzen die Schnellfilter."))
    layout.addLayout(form)
    layout.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return {
        "owner_contains": owner.text().strip().lower(),
        "title_contains": title.text().strip().lower(),
        "workflow_active": workflow_active.currentText(),
        "active_version": active_version.currentText(),
    }

