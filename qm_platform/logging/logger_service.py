from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LoggerService:
    log_file: Path

    def _write(self, level: str, module: str, message: str, context: dict[str, Any] | None = None) -> None:
        payload = {
            "timestamp_utc": utc_now_iso(),
            "level": level,
            "module": module,
            "message": message,
            "correlation_id": str(uuid4()),
            "context": context or {},
        }
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def info(self, module: str, message: str, context: dict[str, Any] | None = None) -> None:
        self._write("INFO", module, message, context)

    def warning(self, module: str, message: str, context: dict[str, Any] | None = None) -> None:
        self._write("WARNING", module, message, context)

    def error(self, module: str, message: str, context: dict[str, Any] | None = None) -> None:
        self._write("ERROR", module, message, context)

