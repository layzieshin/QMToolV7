"""Document filename building and transliteration.

Internal module — extracted from service.py (Phase 4A).
"""
from __future__ import annotations


from .contracts import DocumentVersionState


def build_released_filename(state: DocumentVersionState) -> str:
    doc_part = _safe_filename_token(state.document_id, fallback="Dokument")
    title_part = _safe_filename_token(state.title, fallback="Dokument")
    return f"{doc_part}_{title_part}.pdf"


def _safe_filename_token(raw: str, *, fallback: str) -> str:
    text = transliterate_umlauts((raw or "").strip().replace(" ", "_"))
    text = text.replace("/", "_").replace("\\", "_").replace(":", "_").replace("..", "_")
    safe = "".join(ch for ch in text if ch.isalnum() or ch in ("_", "-")).strip("_-")
    return safe or fallback


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
