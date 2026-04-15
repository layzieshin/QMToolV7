from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QPixmap
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
    QTableView,
    QTableWidget,
    QTabWidget,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import parse_csv_set, role_to_system_role
from interfaces.pyqt.widgets.document_create_wizard import DocumentCreateWizard
from interfaces.pyqt.widgets.workflow_profile_wizard import WorkflowProfileWizardDialog
from interfaces.pyqt.widgets.reject_reason_dialog import RejectReasonDialog
from interfaces.pyqt.widgets.drawer_panel import DrawerPanel
from interfaces.pyqt.widgets.table_helpers import configure_readonly_table, fill_table
from interfaces.pyqt.widgets.workflow_start_wizard import WorkflowStartWizard
from interfaces.pyqt.widgets.signature_placement_dialog import SignaturePlacementDialog
from interfaces.pyqt.presenters.documents_workflow_filter_presenter import DocumentsWorkflowFilterPresenter
from interfaces.pyqt.presenters.documents_workflow_presenter import DocumentsWorkflowPresenter
from interfaces.pyqt.registry.contribution import QtModuleContribution
from modules.documents.contracts import ArtifactType, ControlClass, DocumentStatus, DocumentType, RejectionReason, SystemRole, WorkflowProfile
from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput
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
        self._signature_api = container.get_port("signature_api") if container.has_port("signature_api") else None
        self._audit_logger = container.get_port("audit_logger") if container.has_port("audit_logger") else None
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
        self._extend_signature = QCheckBox("Signatur fuer Jahresverlaengerung liegt vor")
        self._extend_signature.setChecked(False)

        self._tab_overview = self._new_readonly_table(["Feld", "Wert"])
        self._tab_roles = self._new_readonly_table(["Aspekt", "Wert"])
        self._tab_comments = QPlainTextEdit()
        self._tab_comments.setReadOnly(True)
        self._tab_comments.setPlainText("Kommentare werden vorbereitet. Datenanbindung folgt ueber vorhandene Ports.")
        self._tab_history = self._new_readonly_table(["Zeit", "Aktion", "Benutzer", "Ergebnis", "Begruendung"])
        self._history_notice = QLabel("Verlauf ohne neue Änderungen.")
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._inline_notice = QLabel("")
        self._inline_notice.setWordWrap(True)

        self._metadata_inputs = [
            self._title,
            self._description,
            self._doc_type,
            self._control_class,
            self._profile,
            self._department,
            self._site,
            self._regulatory_scope,
            self._valid_until,
            self._next_review,
            self._custom_fields,
        ]
        self._role_inputs = [self._editors, self._reviewers, self._approvers]
        self._metadata_buttons: list[QPushButton] = []
        self._roles_buttons: list[QPushButton] = []

        self._top_actions = self._build_top_filter_bar()
        self._workflow_actions = self._build_workflow_action_bar()
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.addLayout(self._top_actions["layout"])
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Status"))
        filters.addWidget(self._status_filter)
        filters.addWidget(QLabel("Scope"))
        filters.addWidget(self._scope_filter)
        filters.addStretch(1)
        center_layout.addLayout(filters)
        center_layout.addWidget(self._inline_notice)
        center_layout.addWidget(self._table, stretch=1)
        center_layout.addWidget(QLabel("Ergebnis / Fehler"))
        center_layout.addWidget(self._out, stretch=1)
        center_layout.addLayout(self._workflow_actions["layout"])

        self._details = self._build_detail_drawer()
        self._details_toggle = self._details.toggle_button()
        self._details_toggle.setText("Details")
        self._details_toggle.setMinimumWidth(36)
        self._details_toggle.setMaximumWidth(44)
        self._details_toggle.setStyleSheet("background-color: #666666; color: white; font-weight: bold; padding: 5px;")
        self._details_toggle.setToolTip("Details ein-/ausblenden")

        content_row = QHBoxLayout()
        content_row.addWidget(center, stretch=4)
        content_row.addWidget(self._details_toggle)
        content_row.addWidget(self._details, stretch=3)
        self._set_details_open(False)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Dokumentenlenkung mit dreiteiligem Aufbau: Filterbereich oben, Dokumentenanzeige in der Mitte, Workflowsteuerung unten."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addLayout(content_row, stretch=1)

        self._status_filter.currentIndexChanged.connect(lambda _i: self._reload_table())
        self._scope_filter.currentIndexChanged.connect(lambda _i: self._reload_table())
        self._scope_filter.setCurrentIndex(self._scope_filter.findData("tasks"))
        self._apply_table_density()
        self._reload_table()
        self._apply_editor_permissions()
        self._update_action_visibility()

    def _build_top_filter_bar(self) -> dict[str, object]:
        row = QHBoxLayout()
        buttons: dict[str, QPushButton] = {}
        for key, label, handler in [
            ("refresh", "Aktualisieren", self._reload_table),
            ("filter_advanced", "Erweiterter Filter", self._open_advanced_filter),
            ("filter", "Filter anwenden", self._reload_table),
            ("profile_manager", "Workflowprofil-Manager", self._open_workflow_profile_manager),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            buttons[key] = btn
            row.addWidget(btn)
        row.addStretch(1)
        return {"layout": row, "buttons": buttons}

    def _build_workflow_action_bar(self) -> dict[str, object]:
        row = QHBoxLayout()
        buttons: dict[str, QPushButton] = {}
        for key, label, handler in [
            ("new", "Neu / Import", self._new_import),
            ("start", "Workflow starten", self._start_workflow),
            ("abort", "Workflow abbrechen", self._abort_workflow),
            ("edit", "Oeffnen / Bearbeiten", self._edit_docx),
            ("complete", "Bearbeitung annehmen", self._complete_editing),
            ("review_accept", "Pruefung annehmen", self._review_accept),
            ("review_reject", "Pruefung ablehnen", self._review_reject),
            ("approval_accept", "Freigabe annehmen", self._approval_accept),
            ("approval_reject", "Freigabe ablehnen", self._approval_reject),
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

    def _build_detail_drawer(self) -> DrawerPanel:
        panel = DrawerPanel("Details")
        content = QWidget()
        layout = QVBoxLayout(content)
        self._detail_tabs = QTabWidget()
        self._detail_tabs.addTab(self._tab_overview, "Ueberblick")
        self._detail_tabs.addTab(self._build_metadata_tab(), "Metadaten")
        self._detail_tabs.addTab(self._build_roles_tab(), "Rollen")
        self._detail_tabs.addTab(self._tab_comments, "Kommentare")
        self._history_tab_index = self._detail_tabs.addTab(self._tab_history, "Verlauf")
        self._detail_tabs.addTab(self._build_extension_tab(), "Verlaengerung")
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
        self._metadata_buttons.extend([btn_meta, btn_header])
        row.addWidget(btn_meta)
        row.addWidget(btn_header)
        row.addStretch(1)
        layout.addLayout(row)
        return tab

    def _build_roles_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        assignments = QFormLayout()
        assignments.addRow("Editoren CSV", self._editors)
        assignments.addRow("Pruefer CSV", self._reviewers)
        assignments.addRow("Freigeber CSV", self._approvers)
        layout.addLayout(assignments)
        row = QHBoxLayout()
        btn_roles = QPushButton("Rollen speichern")
        btn_roles.clicked.connect(self._assign_roles)
        self._roles_buttons.append(btn_roles)
        row.addWidget(btn_roles)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(self._tab_roles, stretch=1)
        return tab

    def _build_extension_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        form.addRow("Naechste Version", self._next_version)
        layout.addLayout(form)
        row = QHBoxLayout()
        for label, handler in [
            ("Verlaengern (mit Signatur)", self._extend_validity),
            ("Neue Version nach Archiv", self._new_version_after_archive),
        ]:
            b = QPushButton(label)
            b.clicked.connect(handler)
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(QLabel("Verlaengerung und Folgeschritte fuer archivierte Versionen. Gueltigkeitsverlängerung erfordert Signatur und erhöht das Review-Datum um 1 Jahr."))
        return tab

    @staticmethod
    def _format_dt(dt: object) -> str:
        """Format a datetime to German locale string, returns '-' for None."""
        if dt is None:
            return "-"
        try:
            return dt.strftime("%d.%m.%Y %H:%M")  # type: ignore[union-attr]
        except Exception:
            return str(dt)

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

    def _audit(self, *, action: str, actor: str, target: str, result: str, reason: str = "") -> None:
        emit = getattr(self._audit_logger, "emit", None) if self._audit_logger is not None else None
        if callable(emit):
            emit(action=action, actor=actor, target=target, result=result, reason=reason)

    def _set_details_open(self, open_state: bool) -> None:
        self._details.set_open(open_state)

    def _is_qmb(self) -> bool:
        user = self._um.get_current_user()
        return bool(user and role_to_system_role(user.role) == SystemRole.QMB)

    def _apply_editor_permissions(self) -> None:
        can_edit = self._is_qmb()
        self._doc_id.setReadOnly(True)
        self._version.setReadOnly(True)
        for widget in self._metadata_inputs:
            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(not can_edit)
            else:
                widget.setEnabled(can_edit)
        for widget in self._role_inputs:
            widget.setReadOnly(not can_edit)
        for button in self._metadata_buttons + self._roles_buttons:
            button.setVisible(can_edit)
            button.setEnabled(can_edit)

    def _show_error(self, exc: Exception, *, critical: bool = False) -> None:
        if critical:
            QMessageBox.warning(self, "Dokumentenlenkung", str(exc))
        self._inline_notice.setText(f"Warnung: {exc}")
        self._append("ERROR", {"message": str(exc)})

    def _apply_table_density(self) -> None:
        self._table.verticalHeader().setDefaultSectionSize(24)
        self._inline_notice.setText("Tabellendichte aktiv: Kompakt")

    def _is_profile_manager_allowed(self) -> bool:
        user = self._um.get_current_user()
        if user is None:
            return False
        role = role_to_system_role(user.role)
        if role in (SystemRole.ADMIN, SystemRole.QMB):
            return True
        if self._current_state is None:
            return False
        return str(self._current_state.owner_user_id or "") == str(user.user_id)

    def _profiles_file_path(self) -> Path:
        if not self._container.has_port("settings_service"):
            return self._app_home / "modules" / "documents" / "workflow_profiles.json"
        cfg = self._container.get_port("settings_service").get_module_settings("documents")
        raw = str(cfg.get("profiles_file", "modules/documents/workflow_profiles.json")).strip()
        path = Path(raw)
        return path if path.is_absolute() else self._app_home / path

    def _open_workflow_profile_manager(self) -> None:
        try:
            if not self._is_profile_manager_allowed():
                raise RuntimeError("Workflowprofil-Manager ist nur fuer Admin, QMB oder Dokumenteneigner verfuegbar")
            dialog = WorkflowProfileWizardDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            payload = dialog.payload()
            if not payload.profile_id:
                raise RuntimeError("Profil-ID ist erforderlich")
            file_path = self._profiles_file_path()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"profiles": []}
            if file_path.exists():
                data = json.loads(file_path.read_text(encoding="utf-8"))
            profiles = list(data.get("profiles", []))
            profiles = [p for p in profiles if str(p.get("profile_id", "")) != payload.profile_id]
            profiles.append(payload.as_json_dict())
            data["profiles"] = profiles
            file_path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
            self._append("WORKFLOWPROFIL_GESPEICHERT", {"profile_id": payload.profile_id, "path": str(file_path)})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc, critical=True)

    def _available_profiles_for_control_class(self, control_class: ControlClass) -> list[str]:
        try:
            file_path = self._profiles_file_path()
            payload = json.loads(file_path.read_text(encoding="utf-8")) if file_path.exists() else {"profiles": []}
            profiles = []
            for item in payload.get("profiles", []):
                if str(item.get("control_class", "")).strip() == control_class.value:
                    profile_id = str(item.get("profile_id", "")).strip()
                    if profile_id:
                        profiles.append(profile_id)
            return sorted(set(profiles))
        except Exception:
            return []

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
            self._update_action_visibility()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_table_selected(self) -> None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            self._current_state = None
            self._set_details_open(False)
            self._detail_tabs.setCurrentIndex(0)
            self._update_action_visibility()
            return
        self._current_state = self._model._rows[selected[0].row()]
        self._doc_id.setText(self._current_state.document_id)
        self._version.setText(str(self._current_state.version))
        self._refresh_details()
        self._update_action_visibility()

    def _update_action_visibility(self) -> None:
        workflow_buttons = self._workflow_actions["buttons"]
        user = self._um.get_current_user()
        user_id = str(user.user_id) if user is not None else None
        user_role = role_to_system_role(user.role) if user is not None else None
        visible_for = self._presenter.visible_actions_for_context(self._current_state, user_id=user_id, user_role=user_role)
        for key, button in workflow_buttons.items():
            allowed = key in visible_for
            button.setVisible(allowed)
            button.setEnabled(allowed)
            if not allowed:
                button.setToolTip("")

        top_buttons = self._top_actions["buttons"]
        top_buttons["profile_manager"].setVisible(self._is_profile_manager_allowed())
        top_buttons["profile_manager"].setEnabled(self._is_profile_manager_allowed())

        self._apply_editor_permissions()

    def _open_details_from_table(self) -> None:
        if self._current_state is None:
            return
        self._set_details_open(True)
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
            self._tab_roles,
            [
                ("Editoren", ", ".join(sorted(state.assignments.editors)) or "-"),
                ("Pruefer", ", ".join(sorted(state.assignments.reviewers)) or "-"),
                ("Freigeber", ", ".join(sorted(state.assignments.approvers)) or "-"),
                ("Naechster Schritt", "Workflowsteuerung unten blendet Aktionen status- und rollenabhaengig ein."),
            ],
        )
        # Baue Verlauf aus echten Zustandsänderungen
        history_rows: list[tuple[str, str, str, str, str]] = []
        if state.released_at:
            history_rows.append((
                str(state.released_at.strftime("%Y-%m-%d %H:%M:%S") if state.released_at else "-"),
                "Freigegeben",
                str(state.last_actor_user_id or "-"),
                "APPROVED",
                ""
            ))
        if state.approval_completed_at:
            history_rows.append((
                str(state.approval_completed_at.strftime("%Y-%m-%d %H:%M:%S")),
                "Freigabe abgeschlossen",
                str(state.approval_completed_by or "-"),
                "IN_APPROVAL->APPROVED",
                ""
            ))
        if state.review_completed_at:
            history_rows.append((
                str(state.review_completed_at.strftime("%Y-%m-%d %H:%M:%S")),
                "Pruefung abgeschlossen",
                str(state.review_completed_by or "-"),
                "IN_PROGRESS->IN_REVIEW",
                ""
            ))
        if state.last_event_at and state.last_event_id:
            history_rows.append((
                str(state.last_event_at.strftime("%Y-%m-%d %H:%M:%S")),
                "Letzte Aenderung",
                str(state.last_actor_user_id or "-"),
                str(state.last_event_id or "-"),
                f"Extension Count: {state.extension_count}" if state.extension_count > 0 else ""
            ))
        if state.archived_at:
            history_rows.append((
                str(state.archived_at.strftime("%Y-%m-%d %H:%M:%S")),
                "Archiviert",
                str(state.archived_by or "-"),
                "APPROVED->ARCHIVED",
                ""
            ))
        
        if history_rows:
            self._fill_history_table(history_rows)
        else:
            # Fallback wenn keine Events vorhanden sind
            self._fill_history_table([
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
            ])
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
        self._editors.setText(", ".join(sorted(state.assignments.editors)))
        self._reviewers.setText(", ".join(sorted(state.assignments.reviewers)))
        self._approvers.setText(", ".join(sorted(state.assignments.approvers)))
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

    def _build_sign_request_or_none(self, transition: str) -> SignRequest | None:
        state = self._state_from_selection()
        profile = state.workflow_profile
        if profile is None or transition not in set(profile.signature_required_transitions):
            return None
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")

        input_path = self._find_pdf_for_signature()
        if input_path is None:
            raise RuntimeError("Fuer den signaturpflichtigen Uebergang wurde keine PDF-Datei gefunden")

        signature_png = self._export_active_signature_png(str(user.user_id))
        signature_pixmap = QPixmap(str(signature_png))
        if signature_pixmap.isNull():
            raise RuntimeError("Aktive Signatur konnte nicht als Vorschau geladen werden")

        default_placement = SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=140.0)
        default_layout = self._resolved_runtime_layout(
            LabelLayoutInput(show_signature=True, show_name=True, show_date=True),
            user,
        )
        self._audit(
            action="documents.workflow.signature.placement.opened",
            actor=str(user.user_id),
            target=f"{state.document_id}:{state.version}",
            result="ok",
            reason=transition,
        )
        place_dialog = SignaturePlacementDialog(
            input_pdf=input_path,
            placement=default_placement,
            layout=default_layout,
            signature_pixmap=signature_pixmap,
            template_save_callback=self._save_signature_template_from_workflow,
            parent=self,
        )
        place_dialog.showFullScreen()
        if place_dialog.exec() != QDialog.DialogCode.Accepted:
            self._audit(
                action="documents.workflow.signature.placement.cancelled",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="cancelled",
                reason=transition,
            )
            return None
        placement = place_dialog.placement()
        layout_result = place_dialog.layout_result()

        pwd_dialog = QDialog(self)
        pwd_dialog.setWindowTitle("Signatur fuer Uebergang erforderlich")
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        form = QFormLayout()
        form.addRow("Signatur-Passwort", password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(pwd_dialog.accept)
        buttons.rejected.connect(pwd_dialog.reject)
        layout = QVBoxLayout(pwd_dialog)
        layout.addWidget(
            QLabel(
                "Dieser Workflowschritt erfordert eine Signatur. Es wird automatisch eine visuelle Markierung mit Namens-/Datumslabel gesetzt."
            )
        )
        layout.addLayout(form)
        layout.addWidget(buttons)
        if pwd_dialog.exec() != QDialog.DialogCode.Accepted:
            self._audit(
                action="documents.workflow.signature.password.cancelled",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="cancelled",
                reason=transition,
            )
            return None

        safe_title = self._safe_document_title_token(state.title)
        output_name = f"{state.document_id}_{safe_title}_signed.pdf"
        output_path = Path(tempfile.gettempdir()) / output_name
        return SignRequest(
            input_pdf=input_path,
            output_pdf=output_path,
            signature_png=signature_png,
            placement=placement,
            layout=layout_result,
            overwrite_output=True,
            dry_run=False,
            sign_mode="visual",
            signer_user=str(user.user_id),
            password=password.text().strip() or None,
            reason="documents_workflow_transition",
        )

    def _save_signature_template_from_workflow(
        self,
        name: str,
        placement: SignaturePlacementInput,
        layout: LabelLayoutInput,
    ) -> None:
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        create = getattr(self._signature_api, "create_user_signature_template", None)
        get_active = getattr(self._signature_api, "get_active_signature_asset_id", None)
        if not callable(create) or not callable(get_active):
            raise RuntimeError("Signatur-API unterstuetzt Vorlagen nicht")
        template_name = name.strip()
        if not template_name:
            raise RuntimeError("Bitte einen Vorlagennamen eingeben")
        signature_asset_id = get_active(user.user_id)
        if layout.show_signature and not signature_asset_id:
            raise RuntimeError("Keine aktive Signatur vorhanden. Bitte zuerst eine Signatur aktivieren.")
        create(
            owner_user_id=user.user_id,
            name=template_name,
            placement=placement,
            layout=replace(layout, name_text=None, date_text=None),
            signature_asset_id=signature_asset_id,
            scope="user",
        )
        self._audit(
            action="documents.workflow.signature.template.saved",
            actor=str(user.user_id),
            target=f"{self._state_from_selection().document_id}:{self._state_from_selection().version}",
            result="ok",
            reason=template_name,
        )

    def _display_name(self, user) -> str:
        first = (getattr(user, "first_name", None) or "").strip()
        last = (getattr(user, "last_name", None) or "").strip()
        if first and last:
            return f"{first}, {last}"
        if first:
            return first
        if last:
            return last
        return (getattr(user, "display_name", None) or getattr(user, "username", None) or str(user.user_id)).strip()

    def _resolved_runtime_layout(self, layout: LabelLayoutInput, user) -> LabelLayoutInput:
        display_name = self._display_name(user)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        seeded = replace(
            layout,
            name_text=display_name if layout.show_name else None,
            date_text=timestamp if layout.show_date else None,
        )
        resolver = getattr(self._signature_api, "resolve_runtime_layout", None)
        if callable(resolver):
            return resolver(seeded, signer_user=display_name)
        return seeded

    def _export_active_signature_png(self, user_id: str) -> Path:
        get_active = getattr(self._signature_api, "get_active_signature_asset_id", None)
        export = getattr(self._signature_api, "export_active_signature", None)
        if not callable(get_active) or not callable(export):
            raise RuntimeError("Signatur-API unterstuetzt aktive Signaturvorschau nicht")
        active_asset_id = get_active(user_id)
        if not active_asset_id:
            raise RuntimeError("Keine aktive Signatur vorhanden. Bitte zuerst im Signaturmodul hinterlegen.")
        target = Path(tempfile.gettempdir()) / f"qmtool-signature-{uuid4().hex}.png"
        exported = export(user_id, target)
        if not exported.exists() or exported.stat().st_size == 0:
            raise RuntimeError("Aktive Signatur konnte nicht exportiert werden")
        return exported

    @staticmethod
    def _safe_document_title_token(title: str | None) -> str:
        token = (title or "").strip().replace(" ", "_")
        token = (
            token.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("Ä", "Ae")
            .replace("Ö", "Oe")
            .replace("Ü", "Ue")
            .replace("ß", "ss")
        )
        safe = "".join(ch for ch in token if ch.isalnum() or ch in ("_", "-")).strip("_-")
        return safe or "Dokument"

    def _require_signature_call(self, sign_request: SignRequest) -> None:
        sign = getattr(self._signature_api, "sign_with_fixed_position", None)
        if not callable(sign):
            raise RuntimeError("signature_api ist nicht verfuegbar oder unterstuetzt sign_with_fixed_position nicht")
        sign(sign_request)

    def _find_pdf_for_signature(self) -> Path | None:
        state = self._state_from_selection()
        artifacts = self._pool.list_artifacts(state.document_id, state.version)
        priorities = [ArtifactType.SIGNED_PDF, ArtifactType.RELEASED_PDF, ArtifactType.SOURCE_PDF]
        ordered_artifacts = sorted(artifacts, key=lambda artifact: 0 if getattr(artifact, "is_current", False) else 1)
        for artifact_type in priorities:
            for artifact in ordered_artifacts:
                if artifact.artifact_type != artifact_type:
                    continue
                for path in self._resolve_openable_artifact_paths(artifact):
                    if path.exists() and path.suffix.lower() == ".pdf":
                        return path
        
        # Fallback: Versuche SOURCE_DOCX zu PDF zu konvertieren
        conversion_errors: list[str] = []
        for artifact in ordered_artifacts:
            if artifact.artifact_type != ArtifactType.SOURCE_DOCX:
                continue
            for docx_path in self._resolve_openable_artifact_paths(artifact):
                if docx_path.exists() and docx_path.suffix.lower() == ".docx":
                    try:
                        converted = self._convert_docx_to_temp_pdf(docx_path)
                    except RuntimeError as exc:
                        conversion_errors.append(str(exc))
                        continue
                    if converted is not None:
                        return converted
        if conversion_errors:
            raise RuntimeError(conversion_errors[0])
        return None

    def _convert_docx_to_temp_pdf(self, docx_path: Path) -> Path | None:
        """Convert DOCX to a temporary PDF without markup (tracked changes/comments)."""
        if os.name != "nt":
            raise RuntimeError("DOCX-zu-PDF Fallback wird nur unter Windows unterstuetzt")
        safe_stem = self._safe_document_title_token(docx_path.stem)
        output_name = f"{safe_stem}_{uuid4().hex[:8]}.pdf"
        output_path = Path(tempfile.gettempdir()) / output_name
        try:
            import win32com.client  # type: ignore[import]

            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = False
            try:
                doc = word.Documents.Open(str(docx_path.resolve()))
                try:
                    # Alle Überarbeitungen annehmen, damit kein Markup im PDF erscheint
                    if doc.Revisions.Count > 0:
                        doc.Revisions.AcceptAll()
                    # wdFormatPDF=17, Item=0 (wdExportDocumentContent = kein Markup)
                    doc.ExportAsFixedFormat(
                        str(output_path.resolve()),
                        17,     # wdFormatPDF
                        False,  # OpenAfterExport
                        0,      # OptimizeFor: wdExportOptimizeForPrint
                        0,      # Range: wdExportAllDocument
                        1,      # From
                        1,      # To
                        0,      # Item: wdExportDocumentContent (ohne Markup)
                        True,   # IncludeDocProps
                        True,   # KeepIRM
                        0,      # CreateBookmarks: wdExportCreateNoBookmarks
                        True,   # DocStructureTags
                        True,   # BitmapMissingFonts
                        False,  # UseISO19005_1
                    )
                finally:
                    doc.Close(False)  # Ohne Speichern schließen
            finally:
                word.Quit()
        except ImportError:
            # Fallback: docx2pdf (kein Markup-Steuerung, aber besser als nichts)
            try:
                from docx2pdf import convert  # type: ignore[import]

                convert(str(docx_path), str(output_path))
            except ImportError:
                raise RuntimeError(
                    "Weder pywin32 noch docx2pdf verfuegbar. "
                    "Bitte installieren: pip install pywin32 (empfohlen) oder pip install docx2pdf"
                )
        except Exception as exc:
            raise RuntimeError(f"Fehler bei DOCX-zu-PDF Konvertierung: {exc}") from exc
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        raise RuntimeError(f"DOCX-zu-PDF Konvertierung fehlgeschlagen fuer {docx_path}")
    
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
            users = self._um.list_users()
            wizard = WorkflowStartWizard(
                self._profile.text().strip() or state.workflow_profile_id,
                profile_ids=self._available_profiles_for_control_class(state.control_class),
                available_user_ids=[u.user_id for u in users],
                current_editors=set(state.assignments.editors),
                current_reviewers=set(state.assignments.reviewers),
                current_approvers=set(state.assignments.approvers),
                parent=self,
            )
            if wizard.exec() != QDialog.DialogCode.Accepted:
                return
            cfg = wizard.payload()
            profile = self._docs_service.get_profile(cfg.profile_id)
            desired_editors = cfg.editors if cfg.editors else set(state.assignments.editors)
            desired_reviewers = cfg.reviewers if cfg.reviewers else set(state.assignments.reviewers)
            desired_approvers = cfg.approvers if cfg.approvers else set(state.assignments.approvers)
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
            state = self._state_from_selection()
            self._wf.ensure_source_pdf_for_signing(state, actor_user_id=user.user_id, actor_role=role)
            self._audit(
                action="documents.workflow.editing.prepare_pdf",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="ok",
                reason="complete_editing",
            )
            sign_request = self._build_sign_request_or_none("IN_PROGRESS->IN_REVIEW")
            if self._state_from_selection().workflow_profile and "IN_PROGRESS->IN_REVIEW" in set(
                self._state_from_selection().workflow_profile.signature_required_transitions
            ) and sign_request is None:
                self._inline_notice.setText("Signaturvorgang abgebrochen.")
                self._audit(
                    action="documents.workflow.editing.complete",
                    actor=str(user.user_id),
                    target=f"{state.document_id}:{state.version}",
                    result="cancelled",
                    reason="signature_cancelled",
                )
                return
            payload = self._wf.complete_editing(
                self._state_from_selection(),
                sign_request=sign_request,
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("PHASE_ABGESCHLOSSEN", payload)
            self._audit(
                action="documents.workflow.editing.complete",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="ok",
                reason="IN_PROGRESS->IN_REVIEW",
            )
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            try:
                state = self._state_from_selection()
                self._audit(
                    action="documents.workflow.editing.complete",
                    actor=str(getattr(user, "user_id", "system") if "user" in locals() else "system"),
                    target=f"{state.document_id}:{state.version}",
                    result="error",
                    reason=str(exc),
                )
            except Exception:  # noqa: BLE001
                pass
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
            sign_request = self._build_sign_request_or_none("IN_APPROVAL->APPROVED")
            if self._state_from_selection().workflow_profile and "IN_APPROVAL->APPROVED" in set(
                self._state_from_selection().workflow_profile.signature_required_transitions
            ) and sign_request is None:
                self._inline_notice.setText("Signaturvorgang abgebrochen.")
                return
            payload = self._wf.accept_approval(
                self._state_from_selection(),
                user.user_id,
                sign_request=sign_request,
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
            state = self._state_from_selection()
            user, _role = self._current_user_role()

            # Pruefe ob Verlaengerung moeglich ist.
            if state.status != DocumentStatus.APPROVED:
                raise RuntimeError("Verlaengerung ist nur im Status APPROVED moeglich")
            if state.extension_count >= 3:
                raise RuntimeError("Maximale Anzahl von Verlaengerungen (3) erreicht")

            # Fordere Signatur an fuer die Verlaengerung.
            input_path = self._find_pdf_for_signature()
            if input_path is None:
                raise RuntimeError("Keine PDF-Datei fuer Signatur gefunden. Bitte pruefen Sie die Artefakte.")

            signature_png = self._export_active_signature_png(str(user.user_id))
            signature_pixmap = QPixmap(str(signature_png))
            if signature_pixmap.isNull():
                raise RuntimeError("Aktive Signatur konnte nicht als Vorschau geladen werden")
            placement_dialog = SignaturePlacementDialog(
                input_pdf=input_path,
                placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=140.0),
                layout=self._resolved_runtime_layout(
                    LabelLayoutInput(show_signature=True, show_name=True, show_date=True),
                    user,
                ),
                signature_pixmap=signature_pixmap,
                parent=self,
            )
            placement_dialog.showFullScreen()
            if placement_dialog.exec() != QDialog.DialogCode.Accepted:
                self._inline_notice.setText("Verlaengerungsvorgang abgebrochen.")
                return
            placement = placement_dialog.placement()
            layout_result = placement_dialog.layout_result()

            # Passwortdialog fuer die Signatur.
            pwd_dialog = QDialog(self)
            pwd_dialog.setWindowTitle("Signatur fuer Verlaengerung erforderlich")
            password = QLineEdit()
            password.setEchoMode(QLineEdit.EchoMode.Password)
            form = QFormLayout()
            form.addRow("Signatur-Passwort", password)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(pwd_dialog.accept)
            buttons.rejected.connect(pwd_dialog.reject)
            layout = QVBoxLayout(pwd_dialog)
            layout.addWidget(QLabel("Diese Gueltigkeitsverlaengerung erfordert eine Signatur."))
            layout.addLayout(form)
            layout.addWidget(buttons)

            if pwd_dialog.exec() != QDialog.DialogCode.Accepted:
                self._inline_notice.setText("Verlaengerungsvorgang abgebrochen.")
                return

            # Erstelle SignRequest.
            safe_title = self._safe_document_title_token(state.title)
            output_name = f"{state.document_id}_{safe_title}_extended.pdf"
            output_path = Path(tempfile.gettempdir()) / output_name

            sign_request = SignRequest(
                input_pdf=input_path,
                output_pdf=output_path,
                signature_png=signature_png,
                placement=placement,
                layout=layout_result,
                overwrite_output=True,
                dry_run=False,
                sign_mode="visual",
                signer_user=str(user.user_id),
                password=password.text().strip() or None,
                reason="documents_extension_validity",
            )

            # Signiere die PDF. Bei fehlender API wird explizit abgebrochen.
            self._require_signature_call(sign_request)

            # Fuehre Verlaengerung nur nach erfolgreicher Signatur aus.
            payload, is_maxed = self._wf.extend_annual_validity(
                state,
                signature_present=True,
            )
            self._append("JAHRESVERLAENGERUNG", {
                "new_extension_count": payload.extension_count,
                "is_maxed": is_maxed,
                "next_review_at": str(payload.next_review_at)
            })
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
            candidate = raw if raw.is_absolute() else self._app_home / raw
            if self._is_allowed_artifact_path(candidate):
                candidates.append(candidate)
        storage_path = self._artifacts_root / artifact.storage_key
        if self._is_allowed_artifact_path(storage_path):
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

    def _is_allowed_artifact_path(self, candidate: Path) -> bool:
        try:
            resolved = candidate.resolve(strict=False)
            app_home = self._app_home.resolve(strict=False)
            artifacts_root = self._artifacts_root.resolve(strict=False)
            return resolved.is_relative_to(app_home) or resolved.is_relative_to(artifacts_root)
        except Exception:
            return False


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
