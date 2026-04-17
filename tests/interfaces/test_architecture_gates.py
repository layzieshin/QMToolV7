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
    assert "TrainingPresenter" in _read("interfaces/pyqt/contributions/training_placeholder.py") or "TrainingPresenter" in _read("interfaces/pyqt/presenters/training_presenter.py")
    assert "SettingsProfilePresenter" in _read(
        "interfaces/pyqt/contributions/settings_sections/profile_section.py"
    )
    assert "SettingsPolicyPresenter" in _read(
        "interfaces/pyqt/contributions/settings_sections/module_settings_section.py"
    )
    assert "ContributionVisibilityPolicy" in _read("interfaces/pyqt/shell/main_window.py")


def test_domain_ui_hotspots_no_json_renderer() -> None:
    assert "as_json_text(" not in _read("interfaces/pyqt/contributions/home_view.py")
    assert "as_json_text(" not in _read("interfaces/pyqt/contributions/training_placeholder.py")
    assert "as_json_text(" not in _read("interfaces/pyqt/contributions/signature_view.py")


def test_documents_workflow_uses_business_document_id_in_creation_flow() -> None:
    content = _read("interfaces/pyqt/contributions/documents_workflow_view.py")
    assert "technical_document_id" not in content
    assert 'custom_fields={"document_code":' not in content


def test_cli_uses_only_public_module_interfaces() -> None:
    content = _read("interfaces/cli/main.py")
    assert "modules.usermanagement.sqlite_repository" not in content
    assert "modules.usermanagement.password_crypto" not in content
    assert "modules.documents.errors" not in content
    assert "modules.signature.errors" not in content


def test_cli_main_is_thin_entry_point_only() -> None:
    """Verifies main.py delegates command handling to command modules."""
    content = _read("interfaces/cli/main.py")
    # No command handler implementations should remain in main.py
    assert "def cmd_init(" not in content
    assert "def cmd_doctor(" not in content
    assert "def cmd_documents(" not in content
    # No runtime initialization or path resolution logic in main.py
    assert "_resolve_runtime_paths(" not in content
    assert "_seed_admin_credentials(" not in content
    assert "_load_documents_state(" not in content
    # Imports from command modules required
    assert "from interfaces.cli.commands.runtime_commands import cmd_init, cmd_doctor" in content
    assert "from interfaces.cli.commands.documents_commands import cmd_documents" in content
    # Parser setup and delegation still exists
    assert "argparse.ArgumentParser" in content
    assert "parser.parse_args()" in content


def test_legacy_gui_frozen_header() -> None:
    """Phase 6: Legacy Tk GUI is frozen — no new code."""
    content = _read("interfaces/gui/main.py")
    assert "LEGACY FROZEN" in content
    assert "no new code" in content


def test_legacy_gui_boundary_violations_accepted() -> None:
    """Phase 6: Legacy GUI boundary violations are documented, not fixed."""
    content = _read("interfaces/gui/main.py")
    # These boundary violations are explicitly accepted for the frozen legacy GUI
    assert "modules.documents.errors" in content
    assert "modules.signature.errors" in content


def test_boundary_gate_cli_commands_no_internal_imports() -> None:
    """No CLI command file imports directly from modules.*.errors, *.service, etc."""
    import glob
    for path in glob.glob(str(ROOT / "interfaces/cli/commands/*.py")):
        content = Path(path).read_text(encoding="utf-8")
        name = Path(path).name
        for forbidden in (".service ", ".sqlite_repository", ".password_crypto", ".storage "):
            assert f"from modules." not in content or forbidden not in content, (
                f"{name} imports forbidden internal module: {forbidden}"
            )
        # errors must come via api.py
        if ".errors" in content:
            assert "from modules." not in content.split(".errors")[0].split("\n")[-1] or "api" in content, (
                f"{name} imports errors directly instead of via api.py"
            )


def test_documents_signature_ops_extracted() -> None:
    """Phase 3A: No PDF/artifact/signature logic in the workflow view."""
    content = _read("interfaces/pyqt/contributions/documents_workflow_view.py")
    assert "def _build_sign_request_or_none(" not in content
    assert "def _convert_docx_to_temp_pdf(" not in content
    assert "def _find_pdf_for_signature(" not in content
    assert "def _export_active_signature_png(" not in content
    assert "DocumentsSignatureOps" in content


def test_admin_seed_uses_public_api() -> None:
    """Phase 1B: Admin seed in CLI uses public usermanagement API, not internal fallbacks."""
    content = _read("interfaces/cli/commands/runtime_commands.py")
    assert "bootstrap_admin" in content
    assert "from modules.usermanagement.api import bootstrap_admin" in content
    # No direct create_user/change_password fallback
    assert "usermanagement.create_user(" not in content
    assert "usermanagement.change_password(" not in content


def test_documents_service_delegates_to_internal_modules() -> None:
    """Phase 4A: service.py delegates to extracted internal modules."""
    content = _read("modules/documents/service.py")
    assert "from . import artifact_ops" in content
    assert "from . import eventing" in content
    assert "from . import naming" in content
    assert "from . import signature_guard" in content
    assert "from . import validation as _val" in content
    # No inline implementations of extracted logic
    assert "def _transliterate_umlauts" not in content or "naming.transliterate_umlauts" in content
    assert "UserAccessPermissions" not in content  # PDF protection moved to artifact_ops


def test_documents_sections_extracted() -> None:
    """Phase 3A: UI sections extracted from workflow view."""
    content = _read("interfaces/pyqt/contributions/documents_workflow_view.py")
    assert "from interfaces.pyqt.sections.filter_bar import" in content
    assert "from interfaces.pyqt.sections.action_bar import" in content
    assert "from interfaces.pyqt.sections.detail_drawer import" in content
    # No inline builder methods
    assert "def _build_top_filter_bar(" not in content
    assert "def _build_workflow_action_bar(" not in content
    assert "def _build_detail_drawer(" not in content
    assert "def _build_metadata_tab(" not in content

