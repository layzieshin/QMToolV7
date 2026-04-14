from __future__ import annotations

from interfaces.pyqt.registry.catalog import all_contributions


def _by_title():
    return {item.title: item for item in all_contributions()}


def test_pyqt_navigation_contains_expected_entries() -> None:
    titles = set(_by_title().keys())
    assert {
        "Start",
        "Dokumentenlenkung",
        "Dokumente",
        "Signatur",
        "Schulung",
        "Einstellungen",
        "Audit & Logs",
        "Admin/Debug",
    }.issubset(titles)


def test_pyqt_role_restrictions_for_sensitive_views() -> None:
    by_title = _by_title()
    assert by_title["Audit & Logs"].allowed_roles == ("Admin", "QMB")
    assert by_title["Admin/Debug"].allowed_roles == ("Admin",)


def test_users_view_is_embedded_not_top_level() -> None:
    ids = {item.contribution_id for item in all_contributions()}
    assert "platform.users_admin" not in ids
