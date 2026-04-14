from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

P0_DOCS = [
    ROOT / "README.md",
    DOCS / "GUI_SOURCE_OF_TRUTH.md",
    DOCS / "GUI_ARCHITECTURE_PROJECT.md",
    DOCS / "PYQT_CONTRIBUTIONS_REFERENCE.md",
    DOCS / "MODULES_DEVELOPER_GUIDE.md",
    DOCS / "OPERATIONS_CANONICAL.md",
    DOCS / "TEST_SMOKE_GATES.md",
]

P2_DOCS = [
    DOCS / "DEVGUIDE.md",
    DOCS / "AGENTS_PROJECT.md",
    DOCS / "CLI_FIRST_MIGRATION.md",
    DOCS / "RELEASE_READINESS.md",
    DOCS / "TRACK_B_CHANGE_SPEC.md",
    DOCS / "TRACK_B_SRP_PREP.md",
    DOCS / "SRP_REFACTOR_ROADMAP.md",
    DOCS / "UI_MVP.md",
    DOCS / "TAGESSTART.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p0_docs_have_canonical_status_header() -> None:
    for path in P0_DOCS:
        assert "Status: Canonical (P0)" in _read(path), f"missing canonical header in {path}"


def test_p2_docs_have_legacy_status_header() -> None:
    for path in P2_DOCS:
        assert "Status: Legacy/History (P2" in _read(path), f"missing legacy header in {path}"


def test_docs_do_not_reference_old_platform_package_paths() -> None:
    forbidden = [
        "`platform/runtime",
        "`platform/settings",
        "`platform/logging",
        "`platform/sdk",
        "`platform/events",
        "`platform/*`",
    ]
    for path in DOCS.glob("*.md"):
        content = _read(path)
        for token in forbidden:
            assert token not in content, f"forbidden token {token!r} in {path}"


def test_canonical_index_exists_and_lists_p0() -> None:
    index = _read(DOCS / "DOCS_CANONICAL_INDEX.md")
    assert "## P0 (canonical, decision-making)" in index
    assert "`docs/GUI_SOURCE_OF_TRUTH.md`" in index
    assert "`docs/MODULES_DEVELOPER_GUIDE.md`" in index
