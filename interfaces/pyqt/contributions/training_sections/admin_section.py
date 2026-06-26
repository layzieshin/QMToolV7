from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.widgets.access_guards import require_admin_or_qmb
from interfaces.pyqt.widgets.quiz_binding_dialog import QuizBindingDialog
from interfaces.pyqt.widgets.tag_editor_widget import TagEditorWidget
from interfaces.pyqt.widgets.training_comments_admin_dialog import TrainingCommentsAdminDialog


class TrainingAdminSection(QWidget):
    def __init__(
        self,
        *,
        training_admin_api: object,
        usermanagement_service: object,
        selected_item_provider: Callable[[], object | None],
        reload_inbox: Callable[[], None],
        append_status_log: Callable[[str], None],
        show_error: Callable[[Exception], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._admin = training_admin_api
        self._um = usermanagement_service
        self._selected_item_provider = selected_item_provider
        self._reload_inbox = reload_inbox
        self._append_status_log = append_status_log
        self._show_error = show_error

        admin_row = QHBoxLayout(self)
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

    def _require_admin_or_qmb(self):
        return require_admin_or_qmb(self._um)

    def _selected_item(self):
        return self._selected_item_provider()

    def _on_import_quiz(self) -> None:
        try:
            self._require_admin_or_qmb()
            path, _ = QFileDialog.getOpenFileName(self, "Quiz-JSON importieren", "", "JSON (*.json)")
            if not path:
                return
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
            conflict = self._admin.check_quiz_replacement_conflict(p.document_id, p.document_version, p.import_id)
            if conflict.has_conflict:
                reply = QMessageBox.question(
                    self,
                    "Quiz-Ersetzung",
                    f"Fuer {p.document_id} v{p.document_version} existiert bereits ein aktives Quiz.\n"
                    "Soll es ersetzt werden?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    user = self._require_admin_or_qmb()
                    result = self._admin.replace_quiz_binding(
                        p.document_id,
                        p.document_version,
                        p.import_id,
                        user.user_id,
                    )
                    self._append_status_log(f"Quiz ersetzt: {result.old_binding_id} -> {result.new_binding_id}")
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
                f"Letzte {len(log_entries)} Audit-Eintraege:\n"
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
            selected_item = self._selected_item()
            default_doc_id = selected_item.document_id if selected_item is not None else ""
            docs = self._admin.list_assignable_documents()
            labels = [f"{d.document_id} v{d.version} - {d.title}" for d in docs]
            if labels:
                selected, ok = QInputDialog.getItem(
                    self,
                    "Dokument auswaehlen",
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
                "Nutzer auswaehlen",
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
            self._append_status_log(f"Snapshots neu aufgebaut: {count} Eintraege")
            self._reload_inbox()
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
                    "keine Datei gewaehlt - Daten nur im Speicher / Audit."
                )
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

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
