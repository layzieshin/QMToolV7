from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass
class LogQueryService:
    platform_log_file: Path
    audit_log_file: Path

    def query_audit(
        self,
        *,
        limit: int = 400,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        return self._read_jsonl(self.audit_log_file, limit=limit, date_from=date_from, date_to=date_to)

    def query_technical_logs(
        self,
        *,
        limit: int = 400,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        return self._read_jsonl(self.platform_log_file, limit=limit, date_from=date_from, date_to=date_to)

    def export_audit_csv(
        self,
        output_path: Path,
        *,
        limit: int = 2000,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Path:
        return self._export_csv(output_path, self.query_audit(limit=limit, date_from=date_from, date_to=date_to))

    def export_logs_csv(
        self,
        output_path: Path,
        *,
        limit: int = 2000,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Path:
        return self._export_csv(
            output_path,
            self.query_technical_logs(limit=limit, date_from=date_from, date_to=date_to),
        )

    def export_audit_pdf(
        self,
        output_path: Path,
        *,
        limit: int = 2000,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Path:
        rows = self.query_audit(limit=limit, date_from=date_from, date_to=date_to)
        return self._export_pdf_report(
            output_path,
            title="Audit-Log",
            rows=rows,
            headers=["Zeit", "Aktion", "Benutzer", "Ziel", "Ergebnis", "Begruendung"],
            keys=["timestamp_utc", "action", "actor", "target", "result", "reason"],
            date_from=date_from,
            date_to=date_to,
        )

    def export_logs_pdf(
        self,
        output_path: Path,
        *,
        limit: int = 2000,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Path:
        rows = self.query_technical_logs(limit=limit, date_from=date_from, date_to=date_to)
        return self._export_pdf_report(
            output_path,
            title="Technische Logs",
            rows=rows,
            headers=["Zeit", "Level", "Modul", "Nachricht"],
            keys=["timestamp_utc", "level", "module", "message"],
            date_from=date_from,
            date_to=date_to,
        )

    def _read_jsonl(
        self,
        path: Path,
        *,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                ts = self._timestamp_utc(parsed)
                if date_from is not None and (ts is None or ts < date_from):
                    continue
                if date_to is not None and (ts is None or ts >= date_to):
                    continue
                rows.append(parsed)
        return rows[-max(limit, 1) :]

    @staticmethod
    def _as_aware_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _timestamp_utc(cls, row: dict[str, Any]) -> datetime | None:
        raw = row.get("timestamp_utc")
        if raw is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw))
        except Exception:
            return None
        return cls._as_aware_utc(parsed)

    @classmethod
    def _timestamp_local_text(cls, row: dict[str, Any]) -> str:
        parsed = cls._timestamp_utc(row)
        if parsed is None:
            return str(row.get("timestamp_utc", ""))
        return parsed.astimezone().strftime("%d.%m.%Y %H:%M:%S")

    @staticmethod
    def _export_csv(output_path: Path, rows: list[dict[str, Any]]) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        keys: list[str] = sorted({key for row in rows for key in row.keys()})
        with output_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=keys)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key) for key in keys})
        return output_path

    @classmethod
    def _export_pdf_report(
        cls,
        output_path: Path,
        *,
        title: str,
        rows: list[dict[str, Any]],
        headers: list[str],
        keys: list[str],
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=landscape(A4),
            leftMargin=24,
            rightMargin=24,
            topMargin=24,
            bottomMargin=24,
        )
        styles = getSampleStyleSheet()
        body = styles["BodyText"]
        body.fontSize = 8

        def period_text() -> str:
            if date_from is None and date_to is None:
                return "Zeitraum: Alle Daten"
            from_text = (
                cls._as_aware_utc(date_from).astimezone().strftime("%d.%m.%Y")
                if date_from is not None
                else "-"
            )
            to_dt = cls._as_aware_utc(date_to).astimezone() if date_to is not None else None
            to_text = to_dt.strftime("%d.%m.%Y") if to_dt is not None else "-"
            return f"Zeitraum: {from_text} - {to_text}"

        table_rows: list[list[Paragraph]] = [[Paragraph(f"<b>{head}</b>", body) for head in headers]]
        for row in rows:
            rendered: list[Paragraph] = []
            for idx, key in enumerate(keys):
                if idx == 0 and key == "timestamp_utc":
                    text = cls._timestamp_local_text(row)
                else:
                    text = str(row.get(key, ""))
                rendered.append(Paragraph(text, body))
            table_rows.append(rendered)

        story = [
            Paragraph(f"<b>{title}</b>", styles["Heading2"]),
            Paragraph(period_text(), body),
            Paragraph(f"Erstellt am: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}", body),
            Paragraph(f"Zeilen: {len(rows)}", body),
            Spacer(1, 8),
        ]
        table = Table(table_rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return output_path
