from __future__ import annotations

import ast
from pathlib import Path

from interfaces.pyqt.registry import catalog


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _pyqt_production_files() -> list[Path]:
    return sorted((ROOT / "interfaces" / "pyqt").rglob("*.py"))


def _documents_pyqt_files() -> list[Path]:
    base = ROOT / "interfaces" / "pyqt"
    candidates = [
        base / "contributions" / "documents_pool_view.py",
        base / "contributions" / "training_workspace.py",
        base / "contributions" / "documents_workflow_view.py",
        base / "presenters" / "documents_signature_ops.py",
    ]
    candidates.extend((base / "contributions" / "documents_workflow").rglob("*.py"))
    candidates.extend(base.glob("presenters/documents_*.py"))
    return sorted({path for path in candidates if path.exists()})


def _declared_contribution_ids(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "QtModuleContribution":
            continue
        for keyword in node.keywords:
            if keyword.arg == "contribution_id" and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, str):
                    ids.add(keyword.value.value)
    return ids


def _contributions_returns_empty_list(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "contributions":
            continue
        returns = [child for child in node.body if isinstance(child, ast.Return)]
        return len(returns) == 1 and isinstance(returns[0].value, ast.List) and returns[0].value.elts == []
    return False


def test_pyqt_contribution_modules_are_registered_or_explicitly_embedded() -> None:
    """Top-level contribution modules must not drift out of the shell catalog."""
    catalog_ids = {item.contribution_id for item in catalog.all_contributions()}
    contributions_root = ROOT / "interfaces" / "pyqt" / "contributions"
    explicit_non_catalog_modules = {
        "training_placeholder.py": "legacy compatibility wrapper",
        "users_view.py": "embedded in settings_view",
    }

    missing: list[str] = []
    for path in sorted(contributions_root.glob("*.py")):
        if path.name in explicit_non_catalog_modules:
            continue
        declared_ids = _declared_contribution_ids(path)
        if not declared_ids:
            continue
        missing_ids = sorted(declared_ids - catalog_ids)
        if missing_ids:
            missing.append(f"{path.relative_to(ROOT)} -> {missing_ids}")

    assert missing == []
    assert _declared_contribution_ids(contributions_root / "training_placeholder.py") == set()
    assert _contributions_returns_empty_list(contributions_root / "users_view.py")
    assert "platform.users_admin" not in catalog_ids


def test_catalog_contribution_ids_and_titles_unique() -> None:
    """Shell navigation entries must have unique IDs and titles."""
    items = catalog.all_contributions()
    ids = [item.contribution_id for item in items]
    titles = [item.title for item in items]
    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    duplicate_titles = sorted({item for item in titles if titles.count(item) > 1})
    assert duplicate_ids == [], f"duplicate contribution_id values: {duplicate_ids}"
    assert duplicate_titles == [], f"duplicate navigation titles: {duplicate_titles}"


def test_catalog_imports_declared_contribution_modules() -> None:
    """Top-level contribution modules with IDs must be imported in catalog.py."""
    catalog_source = _read("interfaces/pyqt/registry/catalog.py")
    contributions_root = ROOT / "interfaces" / "pyqt" / "contributions"
    explicit_non_catalog_modules = {
        "training_placeholder.py",
        "users_view.py",
    }
    missing_imports: list[str] = []
    for path in sorted(contributions_root.glob("*.py")):
        if path.name in explicit_non_catalog_modules or path.name == "__init__.py":
            continue
        if not _declared_contribution_ids(path):
            continue
        if path.stem not in catalog_source:
            missing_imports.append(str(path.relative_to(ROOT)))
    assert missing_imports == []


def _workflow_action_bar_labels() -> set[str]:
    content = _read("interfaces/pyqt/sections/action_bar.py")
    labels: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if '", on_' in stripped or "', on_" in stripped:
            for quote in ('"', "'"):
                if quote in stripped:
                    label = stripped.split(quote)[1]
                    if label:
                        labels.add(label)
    return labels


def test_documents_workflow_does_not_duplicate_central_action_bar_labels() -> None:
    """Workflow view/sections must not re-create buttons owned by sections/action_bar.py."""
    labels = _workflow_action_bar_labels()
    assert labels, "expected workflow action labels in action_bar.py"
    offenders: list[str] = []
    for path in _documents_pyqt_files():
        if "sections" in path.parts:
            continue
        content = path.read_text(encoding="utf-8")
        for label in labels:
            if f'QPushButton("{label}")' in content or f"QPushButton('{label}')" in content:
                offenders.append(f"{path.relative_to(ROOT)} -> {label}")
    assert offenders == []


ALLOWED_PRODUCT_ENTRYPOINTS = frozenset({
    "interfaces/cli/main.py",
    "interfaces/pyqt/main.py",
    "interfaces/pyqt/__main__.py",
    "interfaces/gui/main.py",
    "src/backend/__main__.py",
})


def test_allowed_product_entrypoints_only() -> None:
    """Product areas may only expose documented entrypoint files."""
    found: set[str] = set()
    for root in (ROOT / "interfaces", ROOT / "src" / "backend"):
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if path.name in {"main.py", "__main__.py"}:
                found.add(path.relative_to(ROOT).as_posix())
    unexpected = sorted(found - ALLOWED_PRODUCT_ENTRYPOINTS)
    assert unexpected == [], f"unexpected entrypoints: {unexpected}"


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
    assert "TrainingPresenter" in _read("interfaces/pyqt/contributions/training_workspace.py") or "TrainingPresenter" in _read("interfaces/pyqt/presenters/training_presenter.py")
    assert "SettingsProfilePresenter" in _read(
        "interfaces/pyqt/contributions/settings_sections/profile_section.py"
    )
    assert "SettingsPolicyPresenter" in _read(
        "interfaces/pyqt/contributions/settings_sections/module_settings_section.py"
    )
    assert "ContributionVisibilityPolicy" in _read("interfaces/pyqt/shell/main_window.py")


def test_domain_ui_hotspots_no_json_renderer() -> None:
    assert "as_json_text(" not in _read("interfaces/pyqt/contributions/home_view.py")
    assert "as_json_text(" not in _read("interfaces/pyqt/contributions/training_workspace.py")
    assert "as_json_text(" not in _read("interfaces/pyqt/contributions/signature_view.py")


def test_training_workspace_remains_composition_only() -> None:
    """Training workspace composes sections; feature handlers belong to those sections."""
    content = _read("interfaces/pyqt/contributions/training_workspace.py")
    tree = ast.parse(content)

    forbidden_functions = {
        # Admin-section handlers must stay in training_sections/admin_section.py.
        "_on_import_quiz",
        "_on_bind_quiz",
        "_on_statistics",
        "_on_comments_admin",
        "_on_set_document_tags",
        "_on_set_user_tags",
        "_on_rebuild_snapshots",
        "_on_export_matrix",
        "_open_tag_editor_dialog",
        # Inbox table state/rendering must stay in training_sections/inbox_section.py.
        "_load_inbox",
        "load_inbox",
        "_render_table",
        "_on_selection_changed",
        "current_item",
        "row_count",
        # User-action handlers must stay in training_sections/user_actions_section.py.
        "_on_read",
        "_open_released_pdf",
        "_on_start_quiz",
        "_on_show_last_quiz_review",
        "_on_add_comment",
    }
    forbidden_self_attrs = {
        "_inbox_items",
        "_selected_item",
        "_btn_read",
        "_btn_quiz_start",
        "_btn_quiz_review",
        "_btn_comment",
        "_btn_import_quiz",
        "_btn_bind_quiz",
        "_btn_stats",
        "_btn_comments_admin",
        "_btn_doc_tags",
        "_btn_user_tags",
        "_btn_rebuild",
        "_btn_export",
        "_btn_refresh",
        "_table",
    }
    forbidden_imports_or_calls = {
        # Direct table/layout/dialog widgets owned by the extracted sections.
        "QDialog",
        "QDialogButtonBox",
        "QFileDialog",
        "QHBoxLayout",
        "QInputDialog",
        "QTableWidget",
        "QTableWidgetItem",
        "PdfViewerDialog",
        "PdfViewerRequest",
        "QuizDialog",
        "QuizBindingDialog",
        "QuizResultDialog",
        "TagEditorWidget",
        "TrainingCommentsAdminDialog",
    }

    function_offenders = sorted(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in forbidden_functions
    )
    attr_offenders = sorted(
        {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr in forbidden_self_attrs
        }
    )
    import_or_call_offenders = sorted(
        {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id in forbidden_imports_or_calls
        }
    )

    assert function_offenders == []
    assert attr_offenders == []
    assert import_or_call_offenders == []
    assert "class TrainingWorkspace(" in content
    assert "TrainingAdminSection" in content
    assert "TrainingInboxSection" in content
    assert "TrainingUserActionsSection" in content
    assert "def _build(" in content
    assert "def contributions(" in content


def test_training_placeholder_is_thin_compatibility_wrapper() -> None:
    """The legacy placeholder module must only re-export the canonical training workspace."""
    content = _read("interfaces/pyqt/contributions/training_placeholder.py")
    tree = ast.parse(content)

    executable_nodes = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.ImportFrom)
            or isinstance(node, ast.Assign)
            or (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
        )
    ]
    import_from_modules = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module != "__future__"
    }
    workspace_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "interfaces.pyqt.contributions.training_workspace"
    ]
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)]
    defined_functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    defined_classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]

    assert executable_nodes == []
    assert import_from_modules == {"interfaces.pyqt.contributions.training_workspace"}
    assert len(workspace_imports) == 1
    assert {alias.name for alias in workspace_imports[0].names} == {
        "TrainingWorkspace",
        "_build",
        "contributions",
    }
    assert len(assignments) == 1
    assert len(assignments[0].targets) == 1
    assert isinstance(assignments[0].targets[0], ast.Name)
    assert assignments[0].targets[0].id == "__all__"
    assert isinstance(assignments[0].value, ast.List)
    assert [item.value for item in assignments[0].value.elts if isinstance(item, ast.Constant)] == [
        "TrainingWorkspace",
        "_build",
        "contributions",
    ]
    assert defined_functions == []
    assert defined_classes == []
    assert calls == []
    assert "TrainingWorkspace" in content
    assert "_build" in content
    assert "contributions" in content


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


def test_boundary_gate_cli_commands_no_broad_module_service_ports() -> None:
    """CLI commands use public module APIs instead of broad Documents/Signature service ports."""
    content = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "interfaces" / "cli" / "commands").glob("*.py")
    )
    assert 'get_port("documents_service")' not in content
    assert 'get_port("signature_service")' not in content


def test_boundary_gate_pyqt_no_broad_documents_service_port() -> None:
    """PyQt uses specialized Documents APIs instead of the broad Documents service port."""
    offenders: list[str] = []
    for path in _pyqt_production_files():
        content = path.read_text(encoding="utf-8")
        if 'get_port("documents_service")' in content:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_boundary_gate_pyqt_no_documents_artifact_path_helper_imports() -> None:
    """Documents artifact path resolution belongs to documents_artifacts_api."""
    assert not (ROOT / "interfaces/pyqt/presenters/artifact_paths.py").exists()
    for path in _pyqt_production_files():
        content = path.read_text(encoding="utf-8")
        assert "interfaces.pyqt.presenters.artifact_paths" not in content, (
            f"{path.relative_to(ROOT)} imports the old PyQt artifact path helper"
        )


def test_boundary_gate_pyqt_no_documents_artifact_storage_paths() -> None:
    """PyQt must not know concrete Documents artifact storage paths."""
    for path in _pyqt_production_files():
        content = path.read_text(encoding="utf-8")
        assert "storage/documents/artifacts" not in content, (
            f"{path.relative_to(ROOT)} contains Documents artifact storage path details"
        )


def test_boundary_gate_documents_pyqt_no_storage_key_path_logic() -> None:
    """Documents PyQt code must use documents_artifacts_api instead of storage_key path logic."""
    for path in _documents_pyqt_files():
        content = path.read_text(encoding="utf-8")
        assert "storage_key" not in content, f"{path.relative_to(ROOT)} still references Documents storage_key"
        assert "artifacts_root" not in content, f"{path.relative_to(ROOT)} still references Documents artifacts_root"


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


def test_backend_uses_only_usermanagement_public_api() -> None:
    """src/backend may import modules.usermanagement.api only — no internals."""
    forbidden_markers = (
        "modules.usermanagement.service",
        "modules.usermanagement.sqlite_repository",
        "modules.usermanagement.postgres_",
        "modules.usermanagement.session_ops",
        "modules.usermanagement.session_store",
        "modules.usermanagement.auth_ops",
        "modules.usermanagement.password_crypto",
        "modules.usermanagement.memory_session",
        "modules.usermanagement.repository",
        "modules.usermanagement.wiring",
        "modules.usermanagement.module",
        "modules.usermanagement.cutover_",
        "UserManagementService",
        "SessionStore",
        "current_user.json",
        "get_current_user",
        "sqlite3",
        "import sqlite",
    )
    offenders: list[str] = []
    backend_root = ROOT / "src" / "backend"
    for path in sorted(backend_root.rglob("*.py")):
        content = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for marker in forbidden_markers:
            if marker in content:
                offenders.append(f"{rel} -> {marker}")
        if "from modules.usermanagement." in content and "modules.usermanagement.api" not in content:
            if "from modules.usermanagement import api" not in content:
                offenders.append(f"{rel} -> non-api usermanagement import")
    assert offenders == [], offenders


def test_backend_auth_path_uses_public_resolve_session() -> None:
    """Backend auth resolve must call um_api.resolve_session; routes use public facades."""
    deps = _read("src/backend/auth_dependencies.py")
    assert "um_api.resolve_session(" in deps
    assert "get_current_user" not in deps
    assert "SessionStore" not in deps
    assert "current_user.json" not in deps

    routes = _read("src/backend/auth_routes.py")
    assert "um_api.login_backend(" in routes
    assert "um_api.logout_backend(" in routes
    assert "um_api.change_own_password(" in routes
    assert "um_api.revoke_all_own_sessions(" in routes
    assert "get_current_user" not in routes
    assert "SessionStore" not in routes

    admin = _read("src/backend/user_admin_routes.py")
    assert "um_api.create_user_as_admin(" in admin
    assert "um_api.update_user_access_as_admin(" in admin
    assert "get_current_user" not in admin
    assert "SessionStore" not in admin

