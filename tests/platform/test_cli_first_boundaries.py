from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIVE_DIRS = (
    ROOT / "interfaces",
    ROOT / "modules",
    ROOT / "platform",
    ROOT / "tests",
)
FORBIDDEN_IMPORT_FRAGMENTS = (
    "from core.",
    "import core",
    "from documents.",
    "import documents",
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


def test_no_legacy_imports_in_active_cli_first_paths() -> None:
    violations: list[str] = []
    for path in _iter_python_files():
        if path.resolve() in ALLOWLIST_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
            if fragment in text:
                violations.append(f"{path.relative_to(ROOT)} -> {fragment}")
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
