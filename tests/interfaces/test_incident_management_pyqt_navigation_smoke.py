from __future__ import annotations

from interfaces.pyqt.registry.catalog import all_contributions


def test_incident_management_single_shell_entry() -> None:
    by_id = {item.contribution_id: item for item in all_contributions()}
    assert "incident_management.workspace" in by_id
    item = by_id["incident_management.workspace"]
    assert item.title == "Fehler und Abweichung"
    assert item.module_id == "incident_management"
    assert item.allowed_roles == ("Admin", "QMB", "User")

    legacy_ids = {
        "incident_management.report_event",
        "incident_management.my_incidents",
        "incident_management.register",
        "incident_management.qmb_review",
        "incident_management.inquiries",
        "incident_management.actions",
        "incident_management.capa",
        "incident_management.effectiveness",
        "incident_management.reports",
        "incident_management.management_review",
        "incident_management.settings",
        "incident_management.leadership",
    }
    ids = {c.contribution_id for c in all_contributions()}
    assert legacy_ids.isdisjoint(ids)


def test_incident_management_area_specs_cover_planned_areas() -> None:
    from interfaces.pyqt.contributions.incident_management_views import _AREA_SPECS

    area_ids = {spec[0] for spec in _AREA_SPECS}
    assert area_ids == {
        "report_event",
        "my_incidents",
        "register",
        "qmb_review",
        "inquiries",
        "actions",
        "capa",
        "effectiveness",
        "reports",
        "management_review",
        "leadership",
        "settings",
    }
