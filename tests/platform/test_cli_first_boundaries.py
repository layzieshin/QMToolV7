from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIVE_DIRS = (
    ROOT / "interfaces",
    ROOT / "modules",
    ROOT / "qm_platform",
    ROOT / "src" / "backend",
    ROOT / "tests",
)
FORBIDDEN_TEXT_IMPORT_FRAGMENTS = (
    "from core.",
    "import core",
    "from framework.",
    "import framework",
)
FORBIDDEN_LEGACY_SIGNATURE_STRINGS = (
    '"signature.logic.',
    "'signature.logic.",
    '"signature.models.',
    "'signature.models.",
)
ALLOWLIST_FILES = {
    # This test contains the forbidden fragments by design.
    (ROOT / "tests" / "platform" / "test_cli_first_boundaries.py").resolve(),
}


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for directory in ACTIVE_DIRS:
        if not directory.exists():
            continue
        files.extend(path for path in directory.rglob("*.py") if path.is_file())
    return files


def _is_forbidden_legacy_documents_module(module_name: str | None) -> bool:
    if not module_name:
        return False
    return module_name == "documents" or module_name.startswith("documents.")


def legacy_documents_import_violations(source: str) -> list[str]:
    """Return AST-based violations for top-level legacy ``documents`` imports."""
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_legacy_documents_module(alias.name):
                    violations.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if _is_forbidden_legacy_documents_module(node.module):
                imported = ", ".join(alias.name for alias in node.names)
                violations.append(f"from {node.module} import {imported}")
    return violations


def test_legacy_documents_ast_allows_documents_commands_import() -> None:
    source = "from interfaces.cli.commands import documents_commands\n"
    assert legacy_documents_import_violations(source) == []


def test_legacy_documents_ast_forbids_top_level_documents_import() -> None:
    assert legacy_documents_import_violations("import documents\n") == ["import documents"]
    assert legacy_documents_import_violations("import documents.foo\n") == ["import documents.foo"]
    assert legacy_documents_import_violations("from documents import api\n") == [
        "from documents import api"
    ]
    assert legacy_documents_import_violations("from documents.legacy import x\n") == [
        "from documents.legacy import x"
    ]


def test_legacy_documents_ast_ignores_comments_and_docstrings() -> None:
    source = '''"""Mentions import documents only in a docstring."""\n# import documents\npass\n'''
    assert legacy_documents_import_violations(source) == []


def test_no_legacy_imports_in_active_cli_first_paths() -> None:
    violations: list[str] = []
    for path in _iter_python_files():
        resolved = path.resolve()
        if resolved in ALLOWLIST_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for fragment in FORBIDDEN_TEXT_IMPORT_FRAGMENTS:
            if fragment in text:
                violations.append(f"{path.relative_to(ROOT)} -> {fragment}")
        try:
            for hit in legacy_documents_import_violations(text):
                violations.append(f"{path.relative_to(ROOT)} -> {hit}")
        except SyntaxError as exc:
            violations.append(f"{path.relative_to(ROOT)} -> parse_error:{exc.msg}")
    assert not violations, "Legacy imports detected:\n" + "\n".join(sorted(violations))


def test_no_unapproved_legacy_signature_bridge_usage() -> None:
    violations: list[str] = []
    for path in _iter_python_files():
        resolved = path.resolve()
        if resolved in ALLOWLIST_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for fragment in FORBIDDEN_LEGACY_SIGNATURE_STRINGS:
            if fragment in text:
                violations.append(f"{path.relative_to(ROOT)} -> {fragment}")
    assert not violations, "Legacy signature bridge usage detected:\n" + "\n".join(sorted(violations))
