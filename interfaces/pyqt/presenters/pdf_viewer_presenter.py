from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ViewerCommentRow:
    ref_no: str
    status: str
    page_number: int | None
    author: str | None
    created_at: str
    preview: str
