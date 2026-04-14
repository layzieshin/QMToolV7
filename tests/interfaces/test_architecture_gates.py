from __future__ import annotations

from pathlib import Path

from interfaces.pyqt.registry import catalog


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_home_dashboard_routes_by_contribution_id() -> None:
    content = _read("interfaces/pyqt/contributions/home_view.py")
    assert "navigate_to_contribution" in content
    assert "target_title" not in content


def test_dashboard_targets_exist_in_catalog() -> None:
    from interfaces.pyqt.presenters.home_presenter import HomeDashboardPresenter

    known = {item.contribution_id for item in catalog.all_contributions()}
    for contribution_id in HomeDashboardPresenter.CARD_TARGETS.values():
        assert contribution_id in known


def test_hotspots_use_presenter_layer() -> None:
    assert "DocumentsWorkflowPresenter" in _read("interfaces/pyqt/contributions/documents_workflow_view.py")
    assert "DocumentsWorkflowFilterPresenter" in _read("interfaces/pyqt/contributions/documents_workflow_view.py")
    assert "TrainingPresenter" in _read("interfaces/pyqt/contributions/training_placeholder.py")
    assert "SettingsProfilePresenter" in _read("interfaces/pyqt/contributions/settings_view.py")
    assert "SettingsPolicyPresenter" in _read("interfaces/pyqt/contributions/settings_view.py")
    assert "ContributionVisibilityPolicy" in _read("interfaces/pyqt/shell/main_window.py")


def test_domain_ui_hotspots_no_json_renderer() -> None:
    assert "as_json_text(" not in _read("interfaces/pyqt/contributions/home_view.py")
    assert "as_json_text(" not in _read("interfaces/pyqt/contributions/training_placeholder.py")
    assert "as_json_text(" not in _read("interfaces/pyqt/contributions/signature_view.py")
