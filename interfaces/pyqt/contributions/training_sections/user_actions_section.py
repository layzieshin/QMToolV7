from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtWidgets import QHBoxLayout, QInputDialog, QMessageBox, QPushButton, QWidget

from interfaces.pyqt.contributions.common import user_to_system_role
from interfaces.pyqt.widgets.pdf_viewer_dialog import PdfViewerDialog, PdfViewerRequest
from interfaces.pyqt.widgets.quiz_dialogs import QuizDialog, QuizResultDialog


class TrainingUserActionsSection(QWidget):
    def __init__(
        self,
        *,
        training_api: object,
        documents_read_api: object,
        documents_artifacts_api: object,
        usermanagement_service: object,
        presenter: object,
        current_item_provider: Callable[[], object | None],
        reload_inbox: Callable[[], None],
        append_status_log: Callable[[str], None],
        show_error: Callable[[Exception], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._api = training_api
        self._read_api = documents_read_api
        self._artifacts = documents_artifacts_api
        self._um = usermanagement_service
        self._presenter = presenter
        self._current_item_provider = current_item_provider
        self._reload_inbox = reload_inbox
        self._append_status_log = append_status_log
        self._show_error = show_error

        lower_bar = QHBoxLayout(self)
        lower_bar.setContentsMargins(0, 0, 0, 0)
        self._btn_refresh = QPushButton("Aktualisieren")
        self._btn_refresh.clicked.connect(self._reload_inbox)
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

    def update_action_state(self) -> None:
        item = self._current_item()
        self._btn_read.setEnabled(self._presenter.is_read_enabled(item))
        self._btn_quiz_start.setEnabled(self._presenter.is_quiz_start_enabled(item))
        self._btn_quiz_review.setEnabled(item is not None)
        quiz_attempted = False
        if item is not None:
            try:
                quiz_attempted = self._api.list_comments_for_document(item.document_id, item.version) is not None
                quiz_attempted = item.quiz_available and (
                    item.quiz_passed
                    or not self._presenter.is_quiz_start_enabled(item)
                    and item.read_confirmed
                )
            except Exception:  # noqa: BLE001
                quiz_attempted = False
        self._btn_comment.setEnabled(self._presenter.is_comment_enabled(item, quiz_attempted=quiz_attempted))

    def _current_user(self):
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        return user

    def _current_item(self):
        return self._current_item_provider()

    def _on_read(self) -> None:
        item = self._current_item()
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
            self._reload_inbox()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_start_quiz(self) -> None:
        item = self._current_item()
        if item is None:
            return
        try:
            session, questions = self._api.start_quiz(
                self._current_user().user_id,
                item.document_id,
                item.version,
            )
            dlg = QuizDialog(session, questions, self._api, parent=self)
            dlg.exec()
            self._reload_inbox()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_show_last_quiz_review(self) -> None:
        item = self._current_item()
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

    def _on_add_comment(self) -> None:
        item = self._current_item()
        if item is None:
            return
        text, ok = QInputDialog.getMultiLineText(self, "Quiz kommentieren", "Kommentar:")
        if not ok or not text.strip():
            return
        try:
            current_user = self._current_user()
            self._api.add_comment(
                current_user.user_id,
                item.document_id,
                item.version,
                text.strip(),
                document_title_snapshot=item.title,
                username_snapshot=current_user.username,
            )
            self._append_status_log(f"Kommentar fuer {item.document_id} gespeichert.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _open_released_pdf(self, document_id: str, version: int) -> str | None:
        ref = self._artifacts.get_released_pdf_for_reading(document_id, version)
        if ref is not None and hasattr(os, "startfile"):
            os.startfile(str(ref.path))  # type: ignore[attr-defined]
            return str(ref.path)
        return None
