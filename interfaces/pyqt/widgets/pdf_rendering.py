from __future__ import annotations

import importlib
from pathlib import Path

from PyQt6.QtGui import QImage, QPixmap


def _fitz():
    return importlib.import_module("fitz")


def get_page_count(path: Path) -> int:
    fitz = _fitz()
    with fitz.open(str(path)) as doc:
        return len(doc)


def render_page(path: Path, page_index: int, zoom: float = 1.5):
    fitz = _fitz()
    with fitz.open(str(path)) as doc:
        page = doc.load_page(page_index)
        return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)


def pixmap_to_qpixmap(pix) -> QPixmap:
    image = QImage(
        pix.samples,
        pix.width,
        pix.height,
        pix.stride,
        QImage.Format.Format_RGB888,
    )
    return QPixmap.fromImage(image)
