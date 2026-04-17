"""Shared signature composition preview for settings UIs (no page-absolute placement)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QLabel, QPlainTextEdit

from interfaces.pyqt.widgets.signature_placement_dialog import compute_label_local_position
from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput


def render_signature_settings_preview(
    *,
    placement: SignaturePlacementInput,
    layout: LabelLayoutInput,
    profile_name_display: str,
    preview_sig_pixmap: QPixmap | None,
    preview_canvas: QLabel,
    preview_text: QPlainTextEdit,
) -> None:
    """Draw composition preview onto canvas and update the summary plain text."""
    preview_w, preview_h = 520, 215
    pixmap = QPixmap(preview_w, preview_h)
    pixmap.fill(QColor("#e6e6e6"))
    painter = QPainter(pixmap)

    area_x, area_y = 20, 16
    area_w, area_h = 480, 180
    painter.fillRect(area_x, area_y, area_w, area_h, QColor("white"))
    painter.setPen(QPen(QColor("#7a7a7a"), 2))
    painter.drawRect(area_x, area_y, area_w, area_h)

    scale = 1.0
    sig_w = max(1, int(placement.target_width * scale))
    sig_h = max(1, int(max(6.0, placement.target_width * 0.3) * scale))
    max_preview_width = int(area_w * 0.58)
    if sig_w > max_preview_width:
        scale = max_preview_width / max(1, sig_w)
        sig_w = max(1, int(placement.target_width * scale))
        sig_h = max(1, int(max(6.0, placement.target_width * 0.3) * scale))

    sig_x = area_x + max(12, int(area_w * 0.18))
    sig_y = area_y + max(18, int((area_h - sig_h) * 0.48))

    if preview_sig_pixmap is not None:
        painter.drawPixmap(sig_x, sig_y, sig_w, sig_h, preview_sig_pixmap)
    else:
        painter.fillRect(sig_x, sig_y, sig_w, sig_h, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QColor("#cc0000"), 2, Qt.PenStyle.DashLine))
        painter.drawRect(sig_x, sig_y, max(1, sig_w - 1), max(1, sig_h - 1))

    painter.setPen(QPen(QColor("#aaaaaa"), 1, Qt.PenStyle.DashLine))
    painter.drawRect(sig_x, sig_y, sig_w, sig_h)

    name_pos = layout.name_position
    date_pos = layout.date_position
    name_fs = max(6, int(layout.name_font_size or 12))
    date_fs = max(6, int(layout.date_font_size or 12))
    color = QColor(layout.color_hex or "#000000")
    if not color.isValid():
        color = QColor("black")

    if layout.show_name and name_pos != "off":
        font = QFont()
        name_px = max(6, int(name_fs * scale * 0.85))
        font.setPixelSize(name_px)
        painter.setFont(font)
        painter.setPen(color)
        name_local = compute_label_local_position(
            position=name_pos,
            sig_height=float(sig_h),
            pixel_size=name_px,
            scale=scale,
            rel_x=layout.name_rel_x,
            rel_y=layout.name_rel_y,
            offset_above=layout.name_above,
            offset_below=layout.name_below,
            x_offset=layout.x_offset,
        )
        painter.drawText(
            int(sig_x + name_local.x()),
            int(sig_y + name_local.y() + name_px),
            layout.name_text or "",
        )

    if layout.show_date and date_pos != "off":
        font = QFont()
        date_px = max(6, int(date_fs * scale * 0.85))
        font.setPixelSize(date_px)
        painter.setFont(font)
        painter.setPen(color)
        date_local = compute_label_local_position(
            position=date_pos,
            sig_height=float(sig_h),
            pixel_size=date_px,
            scale=scale,
            rel_x=layout.date_rel_x,
            rel_y=layout.date_rel_y,
            offset_above=layout.date_above,
            offset_below=layout.date_below,
            x_offset=layout.x_offset,
        )
        painter.drawText(
            int(sig_x + date_local.x()),
            int(sig_y + date_local.y() + date_px),
            layout.date_text or "",
        )

    painter.end()
    preview_canvas.setPixmap(pixmap)

    preview_text.setPlainText(
        "\n".join(
            [
                f"Profil: {profile_name_display}",
                f"Gespeicherte Seite: {placement.page_index}",
                f"Gespeicherte Position: x={placement.x}, y={placement.y}",
                f"Signaturbreite: {placement.target_width}",
                f"Name: {'an' if layout.show_name else 'aus'} ({name_pos}, {name_fs}pt)",
                f"Datum: {'an' if layout.show_date else 'aus'} ({date_pos}, {date_fs}pt)",
                f"Name rel: x={layout.name_rel_x if layout.name_rel_x is not None else '-'}, y={layout.name_rel_y if layout.name_rel_y is not None else '-'}",
                f"Datum rel: x={layout.date_rel_x if layout.date_rel_x is not None else '-'}, y={layout.date_rel_y if layout.date_rel_y is not None else '-'}",
            ]
        )
    )
