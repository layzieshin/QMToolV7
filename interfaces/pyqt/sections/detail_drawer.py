"""Detail drawer with tabs for documents workflow.

Extracted from documents_workflow_view.py (Phase 3A).
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.widgets.drawer_panel import DrawerPanel
from interfaces.pyqt.widgets.table_helpers import configure_readonly_table


def new_readonly_table(headers: list[str]) -> QTableWidget:
    """Create a read-only QTableWidget with the given headers."""
    table = QTableWidget(0, len(headers))
    configure_readonly_table(table, headers)
    return table


def build_metadata_tab(
    *,
    doc_id: QLineEdit,
    version: QLineEdit,
    title: QLineEdit,
    description: QLineEdit,
    doc_type: QComboBox,
    control_class: QComboBox,
    profile: QLineEdit,
    department: QLineEdit,
    site: QLineEdit,
    regulatory_scope: QLineEdit,
    valid_until: QLineEdit,
    next_review: QLineEdit,
    custom_fields: QLineEdit,
    on_save_metadata: Callable[[], None],
    on_save_header: Callable[[], None],
    metadata_buttons: list[QPushButton],
) -> QWidget:
    """Build the metadata editing tab."""
    tab = QWidget()
    layout = QVBoxLayout(tab)
    form = QFormLayout()
    form.addRow("Dokumentenkennung", doc_id)
    form.addRow("Version", version)
    form.addRow("Titel", title)
    form.addRow("Kurzbeschreibung", description)
    form.addRow("Dokumenttyp", doc_type)
    form.addRow("Kontrollklasse", control_class)
    form.addRow("Workflowprofil", profile)
    form.addRow("Department", department)
    form.addRow("Standort", site)
    form.addRow("Regulatory Scope", regulatory_scope)
    form.addRow("gueltig_bis (YYYY-MM-DD)", valid_until)
    form.addRow("naechste_pruefung (YYYY-MM-DD)", next_review)
    form.addRow("Custom Fields JSON", custom_fields)
    layout.addLayout(form)
    row = QHBoxLayout()
    btn_meta = QPushButton("Metadaten speichern")
    btn_meta.clicked.connect(on_save_metadata)
    btn_header = QPushButton("Header speichern")
    btn_header.clicked.connect(on_save_header)
    metadata_buttons.extend([btn_meta, btn_header])
    row.addWidget(btn_meta)
    row.addWidget(btn_header)
    row.addStretch(1)
    layout.addLayout(row)
    return tab


def build_roles_tab(
    *,
    editors: QLineEdit,
    reviewers: QLineEdit,
    approvers: QLineEdit,
    tab_roles: QTableWidget,
    on_save_roles: Callable[[], None],
    roles_buttons: list[QPushButton],
) -> QWidget:
    """Build the roles editing tab."""
    tab = QWidget()
    layout = QVBoxLayout(tab)
    assignments = QFormLayout()
    assignments.addRow("Editoren CSV", editors)
    assignments.addRow("Pruefer CSV", reviewers)
    assignments.addRow("Freigeber CSV", approvers)
    layout.addLayout(assignments)
    row = QHBoxLayout()
    btn_roles = QPushButton("Rollen speichern")
    btn_roles.clicked.connect(on_save_roles)
    roles_buttons.append(btn_roles)
    row.addWidget(btn_roles)
    row.addStretch(1)
    layout.addLayout(row)
    layout.addWidget(tab_roles, stretch=1)
    return tab


def build_extension_tab(
    *,
    next_version: QLineEdit,
    on_extend: Callable[[], None],
    on_new_version: Callable[[], None],
) -> QWidget:
    """Build the annual extension tab."""
    tab = QWidget()
    layout = QVBoxLayout(tab)
    form = QFormLayout()
    form.addRow("Naechste Version", next_version)
    layout.addLayout(form)
    row = QHBoxLayout()
    for label, handler in [
        ("Verlaengern (mit Signatur)", on_extend),
        ("Neue Version nach Archiv", on_new_version),
    ]:
        b = QPushButton(label)
        b.clicked.connect(handler)
        row.addWidget(b)
    row.addStretch(1)
    layout.addLayout(row)
    layout.addWidget(QLabel(
        "Verlaengerung und Folgeschritte fuer archivierte Versionen. "
        "Gueltigkeitsverlängerung erfordert Signatur und erhöht das Review-Datum um 1 Jahr."
    ))
    return tab


class DetailDrawerBuilder:
    """Builds the detail drawer panel with all tabs. Returns (panel, detail_tabs, history_tab_index)."""

    @staticmethod
    def build(
        *,
        tab_overview: QTableWidget,
        tab_roles: QTableWidget,
        tab_comments: QPlainTextEdit,
        tab_history: QTableWidget,
        history_notice: QLabel,
        metadata_tab: QWidget,
        roles_tab: QWidget,
        extension_tab: QWidget,
    ) -> tuple[DrawerPanel, QTabWidget, int]:
        """Returns (drawer_panel, detail_tabs, history_tab_index)."""
        panel = DrawerPanel("Details")
        content = QWidget()
        layout = QVBoxLayout(content)
        detail_tabs = QTabWidget()
        detail_tabs.addTab(tab_overview, "Ueberblick")
        detail_tabs.addTab(metadata_tab, "Metadaten")
        detail_tabs.addTab(roles_tab, "Rollen")
        detail_tabs.addTab(tab_comments, "Kommentare")
        history_tab_index = detail_tabs.addTab(tab_history, "Verlauf")
        detail_tabs.addTab(extension_tab, "Verlaengerung")
        layout.addWidget(history_notice)
        layout.addWidget(detail_tabs)
        panel.set_content_widget(content)
        return panel, detail_tabs, history_tab_index

