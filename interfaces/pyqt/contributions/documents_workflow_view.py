from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import safe_connect
from interfaces.pyqt.logging_adapter import get_logger
from interfaces.pyqt.models.workflow_table_model import WorkflowTableModel
from interfaces.pyqt.presenters.documents_signature_ops import DocumentsSignatureOps
from interfaces.pyqt.presenters.documents_workflow_filter_presenter import DocumentsWorkflowFilterPresenter
from interfaces.pyqt.presenters.documents_workflow_presenter import DocumentsWorkflowPresenter
from interfaces.pyqt.presenters.storage_paths import artifacts_root
from interfaces.pyqt.sections.action_bar import build_workflow_action_bar
from interfaces.pyqt.sections.detail_drawer import (
    DetailDrawerBuilder,
    build_extension_tab,
    build_metadata_tab,
    build_roles_tab,
    new_readonly_table,
)
from interfaces.pyqt.sections.filter_bar import build_top_filter_bar
from interfaces.pyqt.contributions.documents_workflow.actions_mixin import DocumentsWorkflowActionsMixin
from interfaces.pyqt.contributions.documents_workflow.core_mixin import DocumentsWorkflowCoreMixin
from interfaces.pyqt.contributions.documents_workflow.selection_mixin import DocumentsWorkflowSelectionMixin
from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType
from qm_platform.runtime.container import RuntimeContainer


class DocumentsWorkflowWidget(
    DocumentsWorkflowActionsMixin,
    DocumentsWorkflowSelectionMixin,
    DocumentsWorkflowCoreMixin,
    QWidget,
):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._log = get_logger(__name__)
        self._container = container
        self._app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
        self._um = container.get_port("usermanagement_service")
        self._docs_service = container.get_port("documents_service")
        self._pool = container.get_port("documents_pool_api")
        self._wf = container.get_port("documents_workflow_api")
        self._comments_api = container.get_port("documents_comments_api") if container.has_port("documents_comments_api") else None
        self._registry = container.get_port("registry_api") if container.has_port("registry_api") else None
        self._signature_api = container.get_port("signature_api") if container.has_port("signature_api") else None
        self._audit_logger = container.get_port("audit_logger") if container.has_port("audit_logger") else None
        self._artifacts_root = artifacts_root(self._container, self._app_home)
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
        self._reload_thread = None
        self._reload_worker = None
        self._reload_progress = None
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
        safe_connect(self._table.selectionModel().selectionChanged, self._on_table_selected)
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
        self._tab_comments = QTableWidget(0, 6)
        self._tab_comments.setHorizontalHeaderLabels(["Ref", "Kommentarstatus", "Seite", "Autor", "Datum", "Vorschau"])
        self._tab_comments.itemDoubleClicked.connect(self._open_comment_detail)
        self._tab_comments.itemSelectionChanged.connect(self._update_comment_action_state)
        self._comments_context_label = QLabel("Kontext: -")
        self._add_comment_btn = QPushButton("Kommentar hinzufuegen")
        self._add_comment_btn.clicked.connect(self._open_comment_viewer)
        self._resolve_comment_btn = QPushButton("Kommentar resolven")
        self._resolve_comment_btn.setEnabled(False)
        self._resolve_comment_btn.clicked.connect(self._resolve_selected_comment)
        self._activate_comment_btn = QPushButton("Auf aktiv setzen")
        self._activate_comment_btn.setEnabled(False)
        self._activate_comment_btn.clicked.connect(self._activate_selected_comment)
        self._comments_tab = QWidget()
        comments_layout = QVBoxLayout(self._comments_tab)
        comments_layout.addWidget(self._comments_context_label)
        comments_layout.addWidget(self._tab_comments, stretch=1)
        comments_actions = QHBoxLayout()
        comments_actions.addWidget(self._add_comment_btn)
        comments_actions.addWidget(self._resolve_comment_btn)
        comments_actions.addWidget(self._activate_comment_btn)
        comments_actions.addStretch(1)
        comments_layout.addLayout(comments_actions)
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
            on_archive=self._archive_approved,
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
            doc_id=self._doc_id,
            version=self._version,
            title=self._title,
            description=self._description,
            doc_type=self._doc_type,
            control_class=self._control_class,
            profile=self._profile,
            department=self._department,
            site=self._site,
            regulatory_scope=self._regulatory_scope,
            valid_until=self._valid_until,
            next_review=self._next_review,
            custom_fields=self._custom_fields,
            on_save_metadata=self._update_metadata,
            on_save_header=self._update_header,
            on_add_change_request=None,
            metadata_buttons=self._metadata_buttons,
        )
        roles_tab = build_roles_tab(
            editors=self._editors,
            reviewers=self._reviewers,
            approvers=self._approvers,
            tab_roles=self._tab_roles,
            on_save_roles=self._assign_roles,
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
            tab_overview=self._tab_overview,
            tab_roles=self._tab_roles,
            tab_comments=self._comments_tab,
            tab_history=self._tab_history,
            history_notice=self._history_notice,
            metadata_tab=metadata_tab,
            roles_tab=roles_tab,
            extension_tab=extension_tab,
        )
        self._details_toggle = self._details.toggle_button()
        self._details_toggle.setText("Details")
        self._details_toggle.setMinimumWidth(52)
        self._details_toggle.setMinimumHeight(120)
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
