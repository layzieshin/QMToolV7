from __future__ import annotations

from interfaces.pyqt.contributions.common import as_json_text
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QTableView, QVBoxLayout, QWidget, QPlainTextEdit

from interfaces.pyqt.registry.contribution import QtModuleContribution
from qm_platform.runtime.container import RuntimeContainer


class _RegistryModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._headers = ["document_id", "active_version", "register_state", "is_findable"]
        self._rows: list[list[object]] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        return str(self._rows[index.row()][index.column()])

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


class RegistryBrowseWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._model = _RegistryModel()
        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setSortingEnabled(True)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self._details = QPlainTextEdit()
        self._details.setReadOnly(True)

        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self._reload)

        hint = QLabel("Zentrales Register (nur Lesen). Verbindliche Änderungen über den Dokument-Workflow.")
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(refresh)
        layout.addWidget(self._view, stretch=1)
        layout.addWidget(QLabel("Detailansicht"))
        layout.addWidget(self._details, stretch=1)
        self._reload()

    def _reload(self) -> None:
        api = self._container.get_port("registry_api")
        entries = api.list_entries()
        rows: list[list[object]] = []
        for e in entries:
            rows.append(
                [
                    e.document_id,
                    e.active_version if e.active_version is not None else "",
                    e.register_state.value,
                    "yes" if e.is_findable else "no",
                ]
            )
        self._model.load(rows)
        self._details.clear()

    def _on_selection_changed(self) -> None:
        selected = self._view.selectionModel().selectedRows()
        if not selected:
            self._details.clear()
            return
        row = selected[0].row()
        doc_id = str(self._model._rows[row][0])
        try:
            registry_api = self._container.get_port("registry_api")
            docs_service = self._container.get_port("documents_service")
            pool_api = self._container.get_port("documents_pool_api")
            entry = registry_api.get_entry(doc_id)
            header = pool_api.get_header(doc_id)
            state = None
            if entry is not None and entry.active_version is not None:
                state = docs_service.get_document_version(doc_id, int(entry.active_version))
            payload = {
                "registry_entry": entry,
                "document_header": header,
                "active_state": state,
            }
            self._details.setPlainText(as_json_text(payload))
        except Exception as exc:  # noqa: BLE001
            self._details.setPlainText(as_json_text({"error": str(exc)}))


def _build(container: RuntimeContainer) -> QWidget:
    return RegistryBrowseWidget(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="registry.browse",
            module_id="registry",
            title="Register",
            sort_order=40,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
