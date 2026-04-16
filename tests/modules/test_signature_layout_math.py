from __future__ import annotations

from modules.signature.layout_math import compute_target_height, resolve_label_pdf_anchor


def test_compute_target_height_uses_signature_aspect() -> None:
    assert compute_target_height(120.0, signature_aspect=0.5) == 60.0


def test_compute_target_height_falls_back_to_default_aspect() -> None:
    assert compute_target_height(100.0, signature_aspect=None) == 30.0


def test_resolve_label_pdf_anchor_uses_relative_offsets_when_present() -> None:
    x, y = resolve_label_pdf_anchor(
        placement_x=100.0,
        placement_y=200.0,
        signature_height=36.0,
        position="above",
        offset_above=6.0,
        offset_below=12.0,
        x_offset=0.0,
        rel_x=10.0,
        rel_y=5.0,
    )
    assert (x, y) == (110.0, 205.0)


def test_resolve_label_pdf_anchor_below_uses_offsets_without_relative() -> None:
    x, y = resolve_label_pdf_anchor(
        placement_x=100.0,
        placement_y=200.0,
        signature_height=36.0,
        position="below",
        offset_above=6.0,
        offset_below=12.0,
        x_offset=8.0,
        rel_x=None,
        rel_y=None,
    )
    assert (x, y) == (108.0, 188.0)

