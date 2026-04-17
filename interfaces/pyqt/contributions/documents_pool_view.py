from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtWidgets import (
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)

from interfaces.pyqt.presenters.artifact_paths import resolve_openable_artifact_paths
from interfaces.pyqt.presenters.storage_paths import artifacts_root
from interfaces.pyqt.registry.contribution import QtModuleContribution
from modules.documents.contracts import ArtifactType
from qm_platform.runtime.container import RuntimeContainer
from modules.usermanagement.role_policies import is_effective_qmb


class _PoolTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._headers = ["Dokumentenkennung", "Titel", "Version", "gueltig bis", "freigegeben am"]
        self._rows: list[object] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = self._rows[index.row()]
        values = [
            row.document_id,
            row.title,
            row.version,
            row.valid_until.date().isoformat() if row.valid_until else "",
            row.released_at.date().isoformat() if row.released_at else "",
        ]
        return str(values[index.column()])

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return str(section + 1)

    def load(self, rows: list[list[object]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


class DocumentsPoolWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._app_home = Path.cwd()
        self._um = container.get_port("usermanagement_service")
        self._pool = container.get_port("documents_pool_api")
        self._model = _PoolTableModel()
        self._artifacts_root = artifacts_root(self._container, self._app_home)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Suche nach Dokument-ID oder Titel")

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)

        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self._reload)
        open_btn = QPushButton("Lesen")
        open_btn.clicked.connect(self._open_selected_pdf)

        self._error = QLabel("")
        self._error.setWordWrap(True)
        self._error.setObjectName("errorLabel")
        self._details = QPlainTextEdit()
        self._details.setReadOnly(True)

        hint = QLabel(
            "Pool ist der Enddokument-Bereich fuer freigegebene/gueltige Dokumente. "
            "Kein Workflow-Arbeitsbereich."
        )
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        form = QFormLayout()
        form.addRow("Suche", self._search)
        layout.addLayout(form)
        actions = QFormLayout()
        actions.addRow(refresh, open_btn)
        layout.addLayout(actions)
        layout.addWidget(self._error)
        layout.addWidget(self._table, stretch=1)
        layout.addWidget(QLabel("Dokument-Details"))
        layout.addWidget(self._details, stretch=1)

        self._search.textChanged.connect(lambda _text: self._reload())
        self._table.selectionModel().selectionChanged.connect(self._on_selected)
        self._table.doubleClicked.connect(lambda _idx: self._open_selected_pdf())
        self._reload()

    def _reload(self) -> None:
        self._error.clear()
        try:
            rows_o = self._pool.list_current_released_documents()
            term = self._search.text().strip().lower()
            rows = []
            for r in rows_o:
                if term and term not in r.document_id.lower() and term not in (r.title or "").lower():
                    continue
                rows.append(r)
            self._model.load(rows)
            self._details.clear()
        except Exception as exc:  # noqa: BLE001
            self._model.load([])
            self._error.setText(str(exc))

    def _on_selected(self) -> None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            self._details.clear()
            return
        row = self._model._rows[selected[0].row()]
        user = self._um.get_current_user()
        effective_qmb = is_effective_qmb(user) if user else False
        header = self._pool.get_header(row.document_id)
        lines = [
            f"Dokumentenkennung: {row.document_id}",
            f"Titel: {row.title}",
            f"Version: {row.version}",
            "Status: APPROVED",
            f"Owner: {row.owner_user_id or '-'}",
            f"gueltig bis: {row.valid_until.date().isoformat() if row.valid_until else '-'}",
            f"freigegeben am: {row.released_at.date().isoformat() if row.released_at else '-'}",
            f"Department: {header.department if header else '-'}",
            f"Standort: {header.site if header else '-'}",
            f"Regulatory Scope: {header.regulatory_scope if header else '-'}",
            f"QMB Druckberechtigung: {'ja' if effective_qmb else 'nein'}",
        ]
        self._details.setPlainText("\n".join(lines))

    def _open_selected_pdf(self) -> None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            self._error.setText("Bitte zuerst ein Dokument auswählen.")
            return
        row = self._model._rows[selected[0].row()]
        artifacts = self._pool.list_artifacts(row.document_id, row.version)
        for artifact in artifacts:
            if artifact.artifact_type != ArtifactType.RELEASED_PDF:
                continue
            for path in resolve_openable_artifact_paths(
                artifact=artifact,
                app_home=self._app_home,
                artifacts_root=self._artifacts_root,
            ):
                if not path.exists():
                    continue
                if hasattr(os, "startfile"):
                    os.startfile(str(path))  # type: ignore[attr-defined]
                    self._error.setText(f"Geöffnet: {path}")
                    return
        self._error.setText("Kein lokal oeffenbares RELEASED_PDF-Artefakt verfuegbar.")

    def _resolve_artifacts_root(self) -> Path:
        return artifacts_root(self._container, self._app_home)


def _build(container: RuntimeContainer) -> QWidget:
    return DocumentsPoolWidget(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="documents.pool",
            module_id="documents",
            title="Dokumente",
            sort_order=20,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
