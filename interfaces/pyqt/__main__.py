from __future__ import annotations

import importlib.util
import site
import sys
from pathlib import Path


def _ensure_pyqt6_importable() -> None:
    if importlib.util.find_spec("PyQt6") is not None and importlib.util.find_spec("PyQt6.sip") is not None:
        return

    exe = Path(sys.executable).resolve()
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        exe.parent.parent / "Lib" / "site-packages",
        project_root / ".venv" / "Lib" / "site-packages",
    ]

    # Prefer venv site-packages early in sys.path so PyQt6 and PyQt6.sip resolve consistently.
    inserted = False
    normalized_sys_path = [Path(p).resolve() for p in sys.path if p]
    for candidate in candidates:
        if candidate.exists() and candidate.resolve() not in normalized_sys_path:
            sys.path.insert(0, str(candidate))
            inserted = True

    added = False
    for candidate in candidates:
        if candidate.exists():
            site.addsitedir(str(candidate))
            added = True

    if inserted or added:
        importlib.invalidate_caches()


if __name__ == "__main__":
    _ensure_pyqt6_importable()
    from interfaces.pyqt.main import main

    raise SystemExit(main())
