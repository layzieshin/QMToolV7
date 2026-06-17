from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESENTER = ROOT / "interfaces" / "pyqt" / "presenters" / "incident_management_presenter.py"
PYQT_ROOT = ROOT / "interfaces" / "pyqt"


def test_presenter_has_no_qmb_queue_filter() -> None:
    source = PRESENTER.read_text(encoding="utf-8")
    assert "filter_qmb_queue" not in source
    assert "IncidentStatus" not in source


def test_pyqt_has_no_internal_incident_ops_imports() -> None:
    pattern = re.compile(
        r"from modules\.incident_management\.(service|sqlite_repository|\w+_ops|capa_rules|status_transitions)"
    )
    offenders: list[str] = []
    for path in PYQT_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
