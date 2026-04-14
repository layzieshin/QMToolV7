from __future__ import annotations

import importlib
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from modules.signature.contracts import SignaturePlacementInput


class SignaturePlacementDialog(QDialog):
    def __init__(self, *, input_pdf: Path, placement: SignaturePlacementInput, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PDF-Platzierungsvorschau")
        self._input_pdf = input_pdf
        self._page = QSpinBox()
        self._x = QLineEdit(str(placement.x))
        self._y = QLineEdit(str(placement.y))
        self._width = QLineEdit(str(placement.target_width))
        self._info = QLabel("")
        self._info.setWordWrap(True)
        self._render_error = QLabel("")
        self._render_error.setWordWrap(True)
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self)
        self._view.setScene(self._scene)
        self._view.setMinimumHeight(360)
        self._pdf_item: QGraphicsPixmapItem | None = None
        self._placement_item: QGraphicsRectItem | None = None

        page_count = self._read_page_count(input_pdf)
        self._page.setMinimum(0)
        self._page.setMaximum(max(0, page_count - 1))
        self._page.setValue(min(max(0, placement.page_index), max(0, page_count - 1)))

        form = QFormLayout()
        form.addRow("Seite", self._page)
        form.addRow("X", self._x)
        form.addRow("Y", self._y)
        form.addRow("Breite", self._width)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"PDF: {input_pdf}"))
        layout.addWidget(self._info)
        layout.addWidget(self._render_error)
        layout.addWidget(self._view)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._update_info()
        self._render_page_with_overlay()
        self._page.valueChanged.connect(lambda _v: self._on_inputs_changed())
        self._x.textChanged.connect(lambda _v: self._on_inputs_changed())
        self._y.textChanged.connect(lambda _v: self._on_inputs_changed())
        self._width.textChanged.connect(lambda _v: self._on_inputs_changed())

    def _read_page_count(self, input_pdf: Path) -> int:
        try:
            fitz = importlib.import_module("fitz")
            with fitz.open(str(input_pdf)) as doc:
                return max(1, int(doc.page_count))
        except Exception:
            try:
                reader_mod = importlib.import_module("pypdf")
                PdfReader = getattr(reader_mod, "PdfReader")
                return len(PdfReader(str(input_pdf)).pages)
            except Exception:
                return 1

    def _update_info(self) -> None:
        self._info.setText(
            "Platzierungsvorschau: Signaturkomposition wird auf der gewaehlten Seite mit den "
            f"Koordinaten x={self._x.text().strip()}, y={self._y.text().strip()} und Breite={self._width.text().strip()} angewendet."
        )

    def _on_inputs_changed(self) -> None:
        self._update_info()
        self._render_page_with_overlay()

    def _render_page_with_overlay(self) -> None:
        self._scene.clear()
        self._pdf_item = None
        self._placement_item = None
        self._render_error.clear()
        try:
            fitz = importlib.import_module("fitz")
            with fitz.open(str(self._input_pdf)) as doc:
                page_index = int(self._page.value())
                if page_index < 0 or page_index >= doc.page_count:
                    raise RuntimeError(f"Ungueltiger Seitenindex {page_index}")
                page = doc.load_page(page_index)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                fmt = QImage.Format.Format_RGB888
                image = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
                pixmap = QPixmap.fromImage(image)
                self._pdf_item = self._scene.addPixmap(pixmap)

                x = float(self._x.text().strip() or "0")
                y = float(self._y.text().strip() or "0")
                target_width = float(self._width.text().strip() or "120")
                target_height = max(6.0, target_width * 0.3)

                page_w = float(page.rect.width)
                scale = pix.width / page_w if page_w > 0 else 1.0
                rect_x = x * scale
                rect_w = target_width * scale
                rect_h = target_height * scale
                rect_y = pix.height - ((y + target_height) * scale)

                self._placement_item = QGraphicsRectItem(rect_x, rect_y, rect_w, rect_h)
                self._placement_item.setPen(QPen(QColor("red"), 2))
                self._placement_item.setBrush(Qt.BrushStyle.NoBrush)
                self._scene.addItem(self._placement_item)
                self._view.fitInView(self._scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        except Exception as exc:  # noqa: BLE001
            self._render_error.setText(f"Visuelle PDF-Vorschau nicht verfuegbar: {exc}")

    def placement(self) -> SignaturePlacementInput:
        return SignaturePlacementInput(
            page_index=int(self._page.value()),
            x=float(self._x.text().strip() or "0"),
            y=float(self._y.text().strip() or "0"),
            target_width=float(self._width.text().strip() or "120"),
        )
