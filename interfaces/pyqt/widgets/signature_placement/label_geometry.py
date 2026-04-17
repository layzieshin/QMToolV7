"""Map label anchor math to scene-local coordinates (previews + placement dialog)."""
from __future__ import annotations

from typing import cast

from PyQt6.QtCore import QPointF

from modules.signature.layout_math import resolve_label_pdf_anchor


def compute_label_local_position(
    *,
    position: str,
    sig_height: float,
    pixel_size: int,
    scale: float,
    rel_x: float | None,
    rel_y: float | None,
    offset_above: float,
    offset_below: float,
    x_offset: float,
) -> QPointF:
    pdf_x, pdf_y = resolve_label_pdf_anchor(
        placement_x=0.0,
        placement_y=0.0,
        signature_height=sig_height,
        position=cast("Literal['above', 'below', 'off']", position),
        offset_above=offset_above,
        offset_below=offset_below,
        x_offset=x_offset,
        rel_x=rel_x,
        rel_y=rel_y,
    )
    local_x = pdf_x * scale
    local_y = (sig_height - pdf_y) * scale - float(pixel_size)
    return QPointF(local_x, local_y)
