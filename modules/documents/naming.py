"""Document filename building and transliteration.

Internal module — extracted from service.py (Phase 4A).
"""
from __future__ import annotations


from .contracts import DocumentVersionState


def build_released_filename(state: DocumentVersionState) -> str:
    title = transliterate_umlauts((state.title or "").strip().replace(" ", "_"))
    safe_title = "".join(ch for ch in title if ch.isalnum() or ch in ("_", "-")).strip("_-")
    if not safe_title:
        safe_title = "Dokument"
    return f"{state.document_id}_{safe_title}.pdf"


def transliterate_umlauts(raw: str) -> str:
    return (
        raw.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
        .replace("ß", "ss")
    )

