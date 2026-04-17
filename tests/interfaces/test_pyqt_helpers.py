from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from interfaces.pyqt.contributions.common import normalize_role
from interfaces.pyqt.presenters.formatting import format_local
from interfaces.pyqt.presenters.storage_paths import artifacts_root


class _FakeSettingsService:
    def __init__(self, docs_settings: dict[str, object]) -> None:
        self._docs_settings = docs_settings

    def get_module_settings(self, module_id: str) -> dict[str, object]:
        if module_id != "documents":
            return {}
        return dict(self._docs_settings)


class _FakeContainer:
    def __init__(self, docs_settings: dict[str, object] | None = None) -> None:
        self._settings = _FakeSettingsService(docs_settings or {})

    def has_port(self, port_name: str) -> bool:
        return port_name == "settings_service"

    def get_port(self, port_name: str):
        if port_name == "settings_service":
            return self._settings
        raise KeyError(port_name)


def test_normalize_role_is_case_insensitive() -> None:
    assert normalize_role("admin") == "ADMIN"
    assert normalize_role(" qmb ") == "QMB"
    assert normalize_role(None) == ""


def test_format_local_uses_timezone() -> None:
    dt = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    rendered = format_local(dt)
    assert isinstance(rendered, str)
    assert len(rendered) >= 16


def test_artifacts_root_respects_settings_override(tmp_path: Path) -> None:
    container = _FakeContainer({"artifacts_root": "custom/artifacts"})
    root = artifacts_root(container, tmp_path)
    assert root == (tmp_path / "custom" / "artifacts")
