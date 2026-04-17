"""Workflow action bar for documents workflow.

Extracted from documents_workflow_view.py (Phase 3A).
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QHBoxLayout, QPushButton


def build_workflow_action_bar(
    *,
    on_new: Callable[[], None],
    on_start: Callable[[], None],
    on_abort: Callable[[], None],
    on_edit: Callable[[], None],
    on_complete: Callable[[], None],
    on_review_accept: Callable[[], None],
    on_review_reject: Callable[[], None],
    on_approval_accept: Callable[[], None],
    on_approval_reject: Callable[[], None],
    on_archive: Callable[[], None],
) -> dict[str, object]:
    """Build the workflow action button row. Returns {"layout": QHBoxLayout, "buttons": dict}."""
    row = QHBoxLayout()
    buttons: dict[str, QPushButton] = {}
    for key, label, handler in [
        ("new", "Neu / Import", on_new),
        ("start", "Workflow starten", on_start),
        ("abort", "Workflow abbrechen", on_abort),
        ("edit", "Oeffnen / Bearbeiten", on_edit),
        ("complete", "Bearbeitung annehmen", on_complete),
        ("review_accept", "Pruefung annehmen", on_review_accept),
        ("review_reject", "Pruefung ablehnen", on_review_reject),
        ("approval_accept", "Freigabe annehmen", on_approval_accept),
        ("approval_reject", "Freigabe ablehnen", on_approval_reject),
        ("archive", "Archivieren", on_archive),
    ]:
        btn = QPushButton(label)
        btn.clicked.connect(handler)
        buttons[key] = btn
        row.addWidget(btn)
    buttons["new"].setStyleSheet("background-color: #9e9e9e; color: #111111;")
    buttons["start"].setStyleSheet("background-color: #b7f0b1; color: #111111;")
    buttons["abort"].setStyleSheet("background-color: #ffb3b3; color: #111111;")
    row.addStretch(1)
    return {"layout": row, "buttons": buttons}


def update_action_visibility(
    workflow_buttons: dict[str, QPushButton],
    top_buttons: dict[str, QPushButton],
    visible_actions: set[str],
    profile_manager_allowed: bool,
) -> None:
    """Update button visibility/enabled state based on presenter output."""
    for key, button in workflow_buttons.items():
        allowed = key in visible_actions
        button.setVisible(allowed)
        button.setEnabled(allowed)
        if not allowed:
            button.setToolTip("")
    top_buttons["profile_manager"].setVisible(profile_manager_allowed)
    top_buttons["profile_manager"].setEnabled(profile_manager_allowed)

