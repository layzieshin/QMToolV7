"""Training workspace – dreigeteilte Ansicht (§8).

Upper bar: Admin/QMB actions (Import Quiz, Quiz zuordnen, Statistik/Logs, Kommentare)
Middle: Nutzerabhängige Dokumentenliste (materialisierte Inbox)
Lower bar: Kontextbezogene Aktionen (Quiz starten, Lesen, Quiz kommentieren)
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.presenters.training_presenter import TrainingPresenter
from interfaces.pyqt.registry.contribution import QtModuleContribution
from interfaces.pyqt.presenters.artifact_paths import resolve_openable_artifact_paths
from interfaces.pyqt.widgets.access_guards import require_admin_or_qmb
from interfaces.pyqt.widgets.tag_editor_widget import TagEditorWidget
from interfaces.pyqt.widgets.pdf_viewer_dialog import PdfViewerDialog, PdfViewerRequest
from interfaces.pyqt.widgets.quiz_binding_dialog import QuizBindingDialog
from interfaces.pyqt.widgets.quiz_dialogs import QuizDialog, QuizResultDialog
from interfaces.pyqt.widgets.training_comments_admin_dialog import TrainingCommentsAdminDialog
from interfaces.pyqt.contributions.common import user_to_system_role
from interfaces.pyqt.logging_adapter import get_logger
from interfaces.pyqt.presenters.storage_paths import artifacts_root
from modules.documents.contracts import ArtifactType
from qm_platform.runtime.container import RuntimeContainer


# ---------------------------------------------------------------------------
# Main workspace widget
# ---------------------------------------------------------------------------

class TrainingWorkspace(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._logger = get_logger(__name__)
        self._container = container
        self._api = container.get_port("training_api")
        self._admin = container.get_port("training_admin_api")
        self._um = container.get_port("usermanagement_service")
        self._read_api = container.get_port("documents_read_api")
        self._pool = container.get_port("documents_pool_api")
        self._app_home = container.get_port("app_home") if container.has_port("app_home") else Path.cwd()
        self._artifacts_root = artifacts_root(self._container, self._app_home)
        self._presenter = TrainingPresenter()
        self._inbox_items: list = []
        self._selected_item = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- UPPER: Admin bar ---
        self._admin_bar = QWidget()
        admin_row = QHBoxLayout(self._admin_bar)
        admin_row.setContentsMargins(0, 0, 0, 0)
        self._btn_import_quiz = QPushButton("Import Quiz")
        self._btn_import_quiz.clicked.connect(self._on_import_quiz)
        self._btn_bind_quiz = QPushButton("Quiz zuordnen")
        self._btn_bind_quiz.clicked.connect(self._on_bind_quiz)
        self._btn_stats = QPushButton("Statistik / Logs")
        self._btn_stats.clicked.connect(self._on_statistics)
        self._btn_comments_admin = QPushButton("Kommentare")
        self._btn_comments_admin.clicked.connect(self._on_comments_admin)
        self._btn_doc_tags = QPushButton("Dokument-Tags")
        self._btn_doc_tags.clicked.connect(self._on_set_document_tags)
        self._btn_user_tags = QPushButton("Nutzer-Tags")
        self._btn_user_tags.clicked.connect(self._on_set_user_tags)
        self._btn_rebuild = QPushButton("Snapshots neu aufbauen")
        self._btn_rebuild.clicked.connect(self._on_rebuild_snapshots)
        self._btn_export = QPushButton("Matrix exportieren")
        self._btn_export.clicked.connect(self._on_export_matrix)
        for btn in (
            self._btn_import_quiz,
            self._btn_bind_quiz,
            self._btn_stats,
            self._btn_comments_admin,
            self._btn_doc_tags,
            self._btn_user_tags,
            self._btn_rebuild,
            self._btn_export,
        ):
            admin_row.addWidget(btn)
        admin_row.addStretch(1)
        layout.addWidget(self._admin_bar)

        # --- MIDDLE: Inbox table ---
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "Dokumentenkennung", "Titel", "Status", "Owner", "Freigabe am", "Lesestatus", "Quizstatus",
        ])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table, stretch=3)

        # --- LOWER: Context action bar ---
        lower_bar = QHBoxLayout()
        self._btn_refresh = QPushButton("Aktualisieren")
        self._btn_refresh.clicked.connect(self._load_inbox)
        self._btn_read = QPushButton("Lesen")
        self._btn_read.clicked.connect(self._on_read)
        self._btn_quiz_start = QPushButton("Quiz starten")
        self._btn_quiz_start.clicked.connect(self._on_start_quiz)
        self._btn_quiz_review = QPushButton("Letzte Auswertung")
        self._btn_quiz_review.clicked.connect(self._on_show_last_quiz_review)
        self._btn_comment = QPushButton("Quiz kommentieren")
        self._btn_comment.clicked.connect(self._on_add_comment)
        for btn in (self._btn_refresh, self._btn_read, self._btn_quiz_start, self._btn_quiz_review, self._btn_comment):
            lower_bar.addWidget(btn)
        lower_bar.addStretch(1)
        layout.addLayout(lower_bar)

        # --- Output log ---
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setMaximumHeight(120)
        self._out.setVisible(False)
        self._btn_toggle_log = QPushButton("Protokoll anzeigen")
        self._btn_toggle_log.clicked.connect(self._toggle_log_visibility)
        layout.addWidget(self._btn_toggle_log)
        layout.addWidget(self._out, stretch=1)

        # --- Init ---
        self.refresh_for_session()

    # ---- Role visibility (§13) ----

    def _current_user(self):
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        return user

    def _current_user_or_none(self):
        return self._um.get_current_user()

    def _require_admin_or_qmb(self):
        return require_admin_or_qmb(self._um)

    def refresh_for_session(self) -> None:
        self._apply_role_visibility()
        self._load_inbox()
        self._update_action_state()

    def _apply_role_visibility(self) -> None:
        user = self._current_user_or_none()
        is_admin = self._presenter.is_privileged_for_training(user)
        self._admin_bar.setVisible(is_admin)

    # ---- Selection / action state (§13.2) ----

    def _on_selection_changed(self) -> None:
        row = self._table.currentRow()
        if 0 <= row < len(self._inbox_items):
            self._selected_item = self._inbox_items[row]
        else:
            self._selected_item = None
        self._update_action_state()

    def _update_action_state(self) -> None:
        item = self._selected_item
        self._btn_read.setEnabled(self._presenter.is_read_enabled(item))
        self._btn_quiz_start.setEnabled(self._presenter.is_quiz_start_enabled(item))
        self._btn_quiz_review.setEnabled(item is not None)
        # Comment enabled only if quiz was attempted at least once
        quiz_attempted = False
        if item is not None:
            try:
                quiz_attempted = self._api.list_comments_for_document(item.document_id, item.version) is not None
                # Better check: quiz_attempted from inbox item quiz availability + progress
                quiz_attempted = item.quiz_available and (item.quiz_passed or not self._presenter.is_quiz_start_enabled(item) and item.read_confirmed)
            except Exception:  # noqa: BLE001
                quiz_attempted = False
        self._btn_comment.setEnabled(self._presenter.is_comment_enabled(item, quiz_attempted=quiz_attempted))

    # ---- Load inbox (§9.1) ----

    def _load_inbox(self) -> None:
        user = self._current_user_or_none()
        if user is None:
            self._inbox_items = []
            self._render_table()
            self._out.setPlainText("Anmeldung erforderlich.")
            return
        try:
            raw = self._api.list_training_inbox_for_user(user.user_id, open_only=False)
            self._inbox_items = self._presenter.filter_rows(raw, open_only=False)
            self._render_table()
            self._out.clear()
            self._append_status_log(self._presenter.status_line(rows=len(self._inbox_items), open_only=False))
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _render_table(self) -> None:
        self._table.setRowCount(len(self._inbox_items))
        for i, item in enumerate(self._inbox_items):
            self._table.setItem(i, 0, QTableWidgetItem(item.document_id))
            self._table.setItem(i, 1, QTableWidgetItem(item.title))
            self._table.setItem(i, 2, QTableWidgetItem(item.status))
            self._table.setItem(i, 3, QTableWidgetItem(item.owner_user_id or ""))
            self._table.setItem(i, 4, QTableWidgetItem(str(item.released_at or "")))
            read_text = "✓ gelesen" if item.read_confirmed else "offen"
            self._table.setItem(i, 5, QTableWidgetItem(read_text))
            quiz_text = "✓ bestanden" if item.quiz_passed else ("verfuegbar" if item.quiz_available else "-")
            self._table.setItem(i, 6, QTableWidgetItem(quiz_text))
        self._table.resizeColumnsToContents()
        self._selected_item = None
        self._update_action_state()

    # ---- Read action (§9.2) – via documents_read_api ----

    def _on_read(self) -> None:
        item = self._selected_item
        if item is None:
            return
        try:
            current_user = self._current_user()
            self._read_api.open_released_document_for_training(current_user.user_id, item.document_id, item.version)
            opened_path = self._open_released_pdf(item.document_id, item.version)
            if opened_path is None:
                raise RuntimeError("Kein lokal oeffenbares PDF-Artefakt verfuegbar.")
            dlg = PdfViewerDialog(
                request=PdfViewerRequest(
                    document_id=item.document_id,
                    version=item.version,
                    artifact_path=Path(opened_path),
                    artifact_id=None,
                    actor_user_id=current_user.user_id,
                    actor_role=user_to_system_role(current_user).value,
                    mode="TRAINING_READ",
                    enable_comments=True,
                    enable_read_tracking=True,
                    enable_comment_creation=True,
                    min_seconds_per_page=10,
                ),
                documents_read_api=self._read_api,
                parent=self,
            )
            dlg.exec()
            receipt = self._read_api.get_read_receipt(current_user.user_id, item.document_id, item.version)
            if receipt is None:
                QMessageBox.warning(self, "Training", "Das Dokument wurde noch nicht ausreichend gelesen.")
                return
            self._append_status_log(f"Lesebestaetigung fuer {item.document_id} v{item.version} erstellt.")
            self._load_inbox()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    # ---- Quiz start (§9.3) ----

    def _on_start_quiz(self) -> None:
        item = self._selected_item
        if item is None:
            return
        try:
            session, questions = self._api.start_quiz(
                self._current_user().user_id, item.document_id, item.version,
            )
            dlg = QuizDialog(session, questions, self._api, parent=self)
            dlg.exec()
            self._load_inbox()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_show_last_quiz_review(self) -> None:
        item = self._selected_item
        if item is None:
            return
        try:
            review = self._api.get_last_quiz_review(self._current_user().user_id, item.document_id, item.version)
            if review is None:
                QMessageBox.information(self, "Quiz-Auswertung", "Keine abgeschlossene Auswertung vorhanden.")
                return
            QuizResultDialog(review, self).exec()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    # ---- Comment (§9.4) ----

    def _on_add_comment(self) -> None:
        item = self._selected_item
        if item is None:
            return
        text, ok = QInputDialog.getMultiLineText(self, "Quiz kommentieren", "Kommentar:")
        if not ok or not text.strip():
            return
        try:
            self._api.add_comment(
                self._current_user().user_id, item.document_id, item.version, text.strip(),
                document_title_snapshot=item.title,
                username_snapshot=self._current_user().username,
            )
            self._append_status_log(f"Kommentar für {item.document_id} gespeichert.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    # ---- Admin actions ----

    def _on_import_quiz(self) -> None:
        try:
            self._require_admin_or_qmb()
            path, _ = QFileDialog.getOpenFileName(self, "Quiz-JSON importieren", "", "JSON (*.json)")
            if not path:
                return
            from pathlib import Path
            raw = Path(path).read_bytes()
            preview = self._admin.inspect_quiz_json(raw)
            force = False
            if not preview.version_matches_active:
                warning_text = "\n".join(preview.warnings) or "Version des Quiz passt nicht zur aktiven Dokumentversion."
                reply = QMessageBox.question(
                    self,
                    "Version abweichend",
                    f"{warning_text}\n\nSoll das Quiz trotzdem als gueltig importiert werden?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                force = True
            result = self._admin.import_quiz_json(raw, force=force)
            self._append_status_log(f"Quiz importiert: {result.import_id} ({result.question_count} Fragen)")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_bind_quiz(self) -> None:
        try:
            self._require_admin_or_qmb()
            pending = self._admin.list_pending_quiz_mappings()
            if not pending:
                QMessageBox.information(self, "Quiz zuordnen", "Keine offenen Quiz-Importe vorhanden.")
                return
            dialog = QuizBindingDialog(pending, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            selected = dialog.selected()
            if selected is None:
                return
            p = selected
            # Check replacement conflict
            conflict = self._admin.check_quiz_replacement_conflict(p.document_id, p.document_version, p.import_id)
            if conflict.has_conflict:
                reply = QMessageBox.question(
                    self, "Quiz-Ersetzung",
                    f"Für {p.document_id} v{p.document_version} existiert bereits ein aktives Quiz.\n"
                    "Soll es ersetzt werden?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    result = self._admin.replace_quiz_binding(
                        p.document_id, p.document_version, p.import_id, self._current_user().user_id,
                    )
                    self._append_status_log(f"Quiz ersetzt: {result.old_binding_id} → {result.new_binding_id}")
                return
            binding = self._admin.bind_quiz_to_document(p.import_id, p.document_id, p.document_version)
            self._append_status_log(f"Quiz gebunden: {binding.binding_id}")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_statistics(self) -> None:
        try:
            self._require_admin_or_qmb()
            stats = self._admin.get_training_statistics()
            log_entries = self._admin.list_training_audit_log()
            text = (
                f"Zuweisungen: {stats.total_assignments}  |  "
                f"Abgeschlossen: {stats.completed}  |  "
                f"Offen: {stats.open}  |  "
                f"Fehlgeschlagen: {stats.failed}\n\n"
                f"Letzte {len(log_entries)} Audit-Einträge:\n"
            )
            for entry in log_entries[:20]:
                text += f"  {entry.timestamp}  {entry.action}  {entry.actor_user_id}\n"
            QMessageBox.information(self, "Statistik / Logs", text)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_comments_admin(self) -> None:
        try:
            self._require_admin_or_qmb()
            dlg = TrainingCommentsAdminDialog(self._admin, parent=self)
            dlg.exec()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_set_document_tags(self) -> None:
        try:
            self._require_admin_or_qmb()
            default_doc_id = self._selected_item.document_id if self._selected_item is not None else ""
            docs = self._admin.list_assignable_documents()
            labels = [f"{d.document_id} v{d.version} - {d.title}" for d in docs]
            if labels:
                selected, ok = QInputDialog.getItem(
                    self,
                    "Dokument auswählen",
                    "Dokument:",
                    labels,
                    editable=False,
                )
                if not ok:
                    return
                idx = labels.index(selected)
                doc_id = docs[idx].document_id
            else:
                doc_id, ok = QInputDialog.getText(self, "Dokument-Tags", "Dokument-ID:", text=default_doc_id)
                if not ok or not doc_id.strip():
                    return
            current = self._admin.list_document_tags(doc_id)
            suggestions = self._admin.list_tag_pool()
            tags = self._open_tag_editor_dialog(
                title=f"Dokument-Tags: {doc_id}",
                selected_tags=sorted(current.tags),
                suggestions=suggestions,
            )
            if tags is None:
                return
            updated = self._admin.set_document_tags(doc_id, tags)
            self._append_status_log(f"Dokument-Tags gespeichert: {doc_id} -> {', '.join(sorted(updated.tags)) or '-'}")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_set_user_tags(self) -> None:
        try:
            self._require_admin_or_qmb()
            users = self._um.list_users()
            labels = [f"{u.username} ({u.user_id})" for u in users]
            if not labels:
                QMessageBox.information(self, "Nutzer-Tags", "Keine Benutzer vorhanden.")
                return
            selected, ok = QInputDialog.getItem(
                self,
                "Nutzer auswählen",
                "Benutzer:",
                labels,
                editable=False,
            )
            if not ok:
                return
            idx = labels.index(selected)
            user_id = users[idx].user_id
            current = self._admin.list_user_tags(user_id)
            suggestions = self._admin.list_tag_pool()
            tags = self._open_tag_editor_dialog(
                title=f"Nutzer-Tags: {user_id}",
                selected_tags=sorted(current.tags),
                suggestions=suggestions,
            )
            if tags is None:
                return
            updated = self._admin.set_user_tags(user_id, tags)
            self._append_status_log(f"Nutzer-Tags gespeichert: {user_id} -> {', '.join(sorted(updated.tags)) or '-'}")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_rebuild_snapshots(self) -> None:
        try:
            self._require_admin_or_qmb()
            count = self._admin.rebuild_assignment_snapshots()
            self._append_status_log(f"Snapshots neu aufgebaut: {count} Einträge")
            self._load_inbox()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_export_matrix(self) -> None:
        try:
            self._require_admin_or_qmb()
            result = self._admin.export_training_matrix()
            default_name = f"training_matrix_{result.export_id}.csv"
            path_str, _sel = QFileDialog.getSaveFileName(
                self,
                "Matrix als CSV speichern",
                str(Path.home() / default_name),
                "CSV (*.csv)",
            )
            if path_str:
                out = Path(path_str)
                if out.suffix.lower() != ".csv":
                    out = out.with_suffix(".csv")
                fieldnames = [
                    "user_id",
                    "document_id",
                    "version",
                    "source",
                    "exempted",
                    "read_confirmed_at",
                    "quiz_passed_at",
                    "last_score",
                    "quiz_attempts_count",
                ]
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open("w", encoding="utf-8", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
                    w.writeheader()
                    for row in result.rows:
                        w.writerow({k: row.get(k, "") for k in fieldnames})
                self._append_status_log(
                    f"Matrix exportiert: {result.row_count} Zeilen, Export-ID: {result.export_id} -> {out}"
                )
            else:
                self._append_status_log(
                    f"Matrix erzeugt ({result.row_count} Zeilen, Export-ID: {result.export_id}), "
                    "keine Datei gewaehlt — Daten nur im Speicher / Audit."
                )
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    # ---- Helpers ----

    def _append_status_log(self, msg: str) -> None:
        """Append to the training protocol widget and mirror to the main window status bar."""
        self._out.appendPlainText(msg)
        window = self.window()
        if hasattr(window, "statusBar"):
            try:
                window.statusBar().showMessage(msg, 10000)
            except Exception:  # noqa: BLE001
                self._logger.exception("Training status bar update failed")

    def _show_error(self, exc: Exception) -> None:
        QMessageBox.warning(self, "Training", str(exc))
        self._out.appendPlainText(f"FEHLER: {exc}")
        window = self.window()
        if hasattr(window, "statusBar"):
            try:
                window.statusBar().showMessage(f"FEHLER: {exc}", 10000)
            except Exception:  # noqa: BLE001
                self._logger.exception("Training status bar error update failed")

    def _toggle_log_visibility(self) -> None:
        visible = not self._out.isVisible()
        self._out.setVisible(visible)
        self._btn_toggle_log.setText("Protokoll ausblenden" if visible else "Protokoll anzeigen")

    def _open_tag_editor_dialog(
        self,
        *,
        title: str,
        selected_tags: list[str],
        suggestions: list[str],
    ) -> list[str] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(520)
        editor = TagEditorWidget(selected_tags=selected_tags, suggestions=suggestions, parent=dialog)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout = QVBoxLayout(dialog)
        layout.addWidget(editor)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return editor.selected_tags()

    def _open_released_pdf(self, document_id: str, version: int) -> str | None:
        artifacts = self._pool.list_artifacts(document_id, version)
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
                    return str(path)
        return None

    def _resolve_artifacts_root(self) -> Path:
        return artifacts_root(self._container, self._app_home)


# ---------------------------------------------------------------------------
# Contribution registration
# ---------------------------------------------------------------------------

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
