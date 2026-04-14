from __future__ import annotations

import os
import sys
from pathlib import Path
import re


def runtime_home() -> Path:
    configured = os.environ.get("QMTOOL_HOME", "").strip()
    if configured:
        if configured.lower().startswith("microsoft.powershell.core\\filesystem::"):
            configured = configured.split("::", 1)[1]
        return Path(configured).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def resource_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path.cwd().resolve()


def resolve_home_path(app_home: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    # Accept Windows absolute paths even when running tests on non-Windows hosts.
    if candidate.is_absolute() or re.match(r"^[a-zA-Z]:[\\/]", raw_path) or raw_path.startswith("\\\\"):
        return candidate
    return app_home / candidate


def path_writable(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        probe = path.parent / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False
