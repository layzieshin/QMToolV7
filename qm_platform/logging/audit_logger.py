from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class AuditLogger:
    audit_file: Path

    def emit(self, action: str, actor: str, target: str, result: str, reason: str = "") -> None:
        payload: dict[str, Any] = {
            "audit_id": str(uuid4()),
            "action": action,
            "actor": actor,
            "target": target,
            "result": result,
            "reason": reason,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")

