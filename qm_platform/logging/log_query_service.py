from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LogQueryService:
    platform_log_file: Path
    audit_log_file: Path

    def query_audit(self, *, limit: int = 400) -> list[dict[str, Any]]:
        return self._read_jsonl(self.audit_log_file, limit=limit)

    def query_technical_logs(self, *, limit: int = 400) -> list[dict[str, Any]]:
        return self._read_jsonl(self.platform_log_file, limit=limit)

    def export_audit_csv(self, output_path: Path, *, limit: int = 2000) -> Path:
        return self._export_csv(output_path, self.query_audit(limit=limit))

    def export_logs_csv(self, output_path: Path, *, limit: int = 2000) -> Path:
        return self._export_csv(output_path, self.query_technical_logs(limit=limit))

    def export_audit_pdf(self, output_path: Path, *, limit: int = 2000) -> Path:
        return self._export_text_report(output_path, self.query_audit(limit=limit))

    def export_logs_pdf(self, output_path: Path, *, limit: int = 2000) -> Path:
        return self._export_text_report(output_path, self.query_technical_logs(limit=limit))

    def _read_jsonl(self, path: Path, *, limit: int) -> list[dict[str, Any]]:
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
                rows.append(parsed)
        return rows[-max(limit, 1) :]

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

    @staticmethod
    def _export_text_report(output_path: Path, rows: list[dict[str, Any]]) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for row in rows:
            lines.append(json.dumps(row, ensure_ascii=True))
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path
