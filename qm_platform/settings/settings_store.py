from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SettingsStore:
    file_path: Path

    def load_all(self) -> dict[str, Any]:
        if not self.file_path.exists():
            return {}
        return json.loads(self.file_path.read_text(encoding="utf-8"))

    def save_all(self, data: dict[str, Any]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")

