from __future__ import annotations

import json
import csv
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableView,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import parse_csv_set, role_to_system_role
from interfaces.pyqt.models.workflow_table_model import WorkflowTableModel
from interfaces.pyqt.presenters.documents_detail_presenter import DocumentsDetailPresenter
from interfaces.pyqt.presenters.documents_signature_ops import DocumentsSignatureOps
from interfaces.pyqt.sections.filter_bar import build_top_filter_bar, open_advanced_filter_dialog
from interfaces.pyqt.sections.action_bar import build_workflow_action_bar, update_action_visibility
from interfaces.pyqt.sections.detail_drawer import (
    new_readonly_table,
    build_metadata_tab,
    build_roles_tab,
    build_extension_tab,
    DetailDrawerBuilder,
)
from interfaces.pyqt.widgets.document_create_wizard import DocumentCreateWizard
from interfaces.pyqt.widgets.workflow_profile_wizard import WorkflowProfileWizardDialog
from interfaces.pyqt.widgets.reject_reason_dialog import RejectReasonDialog
from interfaces.pyqt.widgets.table_helpers import fill_table
from interfaces.pyqt.widgets.validity_extension_dialog import ValidityExtensionDialog
from interfaces.pyqt.widgets.workflow_start_wizard import WorkflowStartWizard
from interfaces.pyqt.workers import TableReloadResult, TableReloadWorker

from modules.documents.contracts import (
    ArtifactType,
    ControlClass,
    DocumentStatus,
    DocumentType,
    SystemRole,
    ValidityExtensionOutcome,
)
from interfaces.pyqt.presenters.documents_workflow_presenter import DocumentsWorkflowPresenter
from interfaces.pyqt.presenters.documents_workflow_filter_presenter import DocumentsWorkflowFilterPresenter
from qm_platform.runtime.container import RuntimeContainer


# --- _WorkflowTableModel extracted to interfaces/pyqt/models/workflow_table_model.py



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
        self._sig_ops = DocumentsSignatureOps(
            signature_api=self._signature_api,
            pool_api=self._pool,
            um_service=self._um,
            audit_logger=self._audit_logger,
            app_home=self._app_home,
            artifacts_root=self._artifacts_root,
        )
        self._current_state = None
        self._advanced_filters: dict[str, object] = {
            "owner_contains": "",
            "title_contains": "",
            "workflow_active": "all",
            "active_version": "all",
        }
        self._seen_event_ids: dict[str, str | None] = {}
        self._reload_thread: QThread | None = None
        self._reload_worker: TableReloadWorker | None = None
        self._reload_progress: QProgressDialog | None = None
        self._reload_cancelled = False
        self._last_change_export_dir: Path = self._app_home
        self._last_change_export_format: str = "json"

        self._status_filter = QComboBox()
        self._status_filter.addItem("Alle", "ALL")
        for status in DocumentStatus:
            self._status_filter.addItem(status.value, status)
        self._scope_filter = QComboBox()
        self._scope_filter.addItem("Alle", "all")
        self._scope_filter.addItem("Meine Dokumente", "mine")
        self._scope_filter.addItem("Meine Aufgaben", "tasks")
        self._model = WorkflowTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(1, self._table.horizontalHeader().ResizeMode.Stretch)
        self._table.selectionModel().selectionChanged.connect(self._on_table_selected)
        self._table.doubleClicked.connect(lambda _idx: self._run_default_table_action())
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._reload_table)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._run_default_table_action)

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
        self._extension_valid_from = QLabel("-")
        self._extension_valid_until = QLabel("-")
        self._extension_next_review = QLabel("-")
        self._extension_count = QLabel("0/3")
        self._extension_remaining_days = QLabel("-")

        self._tab_overview = new_readonly_table(["Feld", "Wert"])
        self._tab_roles = new_readonly_table(["Aspekt", "Wert"])
        self._tab_comments = QPlainTextEdit()
        self._tab_comments.setReadOnly(True)
        self._tab_comments.setPlainText("Keine Change Requests vorhanden.")
        self._export_change_requests_btn = QPushButton("Change Requests exportieren")
        self._export_change_requests_btn.clicked.connect(self._export_change_requests)
        self._comments_tab = QWidget()
        comments_layout = QVBoxLayout(self._comments_tab)
        comments_layout.addWidget(self._tab_comments, stretch=1)
        comments_layout.addWidget(self._export_change_requests_btn)
        self._tab_history = new_readonly_table(["Zeit", "Aktion", "Benutzer", "Ergebnis", "Begruendung"])
        self._history_notice = QLabel("Verlauf ohne neue Änderungen.")
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setVisible(False)
        self._toggle_output_btn = QPushButton("Protokoll anzeigen")
        self._toggle_output_btn.clicked.connect(self._toggle_output_visibility)
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

        self._top_actions = build_top_filter_bar(
            on_refresh=self._reload_table,
            on_advanced_filter=self._open_advanced_filter,
            on_apply_filter=self._reload_table,
            on_profile_manager=self._open_workflow_profile_manager,
        )
        self._workflow_actions = build_workflow_action_bar(
            on_new=self._new_import,
            on_start=self._start_workflow,
            on_abort=self._abort_workflow,
            on_edit=self._edit_docx,
            on_complete=self._complete_editing,
            on_review_accept=self._review_accept,
            on_review_reject=self._review_reject,
            on_approval_accept=self._approval_accept,
            on_approval_reject=self._approval_reject,
        )
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
        center_layout.addWidget(self._toggle_output_btn)
        center_layout.addWidget(self._out, stretch=1)
        center_layout.addLayout(self._workflow_actions["layout"])

        metadata_tab = build_metadata_tab(
            doc_id=self._doc_id, version=self._version, title=self._title,
            description=self._description, doc_type=self._doc_type,
            control_class=self._control_class, profile=self._profile,
            department=self._department, site=self._site,
            regulatory_scope=self._regulatory_scope, valid_until=self._valid_until,
            next_review=self._next_review, custom_fields=self._custom_fields,
            on_save_metadata=self._update_metadata, on_save_header=self._update_header, on_add_change_request=self._add_change_request,
            metadata_buttons=self._metadata_buttons,
        )
        roles_tab = build_roles_tab(
            editors=self._editors, reviewers=self._reviewers, approvers=self._approvers,
            tab_roles=self._tab_roles, on_save_roles=self._assign_roles,
            roles_buttons=self._roles_buttons,
        )
        extension_tab = build_extension_tab(
            next_version=self._next_version,
            valid_from_label=self._extension_valid_from,
            valid_until_label=self._extension_valid_until,
            next_review_label=self._extension_next_review,
            extension_count_label=self._extension_count,
            extension_remaining_label=self._extension_remaining_days,
            on_extend=self._extend_validity,
            on_new_version=self._new_version_after_archive,
        )
        self._details, self._detail_tabs, self._history_tab_index = DetailDrawerBuilder.build(
            tab_overview=self._tab_overview, tab_roles=self._tab_roles,
            tab_comments=self._comments_tab, tab_history=self._tab_history,
            history_notice=self._history_notice,
            metadata_tab=metadata_tab, roles_tab=roles_tab, extension_tab=extension_tab,
        )
        self._details_toggle = self._details.toggle_button()
        self._details_toggle.setText("Details")
        self._details_toggle.setMinimumWidth(52)
        self._details_toggle.setMinimumHeight(220)
        self._details_toggle.setStyleSheet("background-color: #757575; color: white; font-weight: bold; padding: 8px;")
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

    @staticmethod
    def _format_dt(dt: object) -> str:
        return DocumentsDetailPresenter.format_dt(dt)

    @staticmethod
    def _document_code(state: object) -> str:
        return DocumentsDetailPresenter.document_code(state)

    def _fill_two_col_table(self, table, rows: list[tuple[str, str]]) -> None:
        fill_table(table, rows)

    def _fill_history_table(self, rows: list[tuple[str, str, str, str, str]]) -> None:
        fill_table(self._tab_history, rows)

    def _append(self, title: str, payload: object, *, to_output: bool = True) -> None:
        if to_output:
            self._out.appendPlainText(f"{title}: {payload}\n")
        self._inline_notice.setText(f"Info: {title}")
        window = self.window()
        if hasattr(window, "statusBar"):
            try:
                window.statusBar().showMessage(f"{title}", 10000)
            except Exception:
                pass

    def _audit(self, *, action: str, actor: str, target: str, result: str, reason: str = "") -> None:
        self._sig_ops.audit(action=action, actor=actor, target=target, result=result, reason=reason)

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
            QMessageBox.critical(self, "Dokumentenlenkung", str(exc))
        else:
            QMessageBox.warning(self, "Dokumentenlenkung", str(exc))
        self._inline_notice.setText(f"Fehler: {exc}")
        self._append("ERROR", {"message": str(exc)}, to_output=False)
        window = self.window()
        if hasattr(window, "statusBar"):
            try:
                window.statusBar().showMessage(f"FEHLER: {exc}", 10000)
            except Exception:
                pass

    def _toggle_output_visibility(self) -> None:
        visible = not self._out.isVisible()
        self._out.setVisible(visible)
        self._toggle_output_btn.setText("Protokoll ausblenden" if visible else "Protokoll anzeigen")

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
        result = open_advanced_filter_dialog(self, self._advanced_filters)
        if result is None:
            return
        self._advanced_filters = result
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
        if self._reload_thread is not None:
            self._reload_cancelled = True
            if self._reload_progress is not None:
                self._reload_progress.cancel()
            return
        self._reload_cancelled = False
        self._reload_progress = QProgressDialog("Tabelle wird aktualisiert ...", "Abbrechen", 0, 0, self)
        self._reload_progress.setWindowTitle("Dokumentenlenkung")
        self._reload_progress.setMinimumDuration(150)
        self._reload_progress.canceled.connect(self._cancel_reload)
        self._reload_progress.show()
        self._inline_notice.setText("Tabellenaktualisierung laeuft ...")

        self._reload_thread = QThread(self)
        self._reload_worker = TableReloadWorker(self._build_reload_result)
        self._reload_worker.moveToThread(self._reload_thread)
        self._reload_thread.started.connect(self._reload_worker.run)
        self._reload_worker.finished.connect(self._on_reload_finished)
        self._reload_worker.failed.connect(self._on_reload_failed)
        self._reload_worker.finished.connect(self._cleanup_reload_worker)
        self._reload_worker.failed.connect(self._cleanup_reload_worker)
        self._reload_thread.start()

    def _cancel_reload(self) -> None:
        self._reload_cancelled = True
        self._inline_notice.setText("Tabellenaktualisierung abgebrochen.")

    def _build_reload_result(self) -> TableReloadResult:
        rows: list[object] = []
        status_filter = self._status_filter.currentData()
        statuses = list(DocumentStatus) if status_filter == "ALL" else [status_filter]
        for status in statuses:
            rows.extend(self._pool.list_by_status(status))
        user = self._um.get_current_user()
        scope = str(self._scope_filter.currentData())
        rows = self._filter_presenter.filter_rows(
            rows,
            scope=scope,
            user_id=str(user.user_id) if user is not None else None,
            owner_contains=str(self._advanced_filters["owner_contains"]),
            title_contains=str(self._advanced_filters["title_contains"]),
            workflow_active=str(self._advanced_filters["workflow_active"]),
            active_version=str(self._advanced_filters["active_version"]),
        )
        return TableReloadResult(
            rows=rows,
            scope=scope,
            status_filter=str(status_filter),
            advanced_filters=dict(self._advanced_filters),
        )

    def _on_reload_finished(self, result: object) -> None:
        if self._reload_cancelled:
            return
        if not isinstance(result, TableReloadResult):
            self._show_error(RuntimeError("ungueltiges Reload-Ergebnis"))
            return
        self._model.load(result.rows)
        self._append(
            "TABELLE_AKTUALISIERT",
            {
                "rows": len(result.rows),
                "scope": result.scope,
                "status_filter": result.status_filter,
                "advanced": result.advanced_filters,
            },
            to_output=False,
        )
        self._update_action_visibility()

    def _on_reload_failed(self, error_message: str) -> None:
        if self._reload_cancelled:
            return
        self._show_error(RuntimeError(error_message))

    def _cleanup_reload_worker(self, *_args) -> None:
        if self._reload_progress is not None:
            self._reload_progress.close()
            self._reload_progress.deleteLater()
            self._reload_progress = None
        if self._reload_thread is not None:
            self._reload_thread.quit()
            self._reload_thread.wait(1500)
            self._reload_thread.deleteLater()
            self._reload_thread = None
        if self._reload_worker is not None:
            self._reload_worker.deleteLater()
            self._reload_worker = None

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
        user = self._um.get_current_user()
        user_id = str(user.user_id) if user is not None else None
        user_role = role_to_system_role(user.role) if user is not None else None
        visible_for = self._presenter.visible_actions_for_context(self._current_state, user_id=user_id, user_role=user_role)
        update_action_visibility(
            self._workflow_actions["buttons"],
            self._top_actions["buttons"],
            visible_for,
            self._is_profile_manager_allowed(),
        )
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
        state = self._state_from_selection()
        for artifact_type in preferred_types:
            if self._sig_ops.open_artifact(state, artifact_type):
                self._append("ARTEFAKT_GEOEFFNET", {"type": artifact_type.value})
                self._inline_notice.setText(f"Standardaktion ausgeführt: {artifact_type.value} geöffnet.")
                return
        self._open_details_from_table()
        self._inline_notice.setText("Keine lesbare Datei gefunden. Details wurden geöffnet.")

    def _refresh_details(self) -> None:
        if self._current_state is None:
            return
        state = self._state_from_selection()
        header = self._pool.get_header(state.document_id)
        dp = DocumentsDetailPresenter
        self._fill_two_col_table(self._tab_overview, dp.overview_rows(state, header))
        self._fill_two_col_table(self._tab_roles, dp.roles_rows(state))
        history_rows = dp.history_rows(state)
        self._fill_history_table(history_rows)
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
        self._refresh_change_requests(state)
        self._extension_valid_from.setText(self._format_dt(state.valid_from))
        self._extension_valid_until.setText(self._format_dt(state.valid_until))
        self._extension_next_review.setText(self._format_dt(state.next_review_at))
        self._extension_count.setText(f"{state.extension_count}/3")
        if state.valid_until is not None:
            now = datetime.now(state.valid_until.tzinfo) if state.valid_until.tzinfo else datetime.now()
            remaining_days = max((state.valid_until - now).days, 0)
            self._extension_remaining_days.setText(str(remaining_days))
        else:
            self._extension_remaining_days.setText("-")

    def _refresh_change_requests(self, state) -> None:
        rows = self._wf.list_change_requests(state)
        if not rows:
            self._tab_comments.setPlainText("Keine Change Requests vorhanden.")
            return
        lines: list[str] = []
        for idx, row in enumerate(rows, start=1):
            change_id = str(row.get("change_id", "")).strip() or f"CR-{idx}"
            reason = str(row.get("reason", "")).strip()
            refs = row.get("impact_refs", [])
            if not isinstance(refs, list):
                refs = []
            created_by = str(row.get("created_by", "")).strip()
            created_at = str(row.get("created_at", "")).strip()
            lines.append(f"{idx}. {change_id}")
            lines.append(f"   Grund: {reason}")
            if refs:
                lines.append(f"   Impact-Refs: {', '.join(str(v) for v in refs)}")
            if created_by or created_at:
                lines.append(f"   Erfasst von: {created_by or '-'} am {created_at or '-'}")
            lines.append("")
        self._tab_comments.setPlainText("\n".join(lines).strip())

    def _add_change_request(self) -> None:
        try:
            state = self._state_from_selection()
            user, role = self._current_user_role()
            dialog = QDialog(self)
            dialog.setWindowTitle("Change Request hinzufügen")
            change_id = QLineEdit()
            reason = QLineEdit()
            impact_refs = QLineEdit()
            form = QFormLayout()
            form.addRow("Change-ID", change_id)
            form.addRow("Grund", reason)
            form.addRow("Impact-Refs (CSV)", impact_refs)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout = QVBoxLayout(dialog)
            layout.addLayout(form)
            layout.addWidget(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            payload = self._wf.add_change_request(
                state,
                change_id=change_id.text().strip(),
                reason=reason.text().strip(),
                impact_refs=[value.strip() for value in impact_refs.text().split(",") if value.strip()],
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("CHANGE_REQUEST_GESPEICHERT", {"document_id": payload.document_id, "version": payload.version})
            self._current_state = payload
            self._refresh_details()
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _export_change_requests(self) -> None:
        try:
            state = self._state_from_selection()
            rows = self._wf.list_change_requests(state)
            if not rows:
                self._inline_notice.setText("Keine Change Requests zum Export vorhanden.")
                return
            default_suffix = ".csv" if self._last_change_export_format == "csv" else ".json"
            default_name = f"{state.document_id}_v{state.version}_change_requests{default_suffix}"
            default_target = self._last_change_export_dir / default_name
            selected_filter_default = (
                "CSV (*.csv)" if self._last_change_export_format == "csv" else "JSON (*.json)"
            )
            target, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Change Requests exportieren",
                str(default_target),
                "JSON (*.json);;CSV (*.csv)",
                selected_filter_default,
            )
            if not target:
                return
            output = Path(target)
            output.parent.mkdir(parents=True, exist_ok=True)
            export_csv = selected_filter.lower().startswith("csv") or output.suffix.lower() == ".csv"
            if export_csv:
                if output.suffix.lower() != ".csv":
                    output = output.with_suffix(".csv")
                with output.open("w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(
                        fh,
                        fieldnames=["change_id", "reason", "impact_refs", "created_by", "created_at"],
                    )
                    writer.writeheader()
                    for row in rows:
                        refs = row.get("impact_refs", [])
                        writer.writerow(
                            {
                                "change_id": str(row.get("change_id", "")),
                                "reason": str(row.get("reason", "")),
                                "impact_refs": ",".join(str(v) for v in refs) if isinstance(refs, list) else "",
                                "created_by": str(row.get("created_by", "")),
                                "created_at": str(row.get("created_at", "")),
                            }
                        )
                fmt = "csv"
            else:
                if output.suffix.lower() != ".json":
                    output = output.with_suffix(".json")
                output.write_text(json.dumps(rows, indent=2, ensure_ascii=True), encoding="utf-8")
                fmt = "json"
            self._last_change_export_dir = output.parent
            self._last_change_export_format = fmt
            self._append("CHANGE_REQUEST_EXPORT", {"format": fmt, "path": str(output), "count": len(rows)})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

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
            document_id = data.document_id.strip()
            created = self._wf.create_document_version(
                document_id,
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
                            document_id,
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
                            document_id,
                            version,
                            Path(data.source_path),
                            actor_user_id=user_obj.user_id,
                            actor_role=role,
                        ),
                    )
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc, critical=True)

    def _edit_docx(self) -> None:
        try:
            state = self._state_from_selection()
            post_edit_statuses = {
                DocumentStatus.IN_REVIEW,
                DocumentStatus.IN_APPROVAL,
                DocumentStatus.APPROVED,
                DocumentStatus.ARCHIVED,
            }
            if state.status in post_edit_statuses:
                priorities = DocumentsWorkflowPresenter.default_artifact_priority(state.status)
                for artifact_type in priorities:
                    if self._sig_ops.open_artifact(state, artifact_type):
                        self._append(
                            "PDF_GEOEFFNET",
                            {"reason": "post-edit phase – DOCX gesperrt", "type": artifact_type.value},
                        )
                        return
                raise RuntimeError(
                    f"Status ist '{state.status.value}' – DOCX ist gesperrt. "
                    "Keine PDF-Datei für diese Phase gefunden."
                )
            if not self._sig_ops.open_artifact(state, ArtifactType.SOURCE_DOCX):
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
            sign_request = self._sig_ops.build_sign_request_or_none(state, "IN_PROGRESS->IN_REVIEW", self)
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
            state = self._state_from_selection()
            sign_request = self._sig_ops.build_sign_request_or_none(state, "IN_REVIEW->IN_APPROVAL", self)
            if (
                state.workflow_profile
                and "IN_REVIEW->IN_APPROVAL" in set(state.workflow_profile.signature_required_transitions)
                and sign_request is None
            ):
                self._inline_notice.setText("Signaturvorgang abgebrochen.")
                self._audit(
                    action="documents.workflow.review.accept",
                    actor=str(user.user_id),
                    target=f"{state.document_id}:{state.version}",
                    result="cancelled",
                    reason="signature_cancelled",
                )
                return
            payload = self._wf.accept_review(
                self._state_from_selection(),
                user.user_id,
                sign_request=sign_request,
                actor_role=role,
            )
            self._append("PRUEFUNG_ANGENOMMEN", payload)
            self._audit(
                action="documents.workflow.review.accept",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="ok",
                reason="IN_REVIEW->IN_APPROVAL",
            )
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
            sign_request = self._sig_ops.build_sign_request_or_none(self._state_from_selection(), "IN_APPROVAL->APPROVED", self)
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

            if state.status != DocumentStatus.APPROVED:
                raise RuntimeError("Verlaengerung ist nur im Status APPROVED moeglich")
            if state.extension_count >= 3:
                raise RuntimeError("Maximale Anzahl von Verlaengerungen (3) erreicht")
            dialog = ValidityExtensionDialog(
                valid_from=state.valid_from,
                valid_until=state.valid_until,
                next_review_at=state.next_review_at,
                extension_count=state.extension_count,
                parent=self,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self._inline_notice.setText("Verlaengerungsvorgang abgebrochen.")
                return
            request = dialog.payload()
            if request.review_outcome == ValidityExtensionOutcome.NEW_VERSION_REQUIRED:
                self._inline_notice.setText("Neue Version erforderlich - Verlaengerung nicht ausgefuehrt.")
                return

            sign_request = self._sig_ops.build_extension_sign_request(state, self)
            if sign_request is None:
                self._inline_notice.setText("Verlaengerungsvorgang abgebrochen.")
                return

            self._sig_ops.require_signature_call(sign_request)
            signing_user_id = str(sign_request.signer_user or user.user_id)

            payload, is_maxed = self._wf.extend_annual_validity(
                state,
                actor_user_id=signing_user_id,
                signature_present=True,
                duration_days=request.duration_days,
                reason=request.reason,
                review_outcome=request.review_outcome,
            )
            self._append("JAHRESVERLAENGERUNG", {
                "new_extension_count": payload.extension_count,
                "is_maxed": is_maxed,
                "review_outcome": request.review_outcome.value,
                "reason": request.reason,
                "next_review_at": str(payload.next_review_at),
                "valid_until": str(payload.valid_until),
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

