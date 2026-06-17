from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECTIONS_DIR = ROOT / "interfaces" / "pyqt" / "contributions" / "incident_management_sections"
VIEWS = ROOT / "interfaces" / "pyqt" / "contributions" / "incident_management_views.py"
PRESENTER = ROOT / "interfaces" / "pyqt" / "presenters" / "incident_management_presenter.py"
PYQT_ROOT = ROOT / "interfaces" / "pyqt"

REQUIRED_SECTION_MODULES = (
    "submit_section.py",
    "my_incidents_section.py",
    "register_section.py",
    "qmb_review_section.py",
    "inquiries_section.py",
    "actions_section.py",
    "capa_section.py",
    "effectiveness_section.py",
    "reports_section.py",
    "management_review_section.py",
    "settings_section.py",
    "leadership_section.py",
)

API_QUERY_MARKERS = (
    "list_qmb_review_queue",
    "list_open_inquiries",
    "list_open_actions",
    "list_capa_relevant_incidents",
    "list_pending_effectiveness_reviews",
    "list_leadership_queue",
    "list_my_incidents",
)


def test_incident_management_sections_exist() -> None:
    for name in REQUIRED_SECTION_MODULES:
        assert (SECTIONS_DIR / name).is_file(), f"missing section module: {name}"


def test_views_no_simple_count_placeholder() -> None:
    source = VIEWS.read_text(encoding="utf-8")
    assert "_SimpleCountArea" not in source
    assert "Eintraege: {count}" not in source


def test_sections_use_dedicated_api_queries() -> None:
    combined = ""
    for path in SECTIONS_DIR.glob("*.py"):
        combined += path.read_text(encoding="utf-8")
    for marker in API_QUERY_MARKERS:
        assert marker in combined, f"expected API query usage: {marker}"


def test_sections_do_not_client_filter_incidents_for_queues() -> None:
    offenders: list[str] = []
    for path in SECTIONS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "list_incidents(" in text and any(marker in text for marker in API_QUERY_MARKERS):
            offenders.append(path.name)
    assert offenders == []


def test_presenter_has_no_role_or_status_logic() -> None:
    source = PRESENTER.read_text(encoding="utf-8")
    assert "is_qmb_or_admin" not in source
    assert "IncidentStatus" not in source
    assert "filter_qmb_queue" not in source


def test_pyqt_has_no_internal_incident_imports() -> None:
    pattern = re.compile(r"from modules\.incident_management\.(service|sqlite_repository|\w+_ops|capa_rules|status_transitions)")
    offenders: list[str] = []
    for path in PYQT_ROOT.rglob("*.py"):
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
