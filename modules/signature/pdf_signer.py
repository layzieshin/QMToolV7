from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Optional, cast

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .layout_math import compute_target_height, resolve_label_pdf_anchor
from .visual_models import LabelOffsets, LabelPosition, SignaturePlacement


@dataclass
class RenderLabels:
    name_text: Optional[str]
    date_text: Optional[str]
    name_pos: LabelPosition
    date_pos: LabelPosition
    date_format: str
    offsets: LabelOffsets
    color_rgb: tuple[int, int, int] = (0, 0, 0)
    name_font_size: int = 12
    date_font_size: int = 12
    name_rel_x: float | None = None
    name_rel_y: float | None = None
    date_rel_x: float | None = None
    date_rel_y: float | None = None


class PdfSigner:
    @staticmethod
    def _make_overlay(
        page_w: float,
        page_h: float,
        png_signature: bytes,
        placement: SignaturePlacement,
        labels: Optional[RenderLabels],
    ) -> bytes:
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(page_w, page_h))

        sig = Image.open(BytesIO(png_signature)).convert("RGBA")
        aspect = sig.height / sig.width if sig.width > 0 else 0.3
        target_w = float(placement.target_width)
        target_h = compute_target_height(target_w, signature_aspect=aspect)
        c.drawImage(ImageReader(sig), placement.x, placement.y, width=target_w, height=target_h, mask="auto")

        if labels:
            r, g, b = labels.color_rgb

            if labels.name_text and labels.name_pos != LabelPosition.OFF:
                x, y = resolve_label_pdf_anchor(
                    placement_x=placement.x,
                    placement_y=placement.y,
                    signature_height=target_h,
                    position=cast("Literal['above', 'below', 'off']", labels.name_pos.value),
                    offset_above=labels.offsets.name_above,
                    offset_below=labels.offsets.name_below,
                    x_offset=labels.offsets.x_offset,
                    rel_x=labels.name_rel_x,
                    rel_y=labels.name_rel_y,
                )
                c.setFillColorRGB(r / 255.0, g / 255.0, b / 255.0)
                c.setFont("Helvetica-Bold", max(6, int(labels.name_font_size)))
                c.drawString(x, y, labels.name_text)

            if labels.date_text and labels.date_pos != LabelPosition.OFF:
                x, y = resolve_label_pdf_anchor(
                    placement_x=placement.x,
                    placement_y=placement.y,
                    signature_height=target_h,
                    position=cast("Literal['above', 'below', 'off']", labels.date_pos.value),
                    offset_above=labels.offsets.date_above,
                    offset_below=labels.offsets.date_below,
                    x_offset=labels.offsets.x_offset,
                    rel_x=labels.date_rel_x,
                    rel_y=labels.date_rel_y,
                )
                c.setFillColorRGB(r / 255.0, g / 255.0, b / 255.0)
                c.setFont("Helvetica-Bold", max(6, int(labels.date_font_size)))
                c.drawString(x, y, labels.date_text)

        c.save()
        return buf.getvalue()

    @staticmethod
    def sign_pdf(
        *,
        input_path: str,
        output_path: str,
        png_signature: bytes,
        placement: SignaturePlacement,
        labels: Optional[RenderLabels],
    ) -> None:
        reader = PdfReader(input_path)
        writer = PdfWriter()

        for i, page in enumerate(reader.pages):
            if i == placement.page_index:
                box = page.mediabox
                w, h = float(box.width), float(box.height)
                overlay_pdf = PdfSigner._make_overlay(w, h, png_signature, placement, labels)
                overlay_reader = PdfReader(BytesIO(overlay_pdf))
                page.merge_page(overlay_reader.pages[0])
            writer.add_page(page)

        with open(output_path, "wb") as fh:
            writer.write(fh)
