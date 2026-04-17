from __future__ import annotations

from typing import Literal

TextPosition = Literal["above", "below", "off"]


def compute_target_height(target_width: float, *, signature_aspect: float | None) -> float:
    """Return a stable target height used by preview and final PDF rendering."""
    width = max(1.0, float(target_width))
    if signature_aspect is None or signature_aspect <= 0:
        signature_aspect = 0.3
    return max(6.0, width * signature_aspect)


def resolve_label_pdf_anchor(
    *,
    placement_x: float,
    placement_y: float,
    signature_height: float,
    position: TextPosition,
    offset_above: float,
    offset_below: float,
    x_offset: float,
    rel_x: float | None,
    rel_y: float | None,
) -> tuple[float, float]:
    """Return label anchor in PDF coordinates.

    rel_x/rel_y use signature-local PDF units with origin at signature lower-left.
    """
    x = placement_x + x_offset
    if position == "above":
        y = placement_y + signature_height + offset_above
    elif position == "below":
        y = placement_y - offset_below
    else:
        y = placement_y
    if rel_x is not None:
        x += float(rel_x)
    if rel_y is not None:
        y += float(rel_y)
    return x, y

