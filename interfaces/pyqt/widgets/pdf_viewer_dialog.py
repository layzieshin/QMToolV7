from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QMouseEvent, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRubberBand,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .pdf_rendering import get_page_count, pixmap_to_qpixmap, render_page
from .pdf_comment_create_dialog import PdfCommentCreateDialog
from interfaces.pyqt.contributions.common import role_to_system_role
from interfaces.pyqt.logging_adapter import get_logger


class _SelectionLabel(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._origin = QPoint()
        self._selection = QRect()
        self._pix_size: tuple[int, int] = (0, 0)
        self._anchor_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._anchor_band.hide()

    def set_pixmap_with_size(self, pixmap: QPixmap, *, width: int, height: int) -> None:
        self.setPixmap(pixmap)
        self._pix_size = (max(1, width), max(1, height))
        self._selection = QRect()
        self._rubber.hide()
        self._anchor_band.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._rubber.setGeometry(QRect(self._origin, self._origin))
            self._rubber.show()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._rubber.isVisible():
            rect = QRect(self._origin, event.position().toPoint()).normalized()
            self._rubber.setGeometry(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._rubber.isVisible():
            self._selection = self._rubber.geometry().normalized()
        super().mouseReleaseEvent(event)

    def selection_anchor_json(self) -> str | None:
        if self._selection.isNull():
            return None
        pw, ph = self._pix_size
        x = max(0.0, min(1.0, self._selection.x() / pw))
        y = max(0.0, min(1.0, self._selection.y() / ph))
        w = max(0.0, min(1.0, self._selection.width() / pw))
        h = max(0.0, min(1.0, self._selection.height() / ph))
        return f'{{"x": {x:.4f}, "y": {y:.4f}, "w": {w:.4f}, "h": {h:.4f}}}'

    def show_anchor_json(self, anchor_json: str | None) -> None:
        self._anchor_band.hide()
        if not anchor_json:
            return
        try:
            anchor = json.loads(anchor_json)
            x = float(anchor.get("x", 0.0))
            y = float(anchor.get("y", 0.0))
            w = float(anchor.get("w", 0.0))
            h = float(anchor.get("h", 0.0))
        except Exception:
            return
        pw, ph = self._pix_size
        rect = QRect(
            int(max(0.0, min(1.0, x)) * pw),
            int(max(0.0, min(1.0, y)) * ph),
            int(max(0.0, min(1.0, w)) * pw),
            int(max(0.0, min(1.0, h)) * ph),
        ).normalized()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        self._anchor_band.setGeometry(rect)
        self._anchor_band.show()


@dataclass(frozen=True)
class PdfViewerRequest:
    document_id: str
    version: int
    artifact_path: Path
    artifact_id: str | None
    actor_user_id: str
    actor_role: str
    mode: str
    enable_comments: bool
    enable_read_tracking: bool
    enable_comment_creation: bool
    min_seconds_per_page: int = 10
    workflow_state: object | None = None


@dataclass(frozen=True)
class _PendingComment:
    page_number: int
    comment_text: str
    anchor_json: str | None


class PdfViewerDialog(QDialog):
    def __init__(
        self,
        *,
        request: PdfViewerRequest,
        documents_read_api: object | None = None,
        documents_comments_api: object | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._log = get_logger(__name__)
        self._request = request
        self._read_api = documents_read_api
        self._comments_api = documents_comments_api
        self._page_count = max(1, get_page_count(request.artifact_path))
        self._page_index = 0
        self._session_id: str | None = None
        self._page_started_at = time.monotonic()
        self._page_seconds: dict[int, int] = {}
        self._pending_comments: list[_PendingComment] = []
        self._build_ui()
        self._render_page()
        self._reload_comments()
        if request.enable_read_tracking and self._read_api is not None:
            session = self._read_api.start_tracked_pdf_read(
                request.actor_user_id,
                request.document_id,
                request.version,
                artifact_id=request.artifact_id,
                total_pages=self._page_count,
                source=request.mode,
                min_seconds_per_page=request.min_seconds_per_page,
            )
            self._session_id = session.session_id

    def _build_ui(self) -> None:
        self.setWindowTitle("PDF Viewer")
        self.setMinimumSize(900, 600)
        self._apply_initial_geometry()
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left.setMinimumWidth(640)
        self._img = _SelectionLabel(self)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._img)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self._scroll, 1)
        nav = QHBoxLayout()
        self._lbl = QLabel("")
        btn_prev = QPushButton("Zurueck")
        btn_next = QPushButton("Weiter")
        btn_prev.clicked.connect(lambda: self._change_page(-1))
        btn_next.clicked.connect(lambda: self._change_page(1))
        nav.addWidget(btn_prev)
        nav.addWidget(btn_next)
        nav.addWidget(self._lbl)
        self._btn_add_comment = QPushButton("Kommentar hinzufuegen")
        self._btn_add_comment.setVisible(self._request.enable_comment_creation and self._comments_api is not None)
        self._btn_add_comment.clicked.connect(self._create_comment)
        nav.addWidget(self._btn_add_comment)
        self._btn_save_finish = QPushButton("Kommentare speichern und beenden")
        self._btn_save_finish.setVisible(self._request.enable_comment_creation and self._comments_api is not None)
        self._btn_save_finish.clicked.connect(self._save_comments_and_close)
        nav.addWidget(self._btn_save_finish)
        left_layout.addLayout(nav)
        splitter.addWidget(left)
        self._comments = QListWidget(self)
        self._comments.setMinimumWidth(260)
        self._comments.setVisible(self._request.enable_comments)
        self._comments.itemClicked.connect(self._on_comment_clicked)
        splitter.addWidget(self._comments)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

    def _render_page(self) -> None:
        pix = render_page(self._request.artifact_path, self._page_index, zoom=1.4)
        self._img.set_pixmap_with_size(pixmap_to_qpixmap(pix), width=pix.width, height=pix.height)
        self._lbl.setText(f"Seite {self._page_index + 1}/{self._page_count}")

    def _apply_initial_geometry(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(1100, 760)
            return
        avail = screen.availableGeometry()
        width = min(max(1100, int(avail.width() * 0.9)), avail.width())
        height = min(max(760, int(avail.height() * 0.9)), avail.height())
        self.resize(width, height)
        self.move(
            avail.x() + max(0, (avail.width() - width) // 2),
            avail.y() + max(0, (avail.height() - height) // 2),
        )
        if self._request.mode in {"WORKFLOW_REVIEW", "WORKFLOW_APPROVAL"}:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def _create_comment(self) -> None:
        if self._comments_api is None:
            return
        dlg = PdfCommentCreateDialog(max_page=self._page_count, parent=self)
        dlg.page.setValue(self._page_index + 1)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        text = dlg.text.toPlainText().strip()
        if not text:
            return
        context = None
        if self._request.mode == "WORKFLOW_REVIEW":
            from modules.documents.contracts import WorkflowCommentContext

            context = WorkflowCommentContext.PDF_REVIEW
        elif self._request.mode == "WORKFLOW_APPROVAL":
            from modules.documents.contracts import WorkflowCommentContext

            context = WorkflowCommentContext.PDF_APPROVAL
        if context is None:
            return
        self._pending_comments.append(
            _PendingComment(
                page_number=dlg.page.value(),
                comment_text=text,
                anchor_json=self._img.selection_anchor_json(),
            )
        )
        self._comments.addItem(f"[DRAFT] S.{dlg.page.value()} - {text[:80]}")

    def _save_comments_and_close(self) -> None:
        if not self._pending_comments:
            self.close()
            return
        if self._comments_api is None:
            return
        context = self._resolve_workflow_context()
        if context is None:
            QMessageBox.warning(self, "Kommentar", "Kein gueltiger Workflow-Kommentarkontext aktiv.")
            return
        try:
            role = role_to_system_role(str(self._request.actor_role))
        except Exception as exc:
            QMessageBox.warning(self, "Kommentar", f"Kommentare konnten nicht gespeichert werden: {exc}")
            return
        state = self._request.workflow_state
        if state is None:
            QMessageBox.warning(self, "Kommentar", "Workflow-Kontext fehlt. Bitte aus der Workflow-Ansicht erneut oeffnen.")
            return
        errors: list[str] = []
        for pending in list(self._pending_comments):
            try:
                self._comments_api.create_pdf_workflow_comment(
                    state,
                    context=context,
                    actor_user_id=self._request.actor_user_id,
                    actor_role=role,
                    page_number=pending.page_number,
                    comment_text=pending.comment_text,
                    anchor_json=pending.anchor_json,
                )
                self._pending_comments.remove(pending)
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        self._reload_comments()
        if errors:
            self._log.warning("Some PDF comments failed to save: %s", errors[:3])
            self._reload_comments()
            QMessageBox.warning(
                self,
                "Kommentar",
                "Einige Kommentare konnten nicht gespeichert werden:\n- " + "\n- ".join(errors[:3]),
            )
            return
        self.close()

    def _resolve_workflow_context(self):
        if self._request.mode == "WORKFLOW_REVIEW":
            from modules.documents.contracts import WorkflowCommentContext

            return WorkflowCommentContext.PDF_REVIEW
        if self._request.mode == "WORKFLOW_APPROVAL":
            from modules.documents.contracts import WorkflowCommentContext

            return WorkflowCommentContext.PDF_APPROVAL
        return None

    def _reload_comments(self) -> None:
        self._comments.clear()
        self._img.show_anchor_json(None)
        if not self._request.enable_comments or self._comments_api is None:
            return
        context = self._resolve_workflow_context()
        if context is None:
            return
        state = self._request.workflow_state
        if state is None:
            return
        try:
            role = role_to_system_role(str(self._request.actor_role))
            rows = self._comments_api.list_workflow_comments(
                state,
                context=context,
                actor_user_id=self._request.actor_user_id,
                actor_role=role,
            )
            for row in rows:
                item = QListWidgetItem(
                    f"{row.ref_no} | {row.status.value} | S.{row.page_number or '-'} | {row.preview_text[:70]}"
                )
                item.setData(Qt.ItemDataRole.UserRole, row)
                self._comments.addItem(item)
        except Exception as exc:  # noqa: BLE001
            self._comments.addItem(f"Kommentare konnten nicht geladen werden: {exc}")

    def _on_comment_clicked(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.ItemDataRole.UserRole)
        if row is None:
            return
        page = getattr(row, "page_number", None)
        if isinstance(page, int) and 1 <= page <= self._page_count:
            self._flush_page_time()
            self._page_index = page - 1
            self._page_started_at = time.monotonic()
            self._render_page()
        self._img.show_anchor_json(getattr(row, "anchor_json", None))

    def _change_page(self, delta: int) -> None:
        next_idx = min(max(0, self._page_index + delta), self._page_count - 1)
        if next_idx == self._page_index:
            return
        self._flush_page_time()
        self._page_index = next_idx
        self._page_started_at = time.monotonic()
        self._render_page()

    def _flush_page_time(self) -> None:
        elapsed = int(max(0.0, time.monotonic() - self._page_started_at))
        page_no = self._page_index + 1
        self._page_seconds[page_no] = self._page_seconds.get(page_no, 0) + elapsed
        if self._session_id and self._read_api is not None:
            self._read_api.record_page_dwell(
                self._session_id, page_number=page_no, dwell_seconds=elapsed
            )

    def closeEvent(self, event) -> None:  # noqa: N802
        self._flush_page_time()
        if self._session_id and self._read_api is not None:
            self._read_api.finalize_tracked_pdf_read(self._session_id, source=self._request.mode)
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            if self._pending_comments:
                answer = QMessageBox.question(
                    self,
                    "Ungespeicherte Kommentare",
                    "Es gibt ungespeicherte Kommentare. Jetzt speichern und beenden?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes,
                )
                if answer == QMessageBox.StandardButton.Cancel:
                    return
                if answer == QMessageBox.StandardButton.Yes:
                    self._save_comments_and_close()
                    return
            if self.isMaximized():
                self.showNormal()
                return
            self.close()
            return
        super().keyPressEvent(event)
