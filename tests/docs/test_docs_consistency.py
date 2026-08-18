from __future__ import annotations

import re
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


J04_M0_CHECKLIST = DOCS / "J04_M0_EXECUTABLE_CHECKLIST.md"
MERGE_LEDGER_START = "<!-- J04_M0_MERGE_LEDGER_START -->"
MERGE_LEDGER_END = "<!-- J04_M0_MERGE_LEDGER_END -->"
MERGE_LEDGER_STATUSES = frozenset({"TODO", "IN_PROGRESS", "PASS", "FAILED", "BLOCKED"})
MERGE_LEDGER_OPEN_STATUSES = frozenset({"TODO", "IN_PROGRESS", "FAILED", "BLOCKED"})
MERGE_LEDGER_CHECKPOINTS = (
    ("MR00", "Aktuellen Stand und Ledger etablieren"),
    ("MR01", "Duplicate-Create atomar verhindern"),
    ("MR02", "Documents-Dateipfade vollständig begrenzen"),
    ("MR03", "Autorisierung vor Zustands-/ETag-Offenlegung"),
    ("MR04", "Import-CAS und SQLite-Thread-Sicherheit"),
    ("MR05", "Signature-Dateien und Scratch-Lebenszyklus härten"),
    ("MR06", "DOCX-Kommentarsynchronisation stabilisieren"),
    ("MR07", "Realprocess-Harness auf verbindlichen M0-Scope bringen"),
    ("MR08", "Gesamte Regression und Candidate Freeze"),
    ("MR09", "Kontrollierten CP08-V9-Lauf ausführen"),
    ("MR10", "Packaging, Golive, Human Gate und Merge"),
)
_CURRENT_CHECKPOINT_RE = re.compile(
    r"^Current checkpoint:\s+(MR\d{2}|COMPLETE)\s*$",
    re.MULTILINE,
)
_LEDGER_ROW_RE = re.compile(
    r"^\|\s*(MR\d{2})\s*\|\s*(.*?)\s*\|\s*(\S+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$"
)


def _extract_j04_m0_merge_ledger_block(text: str) -> str:
    start_count = text.count(MERGE_LEDGER_START)
    end_count = text.count(MERGE_LEDGER_END)
    assert start_count == 1, f"expected exactly one ledger start marker, found {start_count}"
    assert end_count == 1, f"expected exactly one ledger end marker, found {end_count}"
    start = text.index(MERGE_LEDGER_START) + len(MERGE_LEDGER_START)
    end = text.index(MERGE_LEDGER_END)
    assert start < end, "ledger start marker must precede end marker"
    return text[start:end]


def _parse_j04_m0_merge_ledger(text: str) -> tuple[str, list[dict[str, str]]]:
    block = _extract_j04_m0_merge_ledger_block(text)
    current_matches = _CURRENT_CHECKPOINT_RE.findall(block)
    assert len(current_matches) == 1, (
        f"expected exactly one Current checkpoint line in ledger, found {current_matches!r}"
    )
    rows: list[dict[str, str]] = []
    for line in block.splitlines():
        match = _LEDGER_ROW_RE.match(line.strip())
        if match is None:
            continue
        rows.append(
            {
                "id": match.group(1),
                "title": match.group(2),
                "status": match.group(3),
                "start_sha": match.group(4),
                "result_evidence": match.group(5),
                "commit": match.group(6),
            }
        )
    return current_matches[0], rows


def test_j04_m0_historical_checkpoint_tables_are_preserved() -> None:
    text = _read(J04_M0_CHECKLIST)
    assert MERGE_LEDGER_START in text
    assert MERGE_LEDGER_END in text
    historical = text.split(MERGE_LEDGER_START, 1)[0]
    assert "| CP00 | Preserve and classify baseline | PASS |" in historical
    assert "| CP08-V8 | Final acceptance attempt | FAILED |" in historical
    assert "| CP08-R9 | Document-release actor remediation + scope cut | PASS |" in historical
    assert "historical snapshot (2026-08-17)" in historical


def test_j04_m0_merge_ledger_is_consistent() -> None:
    current, rows = _parse_j04_m0_merge_ledger(_read(J04_M0_CHECKLIST))
    expected_ids = [checkpoint_id for checkpoint_id, _ in MERGE_LEDGER_CHECKPOINTS]
    assert [row["id"] for row in rows] == expected_ids
    assert len({row["id"] for row in rows}) == len(expected_ids)

    for (expected_id, expected_title), row in zip(MERGE_LEDGER_CHECKPOINTS, rows, strict=True):
        assert row["id"] == expected_id
        assert row["title"] == expected_title
        assert row["status"] in MERGE_LEDGER_STATUSES, (
            f"{row['id']} has illegal status {row['status']!r}"
        )

    in_progress = [row["id"] for row in rows if row["status"] == "IN_PROGRESS"]
    assert len(in_progress) <= 1, f"more than one IN_PROGRESS: {in_progress}"

    seen_open = False
    first_open: str | None = None
    for row in rows:
        if row["status"] in MERGE_LEDGER_OPEN_STATUSES:
            if first_open is None:
                first_open = row["id"]
            seen_open = True
            continue
        if row["status"] == "PASS":
            assert not seen_open, (
                f"{row['id']} is PASS but an earlier checkpoint is still open"
            )
            evidence = row["result_evidence"]
            assert evidence and evidence not in {"—", "-", "pending"}, (
                f"{row['id']} PASS is missing Ergebnis/Evidence"
            )
            assert "build/j04-m0-closure/" in evidence, (
                f"{row['id']} PASS is missing an evidence path under build/j04-m0-closure/"
            )
            assert "passed" in evidence.lower(), (
                f"{row['id']} PASS is missing a result in Ergebnis/Evidence"
            )

    if first_open is None:
        assert current == "COMPLETE"
        assert all(row["status"] == "PASS" for row in rows)
    else:
        assert current == first_open
