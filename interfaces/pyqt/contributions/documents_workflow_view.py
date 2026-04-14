from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QTableWidget,
    QTabWidget,
    QToolButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import parse_csv_set, role_to_system_role
from interfaces.pyqt.widgets.document_create_wizard import DocumentCreateWizard
from interfaces.pyqt.widgets.reject_reason_dialog import RejectReasonDialog
from interfaces.pyqt.widgets.action_bar import ActionBar
from interfaces.pyqt.widgets.drawer_panel import DrawerPanel
from interfaces.pyqt.widgets.signature_request_form import SignatureRequestForm
from interfaces.pyqt.widgets.table_helpers import configure_readonly_table, fill_table
from interfaces.pyqt.widgets.workflow_start_wizard import WorkflowStartWizard
from interfaces.pyqt.presenters.documents_workflow_filter_presenter import DocumentsWorkflowFilterPresenter
from interfaces.pyqt.presenters.documents_workflow_presenter import DocumentsWorkflowPresenter
from interfaces.pyqt.registry.contribution import QtModuleContribution
from modules.documents.contracts import ArtifactType, ControlClass, DocumentStatus, DocumentType, RejectionReason
from qm_platform.runtime.container import RuntimeContainer


@dataclass
class WizardPayload:
    mode: str
    source_path: str
    document_id: str
    title: str
    description: str
    owner_user_id: str
    doc_type: DocumentType
    workflow_profile_id: str


class DocumentWizard(QDialog):
    def __init__(self, owner_ids: list[str], current_owner: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neu / Importieren")
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
        for t in DocumentType:
            self._doc_type.addItem(t.value, t)
        self._profile = QLineEdit("long_release")
        self._as_draft = QCheckBox("Nur als Entwurf anlegen (kein Importschritt)")
        self._as_draft.setChecked(False)
        self._context_help = QLabel("")
        self._context_help.setWordWrap(True)
        self._context_help.setObjectName("heroBody")

        form = QFormLayout()
        form.addRow("Quelle", self._mode)
        form.addRow("Datei", self._source)
        pick = QPushButton("Datei waehlen")
        pick.clicked.connect(self._pick_file)
        form.addRow("", pick)
        form.addRow("Dokumentenkennung", self._document_id)
        form.addRow("Titel", self._title)
        form.addRow("Kurzbeschreibung", self._description)
        form.addRow("Owner", self._owner)
        form.addRow("Dokumenttyp", self._doc_type)
        form.addRow("Workflowprofil", self._profile)
        form.addRow("", self._as_draft)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Wizard-Einstieg fuer Neu/Import. Version wird in dieser Iteration automatisch auf 1 gesetzt.")
        )
        layout.addWidget(self._context_help)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._mode.currentIndexChanged.connect(self._update_help)
        self._document_id.textChanged.connect(self._update_help)
        self._title.textChanged.connect(self._update_help)
        self._source.textChanged.connect(self._update_help)
        self._update_help()

    def _pick_file(self) -> None:
        mode = self._mode.currentData()
        if mode == "template":
            path, _ = QFileDialog.getOpenFileName(self, "Vorlage waehlen", "", "Template (*.dotx *.doct)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "DOCX waehlen", "", "Word (*.docx)")
        if path:
            self._source.setText(path)

    def payload(self) -> WizardPayload:
        return WizardPayload(
            mode=self._mode.currentData(),
            source_path=self._source.text().strip(),
            document_id=self._document_id.text().strip(),
            title=self._title.text().strip(),
            description=self._description.text().strip(),
            owner_user_id=self._owner.currentText().strip(),
            doc_type=self._doc_type.currentData(),
            workflow_profile_id=self._profile.text().strip() or "long_release",
        )

    def create_draft_only(self) -> bool:
        return self._as_draft.isChecked()

    def _update_help(self) -> None:
        mode = self._mode.currentData()
        missing: list[str] = []
        if not self._document_id.text().strip():
            missing.append("Dokumentenkennung")
        if not self._title.text().strip():
            missing.append("Titel")
        if not self._source.text().strip() and not self._as_draft.isChecked():
            missing.append("Quelldatei")
        source_hint = "Vorlage (.dotx/.doct)" if mode == "template" else "Word-Dokument (.docx)"
        missing_hint = ", ".join(missing) if missing else "keine Pflichtfelder fehlen"
        self._context_help.setText(
            f"Schritt-Hinweis: Quelle ist {source_hint}. Pflichtfelder aktuell offen: {missing_hint}. "
            "Du kannst jederzeit korrigieren, bevor angelegt wird."
        )


class TextReasonDialog(QDialog):
    def __init__(self, title: str, template_label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._template = QLineEdit()
        self._free_text = QLineEdit()
        form = QFormLayout()
        form.addRow(template_label, self._template)
        form.addRow("Optionaler Freitext", self._free_text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        hint = QLabel("Bitte einen klaren, kurzen Grund angeben. Optional kann zusätzlicher Kontext ergänzt werden.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def reason(self) -> RejectionReason:
        return RejectionReason(
            template_text=self._template.text().strip() or None,
            free_text=self._free_text.text().strip() or None,
        )


class _WorkflowTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._headers = ["Dokumentenkennung", "Titel", "Status", "Workflow aktiv", "Aktive Version"]
        self._rows: list[object] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self._headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return str(section + 1)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        state = self._rows[index.row()]
        values = [
            state.document_id,
            state.title,
            state.status.value,
            "Ja" if state.workflow_active else "Nein",
            "Ja" if state.status != DocumentStatus.ARCHIVED else "Nein",
        ]
        return values[index.column()]

    def load(self, rows: list[object]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


class DocumentsWorkflowWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
        self._um = container.get_port("usermanagement_service")
        self._docs_service = container.get_port("documents_service")
        self._pool = container.get_port("documents_pool_api")
        self._wf = container.get_port("documents_workflow_api")
        self._artifacts_root = self._resolve_artifacts_root()
        self._presenter = DocumentsWorkflowPresenter()
        self._filter_presenter = DocumentsWorkflowFilterPresenter()
        self._current_state = None
        self._advanced_filters: dict[str, object] = {
            "owner_contains": "",
            "title_contains": "",
            "workflow_active": "all",
            "active_version": "all",
        }
        self._seen_event_ids: dict[str, str | None] = {}

        self._status_filter = QComboBox()
        self._status_filter.addItem("Alle", "ALL")
        for status in DocumentStatus:
            self._status_filter.addItem(status.value, status)
        self._scope_filter = QComboBox()
        self._scope_filter.addItem("Alle", "all")
        self._scope_filter.addItem("Meine Dokumente", "mine")
        self._scope_filter.addItem("Meine Aufgaben", "tasks")
        self._density = QComboBox()
        self._density.addItem("Kompakt", "compact")
        self._density.addItem("Komfortabel", "comfortable")
        self._model = _WorkflowTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(1, self._table.horizontalHeader().ResizeMode.Stretch)
        self._table.selectionModel().selectionChanged.connect(self._on_table_selected)
        self._table.doubleClicked.connect(lambda _idx: self._run_default_table_action())

        self._doc_id = QLineEdit()
        self._version = QLineEdit("1")
        self._title = QLineEdit()
        self._description = QLineEdit()
        self._doc_type = QComboBox()
        self._control_class = QComboBox()
        for dt in DocumentType:
            self._doc_type.addItem(dt.value, dt)
        for cc in ControlClass:
            self._control_class.addItem(cc.value, cc)
        self._profile = QLineEdit("long_release")
        self._department = QLineEdit()
        self._site = QLineEdit()
        self._regulatory_scope = QLineEdit()
        self._valid_until = QLineEdit()
        self._next_review = QLineEdit()
        self._custom_fields = QLineEdit("{}")
        self._editors = QLineEdit()
        self._reviewers = QLineEdit()
        self._approvers = QLineEdit()
        self._next_version = QLineEdit("2")
        self._sign_form = SignatureRequestForm()
        self._extend_signature = QCheckBox("Signatur fuer Jahresverlaengerung liegt vor")
        self._extend_signature.setChecked(False)

        self._tab_overview = self._new_readonly_table(["Feld", "Wert"])
        self._tab_workflow = self._new_readonly_table(["Aspekt", "Wert"])
        self._tab_comments = QPlainTextEdit()
        self._tab_comments.setReadOnly(True)
        self._tab_comments.setPlainText("Kommentare werden vorbereitet. Datenanbindung folgt ueber vorhandene Ports.")
        self._tab_history = self._new_readonly_table(["Zeit", "Aktion", "Benutzer", "Ergebnis", "Begruendung"])
        self._history_notice = QLabel("Verlauf ohne neue Änderungen.")
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._inline_notice = QLabel("")
        self._inline_notice.setWordWrap(True)

        self._actions = self._build_action_bar()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self._actions["widget"])
        chips = QHBoxLayout()
        self._chip_my_tasks = QToolButton()
        self._chip_my_tasks.setText("Meine Aufgaben")
        self._chip_my_tasks.clicked.connect(lambda: self._apply_quick_filter("tasks"))
        self._chip_review = QToolButton()
        self._chip_review.setText("In Prüfung")
        self._chip_review.clicked.connect(lambda: self._apply_quick_filter("review"))
        self._chip_approval = QToolButton()
        self._chip_approval.setText("In Freigabe")
        self._chip_approval.clicked.connect(lambda: self._apply_quick_filter("approval"))
        self._chip_all = QToolButton()
        self._chip_all.setText("Alle")
        self._chip_all.clicked.connect(lambda: self._apply_quick_filter("all"))
        for chip in (self._chip_my_tasks, self._chip_review, self._chip_approval, self._chip_all):
            chips.addWidget(chip)
        chips.addStretch(1)
        left_layout.addLayout(chips)
        filters = QFormLayout()
        filters.addRow("Status", self._status_filter)
        filters.addRow("Scope", self._scope_filter)
        filters.addRow("Dichte", self._density)
        left_layout.addLayout(filters)
        left_layout.addWidget(self._inline_notice)
        left_layout.addWidget(self._table, stretch=1)
        left_layout.addWidget(QLabel("Ergebnis / Fehler"))
        left_layout.addWidget(self._out, stretch=1)

        self._details = self._build_detail_drawer()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self._details)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 3)
        self._details.setVisible(False)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Dokumentenlenkung als arbeitsorientierter Bereich: Aktionsleiste, Tabelle und ausklappbare Detailansicht."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addWidget(splitter, stretch=1)

        self._status_filter.currentIndexChanged.connect(lambda _i: self._reload_table())
        self._scope_filter.currentIndexChanged.connect(lambda _i: self._reload_table())
        self._density.currentIndexChanged.connect(lambda _i: self._apply_table_density())
        self._scope_filter.setCurrentIndex(self._scope_filter.findData("tasks"))
        self._apply_table_density()
        self._reload_table()

    def _build_action_bar(self) -> dict[str, object]:
        bar = ActionBar()
        buttons: dict[str, QPushButton] = {}
        for key, label, handler in [
            ("new", "Neu / Importieren", self._new_import),
            ("refresh", "Aktualisieren", self._reload_table),
            ("filter", "Schnellfilter anwenden", self._reload_table),
            ("filter_advanced", "Erweiterter Filter", self._open_advanced_filter),
            ("edit", "Bearbeiten", self._edit_docx),
            ("start", "Workflow starten", self._start_workflow),
            ("complete", "Phase abschliessen", self._complete_editing),
            ("abort", "Workflow abbrechen", self._abort_workflow),
            ("review_accept", "Pruefung annehmen", self._review_accept),
            ("review_reject", "Pruefung ablehnen", self._review_reject),
            ("approval_accept", "Freigabe annehmen", self._approval_accept),
            ("approval_reject", "Freigabe ablehnen", self._approval_reject),
            ("archive", "Archivieren", self._archive_approved),
            ("details", "Details", self._toggle_details),
        ]:
            btn = bar.add_action(key, label, handler)
            buttons[key] = btn
        bar.finish()
        return {"widget": bar, "buttons": buttons}

    def _build_detail_drawer(self) -> QWidget:
        panel = DrawerPanel("Details")
        content = QWidget()
        layout = QVBoxLayout(content)
        self._detail_tabs = QTabWidget()
        self._detail_tabs.addTab(self._tab_overview, "Ueberblick")
        self._detail_tabs.addTab(self._build_metadata_tab(), "Metadaten")
        self._detail_tabs.addTab(self._build_workflow_tab(), "Workflow")
        self._detail_tabs.addTab(self._tab_comments, "Kommentare")
        self._history_tab_index = self._detail_tabs.addTab(self._tab_history, "Verlauf")
        layout.addWidget(self._history_notice)
        layout.addWidget(self._detail_tabs)
        panel.set_content_widget(content)
        return panel

    def _build_metadata_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        form.addRow("Dokument-ID", self._doc_id)
        form.addRow("Version", self._version)
        form.addRow("Titel", self._title)
        form.addRow("Kurzbeschreibung", self._description)
        form.addRow("Dokumenttyp", self._doc_type)
        form.addRow("Kontrollklasse", self._control_class)
        form.addRow("Workflowprofil", self._profile)
        form.addRow("Department", self._department)
        form.addRow("Standort", self._site)
        form.addRow("Regulatory Scope", self._regulatory_scope)
        form.addRow("gueltig_bis (YYYY-MM-DD)", self._valid_until)
        form.addRow("naechste_pruefung (YYYY-MM-DD)", self._next_review)
        form.addRow("Custom Fields JSON", self._custom_fields)
        layout.addLayout(form)
        row = QHBoxLayout()
        btn_meta = QPushButton("Metadaten speichern")
        btn_meta.clicked.connect(self._update_metadata)
        btn_header = QPushButton("Header speichern")
        btn_header.clicked.connect(self._update_header)
        row.addWidget(btn_meta)
        row.addWidget(btn_header)
        row.addStretch(1)
        layout.addLayout(row)
        return tab

    def _build_workflow_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        assignments = QFormLayout()
        assignments.addRow("Editoren CSV", self._editors)
        assignments.addRow("Pruefer CSV", self._reviewers)
        assignments.addRow("Freigeber CSV", self._approvers)
        assignments.addRow("Naechste Version", self._next_version)
        assignments.addRow("", self._extend_signature)
        layout.addLayout(assignments)
        layout.addWidget(QLabel("Optionaler Signaturdialog fuer Phasenuebergaenge"))
        layout.addWidget(self._sign_form)
        row = QHBoxLayout()
        for label, handler in [
            ("Rollen speichern", self._assign_roles),
            ("Jahresgueltigkeit verlaengern", self._extend_validity),
            ("Neue Version nach Archiv", self._new_version_after_archive),
        ]:
            b = QPushButton(label)
            b.clicked.connect(handler)
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(self._tab_workflow, stretch=1)
        return tab

    def _new_readonly_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        configure_readonly_table(table, headers)
        return table

    def _fill_two_col_table(self, table: QTableWidget, rows: list[tuple[str, str]]) -> None:
        fill_table(table, rows)

    def _fill_history_table(self, rows: list[tuple[str, str, str, str, str]]) -> None:
        fill_table(self._tab_history, rows)

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}: {payload}\n")
        self._inline_notice.setText(f"Info: {title}")

    def _show_error(self, exc: Exception, *, critical: bool = False) -> None:
        if critical:
            QMessageBox.warning(self, "Dokumentenlenkung", str(exc))
        self._inline_notice.setText(f"Warnung: {exc}")
        self._append("ERROR", {"message": str(exc)})

    def _apply_table_density(self) -> None:
        mode = self._density.currentData()
        if mode == "compact":
            self._table.verticalHeader().setDefaultSectionSize(24)
        else:
            self._table.verticalHeader().setDefaultSectionSize(34)
        self._inline_notice.setText(f"Tabellendichte aktiv: {'Kompakt' if mode == 'compact' else 'Komfortabel'}")

    def _apply_quick_filter(self, mode: str) -> None:
        preset = self._filter_presenter.preset(mode)
        self._scope_filter.setCurrentIndex(self._scope_filter.findData(preset.scope))
        self._status_filter.setCurrentIndex(self._status_filter.findData(preset.status_filter))
        self._reload_table()

    def _open_advanced_filter(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Erweiterter Filter")
        owner = QLineEdit(str(self._advanced_filters["owner_contains"]))
        title = QLineEdit(str(self._advanced_filters["title_contains"]))
        workflow_active = QComboBox()
        workflow_active.addItems(["all", "true", "false"])
        workflow_active.setCurrentText(str(self._advanced_filters["workflow_active"]))
        active_version = QComboBox()
        active_version.addItems(["all", "true", "false"])
        active_version.setCurrentText(str(self._advanced_filters["active_version"]))
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
            return
        self._advanced_filters = {
            "owner_contains": owner.text().strip().lower(),
            "title_contains": title.text().strip().lower(),
            "workflow_active": workflow_active.currentText(),
            "active_version": active_version.currentText(),
        }
        self._reload_table()

    def _current_user_role(self):
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        return user, role_to_system_role(user.role)

    def _state_from_selection(self):
        if self._current_state is None:
            raise RuntimeError("Bitte zuerst ein Dokument in der Tabelle auswaehlen")
        return self._current_state

    def _reload_table(self) -> None:
        try:
            rows: list[object] = []
            status_filter = self._status_filter.currentData()
            statuses = list(DocumentStatus) if status_filter == "ALL" else [status_filter]
            for status in statuses:
                rows.extend(self._pool.list_by_status(status))
            user = self._um.get_current_user()
            scope = self._scope_filter.currentData()
            rows = self._filter_presenter.filter_rows(
                rows,
                scope=str(scope),
                user_id=str(user.user_id) if user is not None else None,
                owner_contains=str(self._advanced_filters["owner_contains"]),
                title_contains=str(self._advanced_filters["title_contains"]),
                workflow_active=str(self._advanced_filters["workflow_active"]),
                active_version=str(self._advanced_filters["active_version"]),
            )
            self._model.load(rows)
            self._append(
                "TABELLE_AKTUALISIERT",
                {"rows": len(rows), "scope": scope, "status_filter": str(status_filter), "advanced": self._advanced_filters},
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_table_selected(self) -> None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            self._current_state = None
            self._update_action_visibility()
            return
        self._current_state = self._model._rows[selected[0].row()]
        self._doc_id.setText(self._current_state.document_id)
        self._version.setText(str(self._current_state.version))
        self._refresh_details()
        self._update_action_visibility()

    def _update_action_visibility(self) -> None:
        buttons = self._actions["buttons"]
        always = {"new", "refresh", "filter", "filter_advanced"}
        for key, button in buttons.items():
            button.setVisible(key in always)
            button.setEnabled(key in always)
        if self._current_state is None:
            return
        status = self._current_state.status
        visible_for = self._presenter.visible_actions(status)
        enable_for = visible_for
        for key in visible_for:
            buttons[key].setVisible(True)
        for key in enable_for:
            buttons[key].setEnabled(True)
        for key in visible_for:
            if not buttons[key].isEnabled():
                buttons[key].setToolTip("Aktion im aktuellen Kontext nicht zulässig.")

    def _open_details_from_table(self) -> None:
        if self._current_state is None:
            return
        self._details.setVisible(True)
        self._inline_notice.setText("Details geöffnet.")

    def _run_default_table_action(self) -> None:
        if self._current_state is None:
            return
        status = self._current_state.status
        priorities = self._presenter.default_artifact_priority(status)
        if priorities:
            self._open_readable_artifact(priorities)
        else:
            self._open_details_from_table()

    def _open_readable_artifact(self, preferred_types: list[ArtifactType]) -> None:
        for artifact_type in preferred_types:
            if self._open_artifact(artifact_type):
                self._inline_notice.setText(f"Standardaktion ausgeführt: {artifact_type.value} geöffnet.")
                return
        self._open_details_from_table()
        self._inline_notice.setText("Keine lesbare Datei gefunden. Details wurden geöffnet.")

    def _toggle_details(self) -> None:
        self._details.setVisible(not self._details.isVisible())

    def _refresh_details(self) -> None:
        if self._current_state is None:
            return
        state = self._state_from_selection()
        header = self._pool.get_header(state.document_id)
        self._fill_two_col_table(
            self._tab_overview,
            [
                ("Dokumentenkennung", state.document_id),
                ("Version", str(state.version)),
                ("Titel", state.title or ""),
                ("Status", state.status.value),
                ("Owner", str(state.owner_user_id or "-")),
                ("Workflow aktiv", "Ja" if state.workflow_active else "Nein"),
                ("Dokumenttyp", state.doc_type.value),
                ("Kontrollklasse", state.control_class.value),
                ("Workflowprofil", state.workflow_profile_id or "-"),
                ("Department", str(getattr(header, "department", "") or "-")),
                ("Standort", str(getattr(header, "site", "") or "-")),
                ("Regulatory Scope", str(getattr(header, "regulatory_scope", "") or "-")),
            ],
        )
        self._fill_two_col_table(
            self._tab_workflow,
            [
                ("Editoren", ", ".join(sorted(state.assignments.editors)) or "-"),
                ("Pruefer", ", ".join(sorted(state.assignments.reviewers)) or "-"),
                ("Freigeber", ", ".join(sorted(state.assignments.approvers)) or "-"),
                ("Naechster Schritt", "Aktionen sind statusabhaengig in der Aktionsleiste freigeschaltet."),
            ],
        )
        self._fill_history_table(
            [
                (
                    str(state.last_event_at or "-"),
                    "Letztes Event",
                    str(state.last_actor_user_id or "-"),
                    str(state.last_event_id or "-"),
                    "",
                ),
                (str(state.review_completed_at or "-"), "Pruefung abgeschlossen", str(state.review_completed_by or "-"), "", ""),
                (
                    str(state.approval_completed_at or "-"),
                    "Freigabe abgeschlossen",
                    str(state.approval_completed_by or "-"),
                    "",
                    "",
                ),
                (str(state.released_at or "-"), "Freigegeben", str(state.last_actor_user_id or "-"), "", ""),
                (str(state.archived_at or "-"), "Archiviert", str(state.archived_by or "-"), "", ""),
            ],
        )
        state_key = f"{state.document_id}:{state.version}"
        old_event = self._seen_event_ids.get(state_key)
        new_event = state.last_event_id
        if old_event is not None and old_event != new_event:
            self._detail_tabs.setTabText(self._history_tab_index, "Verlauf *")
            self._history_notice.setText("Neuer Statuswechsel erkannt - Verlauf prüfen.")
        else:
            self._detail_tabs.setTabText(self._history_tab_index, "Verlauf")
            self._history_notice.setText("Verlauf ohne neue Änderungen.")
        self._seen_event_ids[state_key] = new_event
        self._title.setText(state.title or "")
        self._description.setText(state.description or "")
        self._profile.setText(state.workflow_profile_id or "")
        if header is not None:
            self._department.setText(header.department or "")
            self._site.setText(header.site or "")
            self._regulatory_scope.setText(header.regulatory_scope or "")

    def _new_import(self) -> None:
        try:
            users = self._um.list_users()
            user = self._um.get_current_user()
            default_owner = user.user_id if user is not None else ""
            dlg = DocumentCreateWizard([u.user_id for u in users], default_owner, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            data = dlg.payload()
            if not data.document_id:
                raise RuntimeError("Dokumentenkennung ist erforderlich")
            version = 1
            created = self._wf.create_document_version(
                data.document_id,
                version,
                owner_user_id=data.owner_user_id or default_owner or None,
                title=data.title,
                description=data.description or None,
                doc_type=data.doc_type,
                control_class=ControlClass.CONTROLLED,
                workflow_profile_id=data.workflow_profile_id,
            )
            self._append("WIZARD_DRAFT", created)
            if not dlg.create_draft_only():
                user_obj, role = self._current_user_role()
                if data.mode == "template":
                    self._append(
                        "WIZARD_TEMPLATE",
                        self._wf.create_from_template(
                            data.document_id,
                            version,
                            Path(data.source_path),
                            actor_user_id=user_obj.user_id,
                            actor_role=role,
                        ),
                    )
                elif data.mode == "docx":
                    self._append(
                        "WIZARD_IMPORT_DOCX",
                        self._wf.import_existing_docx(
                            data.document_id,
                            version,
                            Path(data.source_path),
                            actor_user_id=user_obj.user_id,
                            actor_role=role,
                        ),
                    )
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc, critical=True)

    def _build_sign_request_or_none(self):
        if not self._sign_form.has_input():
            return None
        user, _ = self._current_user_role()
        return self._sign_form.build_request(
            signer_user=user.username,
            reason="pyqt_documents_workflow",
        )

    def _edit_docx(self) -> None:
        try:
            if not self._open_artifact(ArtifactType.SOURCE_DOCX):
                raise RuntimeError("Kein lokaler DOCX-Pfad im Artefakt verfuegbar")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc, critical=True)

    def _start_workflow(self) -> None:
        try:
            user, role = self._current_user_role()
            state = self._state_from_selection()
            wizard = WorkflowStartWizard(self._profile.text().strip() or state.workflow_profile_id, self)
            if wizard.exec() != QDialog.DialogCode.Accepted:
                return
            cfg = wizard.payload()
            profile = self._docs_service.get_profile(cfg.profile_id)
            desired_editors = parse_csv_set(cfg.editors_csv) if cfg.editors_csv else set(state.assignments.editors)
            desired_reviewers = parse_csv_set(cfg.reviewers_csv) if cfg.reviewers_csv else set(state.assignments.reviewers)
            desired_approvers = parse_csv_set(cfg.approvers_csv) if cfg.approvers_csv else set(state.assignments.approvers)
            if (
                desired_editors != set(state.assignments.editors)
                or desired_reviewers != set(state.assignments.reviewers)
                or desired_approvers != set(state.assignments.approvers)
            ):
                state = self._wf.assign_workflow_roles(
                    state,
                    editors=desired_editors,
                    reviewers=desired_reviewers,
                    approvers=desired_approvers,
                    actor_user_id=user.user_id,
                    actor_role=role,
                )
                self._append("ROLLEN_GESPEICHERT", state)
            payload = self._wf.start_workflow(state, profile, actor_user_id=user.user_id, actor_role=role)
            self._append("WORKFLOW_GESTARTET", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc, critical=True)

    def _complete_editing(self) -> None:
        try:
            user, role = self._current_user_role()
            payload = self._wf.complete_editing(
                self._state_from_selection(),
                sign_request=self._build_sign_request_or_none(),
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("PHASE_ABGESCHLOSSEN", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _abort_workflow(self) -> None:
        try:
            dlg = RejectReasonDialog("Workflow abbrechen", "Grund", self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            user, role = self._current_user_role()
            payload = self._wf.abort_workflow(
                self._state_from_selection(),
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append(
                "WORKFLOW_ABGEBROCHEN",
                {"result": payload, "dialog_reason": dlg.reason()},
            )
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _review_accept(self) -> None:
        try:
            user, role = self._current_user_role()
            payload = self._wf.accept_review(self._state_from_selection(), user.user_id, actor_role=role)
            self._append("PRUEFUNG_ANGENOMMEN", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _review_reject(self) -> None:
        try:
            dlg = RejectReasonDialog("Pruefung ablehnen", "Ablehnungsgrund", self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            user, role = self._current_user_role()
            payload = self._wf.reject_review(self._state_from_selection(), user.user_id, dlg.reason(), actor_role=role)
            self._append("PRUEFUNG_ABGELEHNT", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _approval_accept(self) -> None:
        try:
            confirm = QMessageBox.question(
                self,
                "Freigabe annehmen",
                "Freigabe wirklich annehmen? Optional wird die konfigurierte Signaturanforderung ausgefuehrt.",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            user, role = self._current_user_role()
            payload = self._wf.accept_approval(
                self._state_from_selection(),
                user.user_id,
                sign_request=self._build_sign_request_or_none(),
                actor_role=role,
            )
            self._append("FREIGABE_ANGENOMMEN", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _approval_reject(self) -> None:
        try:
            dlg = RejectReasonDialog("Freigabe ablehnen", "Ablehnungsgrund", self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            user, role = self._current_user_role()
            payload = self._wf.reject_approval(self._state_from_selection(), user.user_id, dlg.reason(), actor_role=role)
            self._append("FREIGABE_ABGELEHNT", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _archive_approved(self) -> None:
        try:
            user, role = self._current_user_role()
            payload = self._wf.archive_approved(self._state_from_selection(), role, actor_user_id=user.user_id)
            self._append("ARCHIVIERT", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _assign_roles(self) -> None:
        try:
            user, role = self._current_user_role()
            payload = self._wf.assign_workflow_roles(
                self._state_from_selection(),
                editors=parse_csv_set(self._editors.text()),
                reviewers=parse_csv_set(self._reviewers.text()),
                approvers=parse_csv_set(self._approvers.text()),
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("ROLLEN_GESPEICHERT", payload)
            self._refresh_details()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _update_metadata(self) -> None:
        try:
            user, role = self._current_user_role()
            valid_until = datetime.fromisoformat(self._valid_until.text().strip()) if self._valid_until.text().strip() else None
            next_review = datetime.fromisoformat(self._next_review.text().strip()) if self._next_review.text().strip() else None
            custom_fields = json.loads(self._custom_fields.text().strip() or "{}")
            payload = self._wf.update_version_metadata(
                self._state_from_selection(),
                title=self._title.text().strip() or None,
                description=self._description.text().strip() or None,
                valid_until=valid_until,
                next_review_at=next_review,
                custom_fields=custom_fields,
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("METADATEN_GESPEICHERT", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _update_header(self) -> None:
        try:
            user, role = self._current_user_role()
            state = self._state_from_selection()
            payload = self._wf.update_document_header(
                state.document_id,
                doc_type=self._doc_type.currentData(),
                control_class=self._control_class.currentData(),
                workflow_profile_id=self._profile.text().strip() or None,
                department=self._department.text().strip() or None,
                site=self._site.text().strip() or None,
                regulatory_scope=self._regulatory_scope.text().strip() or None,
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("HEADER_GESPEICHERT", payload)
            self._refresh_details()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _extend_validity(self) -> None:
        try:
            payload = self._wf.extend_annual_validity(
                self._state_from_selection(),
                signature_present=self._extend_signature.isChecked(),
            )
            self._append("JAHRESVERLAENGERUNG", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _new_version_after_archive(self) -> None:
        try:
            payload = self._wf.create_new_version_after_archive(
                self._state_from_selection(),
                int(self._next_version.text().strip()),
            )
            self._append("NEUE_VERSION_NACH_ARCHIV", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _open_artifact(self, artifact_type: ArtifactType) -> bool:
        try:
            state = self._state_from_selection()
            artifacts = self._pool.list_artifacts(state.document_id, state.version)
            for artifact in artifacts:
                if artifact.artifact_type != artifact_type:
                    continue
                for path in self._resolve_openable_artifact_paths(artifact):
                    if not path.exists():
                        continue
                    if hasattr(os, "startfile"):
                        os.startfile(str(path))  # type: ignore[attr-defined]
                        self._append("ARTEFAKT_GEOEFFNET", {"type": artifact_type.value, "path": str(path)})
                        return True
            raise RuntimeError(f"Kein lokal oeffenbarer Pfad fuer {artifact_type.value} gefunden")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)
            return False

    def _resolve_artifacts_root(self) -> Path:
        if not self._container.has_port("settings_service"):
            return self._app_home / "storage" / "documents" / "artifacts"
        settings_service = self._container.get_port("settings_service")
        docs_settings = settings_service.get_module_settings("documents")
        raw_root = docs_settings.get("artifacts_root", "storage/documents/artifacts")
        root = Path(raw_root)
        if root.is_absolute():
            return root
        return self._app_home / root

    def _resolve_openable_artifact_paths(self, artifact) -> list[Path]:
        candidates: list[Path] = []
        for key in ("absolute_path", "file_path", "path"):
            value = artifact.metadata.get(key)
            if not value:
                continue
            raw = Path(value)
            candidates.append(raw if raw.is_absolute() else self._app_home / raw)
        storage_path = self._artifacts_root / artifact.storage_key
        candidates.append(storage_path)
        unique: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            token = str(candidate)
            if token in seen:
                continue
            seen.add(token)
            unique.append(candidate)
        return unique


def _build(container: RuntimeContainer) -> QWidget:
    return DocumentsWorkflowWidget(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="documents.workflow",
            module_id="documents",
            title="Dokumentenlenkung",
            sort_order=10,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
