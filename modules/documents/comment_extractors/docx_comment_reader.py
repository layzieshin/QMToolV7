from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class DocxCommentData:
    docx_comment_id: str
    author: str | None
    created_at: datetime | None
    text: str
    preview_text: str
    source_comment_key: str


class DocxCommentReader:
    _NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    def read_comments(self, artifact_path: Path, *, context: str) -> list[DocxCommentData]:
        if not artifact_path.exists():
            return []
        try:
            with zipfile.ZipFile(artifact_path, "r") as zf:
                if "word/comments.xml" not in zf.namelist():
                    return []
                xml_raw = zf.read("word/comments.xml")
        except Exception:
            return []
        try:
            root = ET.fromstring(xml_raw)
        except Exception:
            return []

        result: list[DocxCommentData] = []
        for node in root.findall(".//w:comment", self._NS):
            comment_id = str(node.attrib.get(f"{{{self._NS['w']}}}id", "")).strip()
            if not comment_id:
                continue
            author = str(node.attrib.get(f"{{{self._NS['w']}}}author", "")).strip() or None
            dt_raw = str(node.attrib.get(f"{{{self._NS['w']}}}date", "")).strip()
            created_at = _parse_w_datetime(dt_raw)
            text = self._extract_comment_text(node).strip()
            if not text:
                continue
            preview = text if len(text) <= 160 else f"{text[:157]}..."
            key = build_source_comment_key(
                context=context,
                docx_comment_id=comment_id,
                author=author,
                created_at=created_at,
                text=text,
            )
            result.append(
                DocxCommentData(
                    docx_comment_id=comment_id,
                    author=author,
                    created_at=created_at,
                    text=text,
                    preview_text=preview,
                    source_comment_key=key,
                )
            )
        return result

    def _extract_comment_text(self, comment_node: ET.Element) -> str:
        parts: list[str] = []
        for text_node in comment_node.findall(".//w:t", self._NS):
            if text_node.text:
                parts.append(text_node.text)
        return " ".join(" ".join(parts).split())


def _parse_w_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        token = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        parsed = datetime.fromisoformat(token)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def build_source_comment_key(
    *,
    context: str,
    docx_comment_id: str,
    author: str | None,
    created_at: datetime | None,
    text: str,
) -> str:
    normalized = " ".join(text.split()).strip()
    text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    author_token = (author or "").strip() or "unknown"
    created_token = (created_at or datetime.now(timezone.utc)).isoformat()
    return f"{context}|{docx_comment_id}|{author_token}|{created_token}|{text_hash}"
