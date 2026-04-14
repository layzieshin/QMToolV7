from __future__ import annotations

from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import as_json_text, normalize_role
from interfaces.pyqt.presenters.training_presenter import TrainingPresenter
from interfaces.pyqt.registry.contribution import QtModuleContribution
from qm_platform.runtime.container import RuntimeContainer


class TrainingWorkspace(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._api = container.get_port("training_api")
        self._admin = container.get_port("training_admin_api")
        self._um = container.get_port("usermanagement_service")
        self._presenter = TrainingPresenter()

        self._user_id = QLineEdit()
        self._doc_id = QLineEdit()
        self._version = QLineEdit("1")
        self._session_id = QLineEdit()
        self._answers = QLineEdit("0,0,0")
        self._comment = QLineEdit()
        self._last_page_seen = QLineEdit("1")
        self._total_pages = QLineEdit("1")
        self._scrolled_to_end = QLineEdit("true")
        self._category_id = QLineEdit("cat-1")
        self._category_name = QLineEdit("Kategorie 1")
        self._category_desc = QLineEdit()
        self._quiz_json = QPlainTextEdit('{"questions":[{"id":"q1","text":"Frage 1","options":["A","B","C"],"correct_index":0},{"id":"q2","text":"Frage 2","options":["A","B","C"],"correct_index":1},{"id":"q3","text":"Frage 3","options":["A","B","C"],"correct_index":2}]}')
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Dokument", "Version", "gelesen", "Quiz", "bestanden", "letzte Aktion"])
        self._show_open_only = QLineEdit("true")
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        outer = QVBoxLayout(self)
        outer.addWidget(QLabel("Schulungsbereich: offene Schulungen, Lesen, Quiz und Verlauf."))

        tabs = QTabWidget()
        tabs.addTab(self._build_user_tab(), "Meine Schulungen")
        role = normalize_role(self._current_user().role)
        if role in ("ADMIN", "QMB"):
            tabs.addTab(self._build_admin_tab(), "Admin / QMB")
        outer.addWidget(tabs, stretch=1)
        outer.addWidget(QLabel("Ergebnis"))
        outer.addWidget(self._out, stretch=1)
        self._list_required()

    def _build_user_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        row = QHBoxLayout()
        btn_refresh = QPushButton("Offene Schulungen laden")
        btn_refresh.clicked.connect(self._list_required)
        btn_read = QPushButton("Lesen bestätigen")
        btn_read.clicked.connect(self._confirm_read)
        btn_quiz_start = QPushButton("Quiz starten")
        btn_quiz_start.clicked.connect(self._start_quiz)
        btn_quiz_submit = QPushButton("Quiz abgeben")
        btn_quiz_submit.clicked.connect(self._submit_answers)
        row.addWidget(btn_refresh)
        row.addWidget(btn_read)
        row.addWidget(btn_quiz_start)
        row.addWidget(btn_quiz_submit)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(self._table, stretch=1)
        form = QFormLayout()
        form.addRow("Benutzer-ID (optional)", self._user_id)
        form.addRow("Dokument-ID", self._doc_id)
        form.addRow("Version", self._version)
        form.addRow("Quiz-Session-ID", self._session_id)
        form.addRow("Quiz-Antworten CSV", self._answers)
        form.addRow("Kommentartext", self._comment)
        form.addRow("last_page_seen", self._last_page_seen)
        form.addRow("total_pages", self._total_pages)
        form.addRow("scrolled_to_end (true/false)", self._scrolled_to_end)
        form.addRow("Nur offene Schulungen (true/false)", self._show_open_only)
        layout.addLayout(form)
        btn_comment = QPushButton("Kommentar speichern")
        btn_comment.clicked.connect(self._add_comment)
        layout.addWidget(btn_comment)
        return tab

    def _build_admin_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        form.addRow("Kategorie-ID", self._category_id)
        form.addRow("Kategoriename", self._category_name)
        form.addRow("Kategoriebeschreibung", self._category_desc)
        layout.addLayout(form)
        row = QHBoxLayout()
        for label, fn in [
            ("Freigegebene Dokumente", self._admin_list_approved),
            ("Kategorie erstellen", self._admin_create_category),
            ("Dokument zu Kategorie", self._admin_assign_doc),
            ("Benutzer zu Kategorie", self._admin_assign_user),
            ("Zuweisungen synchronisieren", self._admin_sync),
            ("Matrix anzeigen", self._admin_matrix),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(fn)
            row.addWidget(btn)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(QLabel("Quiz-JSON Import (nur freigegebene, aktuelle Dokumente)"))
        layout.addWidget(self._quiz_json, stretch=1)
        btn_import = QPushButton("Quiz für Dokument importieren")
        btn_import.clicked.connect(self._admin_import_quiz)
        layout.addWidget(btn_import)
        return tab

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}: {payload}\n")

    def _show_error(self, exc: Exception) -> None:
        QMessageBox.warning(self, "Training", str(exc))
        self._append("ERROR", {"message": str(exc)})

    def _current_user(self):
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        return user

    def _current_user_id(self) -> str:
        override = self._user_id.text().strip()
        if override:
            return override
        return self._current_user().user_id

    def _require_admin_or_qmb(self) -> None:
        role = normalize_role(self._current_user().role)
        if role not in ("ADMIN", "QMB"):
            raise RuntimeError("Nur QMB oder ADMIN dürfen Training-Admin-Aktionen ausführen")

    def _doc_ref(self) -> tuple[str, int]:
        return self._doc_id.text().strip(), int(self._version.text().strip())

    def _list_required(self) -> None:
        try:
            payload = self._api.list_training_overview_for_user(self._current_user_id())
            open_only = self._show_open_only.text().strip().lower() != "false"
            rows = self._presenter.filter_rows(payload, open_only=open_only)
            self._append("PFLICHTLISTE_OVERVIEW", self._presenter.status_line(rows=len(rows), open_only=open_only))
            self._table.setRowCount(len(rows))
            for i, item in enumerate(rows):
                self._table.setItem(i, 0, QTableWidgetItem(str(item.document_id)))
                self._table.setItem(i, 1, QTableWidgetItem(str(item.version)))
                self._table.setItem(i, 2, QTableWidgetItem("ja" if item.read_confirmed else "nein"))
                self._table.setItem(i, 3, QTableWidgetItem("ja" if item.quiz_available else "nein"))
                self._table.setItem(i, 4, QTableWidgetItem("ja" if item.quiz_passed else "nein"))
                self._table.setItem(i, 5, QTableWidgetItem(str(item.last_action_at or "")))
            self._table.resizeColumnsToContents()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _confirm_read(self) -> None:
        try:
            doc_id, version = self._doc_ref()
            payload = self._api.confirm_read(
                user_id=self._current_user_id(),
                document_id=doc_id,
                version=version,
                last_page_seen=int(self._last_page_seen.text().strip() or "1"),
                total_pages=int(self._total_pages.text().strip() or "1"),
                scrolled_to_end=self._scrolled_to_end.text().strip().lower() == "true",
            )
            self._append("LESEN_BESTAETIGT", payload)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _start_quiz(self) -> None:
        try:
            doc_id, version = self._doc_ref()
            session, questions = self._api.start_quiz(self._current_user_id(), doc_id, version)
            self._session_id.setText(session.session_id)
            self._append("QUIZ_START", {"session": session, "questions": questions})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _submit_answers(self) -> None:
        try:
            answers = [int(v.strip()) for v in self._answers.text().split(",") if v.strip()]
            payload = self._api.submit_quiz_answers(self._session_id.text().strip(), answers)
            self._append("QUIZ_ABGABE", payload)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _add_comment(self) -> None:
        try:
            doc_id, version = self._doc_ref()
            payload = self._api.add_comment(self._current_user_id(), doc_id, version, self._comment.text().strip())
            self._append("KOMMENTAR_HINZUGEFUEGT", payload)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _admin_list_approved(self) -> None:
        try:
            self._require_admin_or_qmb()
            payload = self._admin.list_quiz_capable_approved_documents()
            self._append("ADMIN_QUIZ_FAHIGE_DOKUMENTE", payload)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _admin_create_category(self) -> None:
        try:
            self._require_admin_or_qmb()
            payload = self._admin.create_category(
                self._category_id.text().strip(),
                self._category_name.text().strip(),
                self._category_desc.text().strip() or None,
            )
            self._append("ADMIN_KATEGORIE_ERSTELLT", payload)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _admin_assign_doc(self) -> None:
        try:
            self._require_admin_or_qmb()
            doc_id, _version = self._doc_ref()
            self._admin.assign_document_to_category(self._category_id.text().strip(), doc_id)
            self._append("ADMIN_DOKU_ZUGEWIESEN", {"category_id": self._category_id.text().strip(), "document_id": doc_id})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _admin_assign_user(self) -> None:
        try:
            self._require_admin_or_qmb()
            self._admin.assign_user_to_category(self._category_id.text().strip(), self._current_user_id())
            self._append("ADMIN_BENUTZER_ZUGEWIESEN", {"category_id": self._category_id.text().strip(), "user_id": self._current_user_id()})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _admin_sync(self) -> None:
        try:
            self._require_admin_or_qmb()
            payload = self._admin.sync_required_assignments()
            self._append("ADMIN_SYNC", {"created_or_updated": payload})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _admin_import_quiz(self) -> None:
        try:
            self._require_admin_or_qmb()
            doc_id, version = self._doc_ref()
            raw = self._quiz_json.toPlainText().strip()
            digest = self._admin.import_quiz_questions(doc_id, version, raw.encode("utf-8"))
            self._append("ADMIN_QUIZ_IMPORT", {"digest": digest, "document_id": doc_id, "version": version})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _admin_matrix(self) -> None:
        try:
            self._require_admin_or_qmb()
            payload = self._admin.list_matrix()
            self._append("ADMIN_MATRIX", payload)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)


def _build(container: RuntimeContainer) -> QWidget:
    return TrainingWorkspace(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="training.workspace",
            module_id="training",
            title="Schulung",
            sort_order=40,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
