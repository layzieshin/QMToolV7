"""Persistent settings for the internal license issuer GUI."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


def _default_config_dir() -> Path:
    appdata = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if appdata:
        return Path(appdata) / "QM-Tool-LicenseIssuer"
    return Path.home() / ".qm-tool-license-issuer"


@dataclass
class IssuerSettings:
    private_key_pem: str = ""
    output_dir: str = ""
    last_customer_id: str = ""
    last_issued_to: str = ""
    last_preset_id: str = "trial_30"
    issue_log_path: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> IssuerSettings:
        config_path = path or (_default_config_dir() / "config.json")
        if not config_path.is_file():
            return cls(issue_log_path=str(_default_config_dir() / "issues.jsonl"))
        data = json.loads(config_path.read_text(encoding="utf-8"))
        settings = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if not settings.issue_log_path:
            settings.issue_log_path = str(_default_config_dir() / "issues.jsonl")
        return settings

    def save(self, path: Path | None = None) -> Path:
        config_dir = path.parent if path else _default_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = path or (config_dir / "config.json")
        config_path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=True), encoding="utf-8")
        return config_path

    def append_issue_log(self, entry: dict) -> None:
        log_path = Path(self.issue_log_path or (_default_config_dir() / "issues.jsonl"))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
