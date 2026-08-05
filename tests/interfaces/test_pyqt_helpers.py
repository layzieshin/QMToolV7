from __future__ import annotations

from datetime import datetime, timezone

from interfaces.pyqt.contributions.common import normalize_role
from interfaces.pyqt.presenters.formatting import format_local

def test_normalize_role_is_case_insensitive() -> None:
    assert normalize_role("admin") == "ADMIN"
    assert normalize_role(" qmb ") == "QMB"
    assert normalize_role(None) == ""


def test_format_local_uses_timezone() -> None:
    dt = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    rendered = format_local(dt)
    assert isinstance(rendered, str)
    assert len(rendered) >= 16
