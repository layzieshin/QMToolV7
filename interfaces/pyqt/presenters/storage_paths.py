from __future__ import annotations

from pathlib import Path

def platform_logs_root(app_home: Path) -> Path:
    return app_home / "storage" / "platform" / "logs"
