from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
J04_M0_REPORT = DOCS / "J04_M0_ACCEPTANCE_REPORT.md"

# Matches the detail-section header for any MR09 remediation sub-step,
# e.g. "### MR09-R2-R3 — …"
_MR09_REMEDIATION_SECTION_RE = re.compile(
    r"^###\s+(MR09-R\d+-R\d+)\s+—.*$", re.MULTILINE
)
# Matches "- **Status:** PASS" / "IN_PROGRESS" etc. in a detail section
_SECTION_STATUS_RE = re.compile(r"^-\s+\*\*Status:\*\*\s+(\S+)", re.MULTILINE)

P0_DOCS = [
    ROOT / "README.md",
    DOCS / "GUI_SOURCE_OF_TRUTH.md",
    DOCS / "GUI_ARCHITECTURE_PROJECT.md",
    DOCS / "MODULES_DEVELOPER_GUIDE.md",
    DOCS / "OPERATIONS_CANONICAL.md",
    DOCS / "TEST_SMOKE_GATES.md",
]

P2_DOCS = [
    DOCS / "PYQT_CONTRIBUTIONS_REFERENCE.md",
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
J04_M0_PATH_MATRIX = DOCS / "J04_M0_PATH_MATRIX.md"
MASTER_ORCHESTRATION_ROADMAP = DOCS / "MASTER_ORCHESTRATION_ROADMAP.md"
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


def _last_mr09_remediation_checkpoint(checklist_text: str) -> tuple[str, str]:
    """Return (name, status) of the last MR09-R*-R* detail section in the checklist.

    The section name is e.g. "MR09-R2-R4". The status is the value on the
    "- **Status:** …" line immediately following that header (first occurrence
    within the section, before the next ``###`` header).
    """
    matches = list(_MR09_REMEDIATION_SECTION_RE.finditer(checklist_text))
    assert matches, "no MR09 remediation detail section found in checklist"
    last_match = matches[-1]
    section_name = last_match.group(1)
    # Text from the header to the next ### header (or end of file)
    section_start = last_match.end()
    next_header = checklist_text.find("\n###", section_start)
    section_body = (
        checklist_text[section_start:next_header]
        if next_header != -1
        else checklist_text[section_start:]
    )
    status_match = _SECTION_STATUS_RE.search(section_body)
    assert status_match, (
        f"no '- **Status:** …' line found in section {section_name!r}"
    )
    return section_name, status_match.group(1)


# All status keywords that may appear in the report's status clauses.
_ALL_STATUS_KEYWORDS = frozenset({"PASS", "IN_PROGRESS", "FAILED", "BLOCKED", "TODO"})


def _extract_checkpoint_clause_from_top_line(top_line: str, checkpoint: str) -> str:
    """Return the semicolon-delimited clause within *top_line* that starts with
    *checkpoint* (or the shortest suffix starting at the checkpoint occurrence).

    The top-line format is a parenthesised list of semicolon-separated clauses, e.g.:
        … (MR09-R2-R4 IN_PROGRESS: …; MR09-R2-R3 PASS; …)
    We want only the clause that belongs to *checkpoint*, not neighbouring ones.
    """
    idx = top_line.find(checkpoint)
    assert idx != -1, (
        f"checkpoint {checkpoint!r} not found in top status line:\n{top_line!r}"
    )
    # Take text from the checkpoint occurrence to the next semicolon, closing paren,
    # or end of line – whichever comes first.
    fragment = top_line[idx:]
    end = len(fragment)
    for delim in (";", ")", "\n"):
        pos = fragment.find(delim)
        if pos != -1 and pos < end:
            end = pos
    return fragment[:end]


def _extract_checkpoint_bullet_from_candidate_section(
    candidate_section: str, checkpoint: str
) -> str:
    """Return the bullet/paragraph in *candidate_section* that begins with
    *checkpoint*, bounded to the next bullet or end of section.

    Candidate-section bullet format (simplified):
        - **MR09-R2-R4** (IN_PROGRESS) …
        - **MR09-R2-R3** … (**PASS**).
    We look for a line that contains *checkpoint* after a leading ``-`` or ``*``,
    and return up to (but not including) the next such bullet line.
    """
    lines = candidate_section.splitlines(keepends=True)
    start_idx: int | None = None
    end_idx: int = len(lines)
    bullet_re = re.compile(r"^\s*[-*]\s+\*{0,2}" + re.escape(checkpoint))
    for i, line in enumerate(lines):
        if bullet_re.match(line):
            if start_idx is None:
                start_idx = i
            elif start_idx is not None:
                # A second bullet starting with the same checkpoint would be odd,
                # but we stop at the next distinct bullet if checkpoint already found.
                end_idx = i
                break
        elif start_idx is not None and re.match(r"^\s*[-*]\s+\*{0,2}MR09", line):
            # Next bullet for a different checkpoint – stop here.
            end_idx = i
            break
    assert start_idx is not None, (
        f"no bullet starting with {checkpoint!r} found in Candidate section"
    )
    return "".join(lines[start_idx:end_idx])


def test_acceptance_report_remediation_checkpoint_consistent_with_checklist() -> None:
    """The top status line and the current Candidate section of the Acceptance Report
    must agree with the last MR09 remediation checkpoint found in the Checklist.

    The check is performed on the *checkpoint-specific clause / bullet* only, so
    a status keyword from a neighbouring checkpoint cannot satisfy the assertion.
    """
    checklist_text = _read(J04_M0_CHECKLIST)
    report_text = _read(J04_M0_REPORT)

    checkpoint, status = _last_mr09_remediation_checkpoint(checklist_text)

    # --- top "Current status" line: isolate the checkpoint-specific clause ---
    top_line_match = re.search(r"^Current status:.*$", report_text, re.MULTILINE)
    assert top_line_match, "no 'Current status:' line found in Acceptance Report"
    top_line = top_line_match.group(0)
    assert checkpoint in top_line, (
        f"top status line does not mention current remediation checkpoint "
        f"{checkpoint!r}.\nLine: {top_line!r}"
    )
    top_clause = _extract_checkpoint_clause_from_top_line(top_line, checkpoint)
    assert status in top_clause, (
        f"top status line clause for {checkpoint!r} does not contain expected "
        f"status {status!r}.\nClause: {top_clause!r}"
    )
    # No other status keyword may appear as the checkpoint's own status in this clause.
    for other in _ALL_STATUS_KEYWORDS - {status}:
        # Allow the other keyword if it belongs to a sub-description after a colon,
        # but not as the direct <checkpoint> <STATUS> pairing.
        direct_re = re.compile(
            re.escape(checkpoint) + r"\s+" + re.escape(other)
        )
        assert not direct_re.search(top_clause), (
            f"top status clause for {checkpoint!r} contains unexpected status "
            f"{other!r} directly after checkpoint name.\nClause: {top_clause!r}"
        )

    # --- first "Technical acceptance candidate" section: isolate the bullet ---
    candidate_section_match = re.search(
        r"^## Technical acceptance candidate\b(.*?)^##\s",
        report_text,
        re.MULTILINE | re.DOTALL,
    )
    assert candidate_section_match, (
        "no 'Technical acceptance candidate' section found in Acceptance Report"
    )
    candidate_section = candidate_section_match.group(1)
    assert checkpoint in candidate_section, (
        f"Candidate section does not mention current remediation checkpoint "
        f"{checkpoint!r}"
    )
    bullet = _extract_checkpoint_bullet_from_candidate_section(
        candidate_section, checkpoint
    )
    assert status in bullet, (
        f"Candidate section bullet for {checkpoint!r} does not contain expected "
        f"status {status!r}.\nBullet: {bullet!r}"
    )


def test_acceptance_report_remediation_checkpoint_status_not_satisfied_by_neighbour() -> None:
    """Regression: the status check must fail when the expected status appears only
    in a neighbouring checkpoint's clause/bullet, not in the current checkpoint's.

    Synthetic scenario (does not use real files):
      - Last checklist section is "MR09-R2-X" with Status: IN_PROGRESS
      - Top status line contains: "MR09-R2-X IN_PROGRESS: …; MR09-R2-W PASS"
        (PASS belongs to neighbour MR09-R2-W, not to MR09-R2-X)
      - Candidate section bullet: "- **MR09-R2-X** mentions nothing; neighbour bullet
        lists MR09-R2-W PASS"
    The clause/bullet isolation must ensure that asking for IN_PROGRESS in the
    MR09-R2-X clause succeeds, and that PASS from the neighbouring clause does NOT
    bleed into the assertion for MR09-R2-X.
    """
    # Synthetic top line: checkpoint clause ends at ";", neighbour has PASS after it.
    top_line = (
        "Current status: `X` — **MR09 IN_PROGRESS "
        "(MR09-R2-X IN_PROGRESS: doing work; MR09-R2-W PASS; kein Candidate)**"
    )
    checkpoint = "MR09-R2-X"
    expected_status = "IN_PROGRESS"

    # The clause extracted for MR09-R2-X must contain IN_PROGRESS.
    clause = _extract_checkpoint_clause_from_top_line(top_line, checkpoint)
    assert expected_status in clause, (
        f"expected {expected_status!r} in clause {clause!r}"
    )
    # PASS from the neighbour must NOT be in the MR09-R2-X clause.
    assert "PASS" not in clause, (
        f"PASS from neighbour leaked into MR09-R2-X clause: {clause!r}"
    )

    # Synthetic candidate section: MR09-R2-X bullet has no PASS, neighbour does.
    candidate_section = (
        "\n"
        "- **MR09-R2-X** (IN_PROGRESS) doing work.\n"
        "- **MR09-R2-W** hat etwas abgeschlossen (**PASS**).\n"
    )
    bullet = _extract_checkpoint_bullet_from_candidate_section(
        candidate_section, checkpoint
    )
    assert expected_status in bullet, (
        f"expected {expected_status!r} in bullet {bullet!r}"
    )
    # PASS from the neighbour bullet must not bleed into the MR09-R2-X bullet.
    assert "PASS" not in bullet, (
        f"PASS from neighbour leaked into MR09-R2-X bullet: {bullet!r}"
    )


def test_j04_m0_formal_acceptance_status_sources_agree() -> None:
    """Current J04-M0 steering sources must agree on formal Acceptance.

    When the Acceptance Report current status is ``Accepted``, the roadmap
    acceptance line and the Path Matrix Final Green Gate must not still claim
    rejection or an unrun final gate. Historical snapshots elsewhere remain
    out of scope for this check.
    """
    report_text = _read(J04_M0_REPORT)
    roadmap_text = _read(MASTER_ORCHESTRATION_ROADMAP)
    matrix_text = _read(J04_M0_PATH_MATRIX)

    top_line_match = re.search(r"^Current status:.*$", report_text, re.MULTILINE)
    assert top_line_match, "no 'Current status:' line found in Acceptance Report"
    top_line = top_line_match.group(0)
    assert top_line.startswith("Current status: `Accepted`"), (
        f"Acceptance Report current status is not Accepted.\nLine: {top_line!r}"
    )

    roadmap_status_match = re.search(
        r"^- J04-M0 acceptance status:.*$",
        roadmap_text,
        re.MULTILINE,
    )
    assert roadmap_status_match, "no J04-M0 acceptance status line in roadmap"
    roadmap_status = roadmap_status_match.group(0)
    assert "`Accepted`" in roadmap_status, (
        f"roadmap acceptance status does not contain Accepted.\nLine: {roadmap_status!r}"
    )
    assert "Rejected / follow-up required" not in roadmap_status, (
        f"roadmap acceptance status still claims rejection.\nLine: {roadmap_status!r}"
    )

    final_gate_match = re.search(
        r"^\| Final Green Gate \(2-Client-Live, Golive, Packaging\) \|.*?\|.*?\|$",
        matrix_text,
        re.MULTILINE,
    )
    assert final_gate_match, "Final Green Gate row missing from Path Matrix"
    final_gate = final_gate_match.group(0)
    assert "`available`" in final_gate, (
        f"Final Green Gate is not marked available.\nRow: {final_gate!r}"
    )
    assert "acceptance remains rejected" not in final_gate.lower(), (
        f"Final Green Gate still claims rejected acceptance.\nRow: {final_gate!r}"
    )
    assert "NOT RUN" not in final_gate, (
        f"Final Green Gate still claims NOT RUN.\nRow: {final_gate!r}"
    )
    assert "`Accepted`" in final_gate or "Accepted" in final_gate, (
        f"Final Green Gate does not reference Accepted.\nRow: {final_gate!r}"
    )


# ---------------------------------------------------------------------------
# AP-029 / Web-PostgreSQL transition governance
# ---------------------------------------------------------------------------

AP029_PLAN = DOCS / "AP-029_WEB_POSTGRES_TRANSITION_PLAN.md"
DATABASE_EVOLUTION_POLICY = DOCS / "DATABASE_EVOLUTION_POLICY.md"
GUI_SOURCE_OF_TRUTH = DOCS / "GUI_SOURCE_OF_TRUTH.md"
DOCS_CANONICAL_INDEX = DOCS / "DOCS_CANONICAL_INDEX.md"
MODULE_INTEGRATION_POLICY = DOCS / "MODULE_INTEGRATION_POLICY.md"
ARCHITECTURE_REFACTOR = DOCS / "ARCHITECTURE_REFACTOR_CANONICAL.md"

AP029_LEDGER_START = "<!-- AP029_LEDGER_START -->"
AP029_LEDGER_END = "<!-- AP029_LEDGER_END -->"
AP029_LEDGER_STATUSES = frozenset({"TODO", "IN_PROGRESS", "PASS", "FAILED", "BLOCKED"})
AP029_LEDGER_OPEN_STATUSES = frozenset({"TODO", "IN_PROGRESS", "FAILED", "BLOCKED"})
AP029_LEDGER_CHECKPOINTS = (
    ("GOV00", "Canonical architecture decisions and executable plan"),
    ("GOV01", "Executable macro governance and ledger hardening"),
    ("TOOL00", "Native Cursor reviewer and gated macro tooling"),
    ("CB00", "Controlled portable container-core integration"),
    ("INV00", "Read-only SQLite store inventory"),
    ("PG00", "PostgreSQL platform foundation"),
    ("WEB00", "webclient foundation and /api/v1 cookie/CSRF shell"),
    ("PG01", "Documents/Registry/Signature PostgreSQL migration"),
    ("OPS00", "Windows service, HTTPS, backup/restore, export"),
    ("INT00", "Joint integration gate PG00/WEB00/PG01/OPS00"),
    ("WEB01", "Full Documents/Signature web workflow"),
    ("PILOT00", "Pilot readiness security/restore/ops/human-smoke"),
    ("PILOT01", "Limited live-data pilot with human approval"),
    ("CB01", "Container productization after proven DMS web pattern"),
    ("CONV00", "DOCX/DOTX converter comparison and hardening"),
    ("J04-M1", "Relational domain normalization after pilot"),
    ("MOD00", "Further modules on same backend/PG/web pattern"),
)
_AP029_LEDGER_IDS = tuple(checkpoint_id for checkpoint_id, _ in AP029_LEDGER_CHECKPOINTS)
_AP029_CURRENT_CHECKPOINT_RE = re.compile(
    r"^Current checkpoint:\s+(\S+)\s*$",
    re.MULTILINE,
)
_AP029_LEDGER_ROW_RE = re.compile(
    rf"^\|\s*({'|'.join(re.escape(checkpoint_id) for checkpoint_id in _AP029_LEDGER_IDS)})\s*"
    r"\|\s*(.*?)\s*\|\s*(\S+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$"
)
AP029_REQUIRED_DECISIONS = (
    "D01",
    "D02",
    "D03",
    "D04",
    "D05",
    "D06",
    "D07",
    "D08",
    "D09",
    "D10",
    "D11",
    "D12",
    "D13",
    "D14",
    "D15",
)


def _extract_ap029_ledger_block(text: str) -> str:
    start_count = text.count(AP029_LEDGER_START)
    end_count = text.count(AP029_LEDGER_END)
    assert start_count == 1, f"expected exactly one AP029 ledger start marker, found {start_count}"
    assert end_count == 1, f"expected exactly one AP029 ledger end marker, found {end_count}"
    start = text.index(AP029_LEDGER_START) + len(AP029_LEDGER_START)
    end = text.index(AP029_LEDGER_END)
    assert start < end, "AP029 ledger start marker must precede end marker"
    return text[start:end]


def _parse_ap029_ledger(text: str) -> tuple[str, list[dict[str, str]]]:
    block = _extract_ap029_ledger_block(text)
    current_matches = _AP029_CURRENT_CHECKPOINT_RE.findall(block)
    assert len(current_matches) == 1, (
        f"expected exactly one Current checkpoint line in AP029 ledger, found {current_matches!r}"
    )
    rows: list[dict[str, str]] = []
    for line in block.splitlines():
        match = _AP029_LEDGER_ROW_RE.match(line.strip())
        if match is None:
            continue
        rows.append(
            {
                "id": match.group(1),
                "title": match.group(2),
                "status": match.group(3),
                "start_sha": match.group(4),
                "result_evidence": match.group(5),
                "notes": match.group(6),
            }
        )
    return current_matches[0], rows


def _ap029_evidence_root(checkpoint_id: str) -> str:
    return f"build/ap-029-{checkpoint_id.lower()}/"


def _p0_section(index_text: str) -> str:
    match = re.search(
        r"## P0 \(canonical, decision-making\)\s*(.*?)(?=\n## |\Z)",
        index_text,
        re.DOTALL,
    )
    assert match, "P0 section missing from DOCS_CANONICAL_INDEX"
    return match.group(1)


def _p2_section(index_text: str) -> str:
    match = re.search(
        r"## P2 \(legacy/history or roadmap support\)[^\n]*\s*(.*?)(?=\n## |\Z)",
        index_text,
        re.DOTALL,
    )
    assert match, "P2 section missing from DOCS_CANONICAL_INDEX"
    return match.group(1)


def test_ap029_transition_decisions_are_consistent() -> None:
    plan = _read(AP029_PLAN)
    roadmap = _read(MASTER_ORCHESTRATION_ROADMAP)
    gui_sot = _read(GUI_SOURCE_OF_TRUTH)
    db_policy = _read(DATABASE_EVOLUTION_POLICY)
    module_policy = _read(MODULE_INTEGRATION_POLICY)
    architecture = _read(ARCHITECTURE_REFACTOR)
    index = _read(DOCS_CANONICAL_INDEX)

    assert "Status: Active transition governance (P1)" in plan
    assert "haben Status **DECIDED**" in plan
    for decision_id in AP029_REQUIRED_DECISIONS:
        assert f"### {decision_id}" in plan, f"missing decision {decision_id}"

    assert "webclient/" in plan
    assert "/api/v1" in plan
    assert "organization_id" in plan
    assert "Same-Origin" in plan
    assert "kein produktiver sqlite-fallback" in plan.lower()

    # Roadmap and P0 owners must not contradict the decided target.
    assert "PostgreSQL bleibt Zielrichtung/offene Entscheidung" not in roadmap
    ziel = roadmap.split("## Zielarchitektur", 1)[-1].split("## MVP-Priorisierung", 1)[0]
    assert "PyQt Client" not in ziel
    assert "webclient" in roadmap.lower()
    assert "PostgreSQL-only" in roadmap or "ausschliesslich PostgreSQL" in roadmap
    assert "kein produktiver SQLite-Fallback" in roadmap

    current, _ = _parse_ap029_ledger(plan)
    next_action = re.search(
        r"## Naechste freigegebene Aktion\s*(.*?)(?=\n## |\Z)",
        roadmap,
        re.DOTALL,
    )
    assert next_action, "roadmap next-action section missing"
    next_body = next_action.group(1)
    assert current in next_body
    assert f"ausschliesslich {current}" in next_body or f"ausschließlich {current}" in next_body

    assert "webclient/*" in gui_sot
    assert "PostgreSQL only" in db_policy or "PostgreSQL-only" in db_policy
    assert "No productive SQLite fallback" in db_policy
    assert "frozen" in module_policy.lower() and "pyqt" in module_policy.lower()
    assert "webclient" in architecture.lower()
    assert "`docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`" in index


def test_webclient_is_only_active_gui_source() -> None:
    gui_sot = _read(GUI_SOURCE_OF_TRUTH)
    gui_arch = _read(DOCS / "GUI_ARCHITECTURE_PROJECT.md")
    index = _read(DOCS_CANONICAL_INDEX)
    pyqt_ref = _read(DOCS / "PYQT_CONTRIBUTIONS_REFERENCE.md")

    assert "webclient/*" in gui_sot or "`webclient/*`" in gui_sot
    assert "WEB00" in gui_sot
    assert "noch nicht" in gui_sot.lower() or "not implemented" in gui_sot.lower()
    assert "frozen" in gui_sot.lower()
    assert "Legacy/Reference" in gui_sot or "legacy/reference" in gui_sot.lower()
    assert "keine neuen PyQt-Contributions" in gui_sot or "no new PyQt" in gui_sot

    assert "webclient/" in gui_arch
    assert "/api/v1" in gui_arch
    assert "Generic-first" in gui_arch or "generic-first" in gui_arch.lower()

    p0 = _p0_section(index)
    p2 = _p2_section(index)
    assert "`docs/PYQT_CONTRIBUTIONS_REFERENCE.md`" not in p0
    assert "`docs/PYQT_CONTRIBUTIONS_REFERENCE.md`" in p2
    assert "Status: Legacy/History (P2" in pyqt_ref
    assert "Frozen" in pyqt_ref or "frozen" in pyqt_ref


def test_product_runtime_target_is_postgres_only() -> None:
    plan = _read(AP029_PLAN)
    roadmap = _read(MASTER_ORCHESTRATION_ROADMAP)
    db_policy = _read(DATABASE_EVOLUTION_POLICY)

    assert "### D03" in plan
    d03_start = plan.index("### D03")
    d03_end = plan.find("\n### ", d03_start + 1)
    d03 = plan[d03_start:d03_end if d03_end != -1 else None]
    assert "PostgreSQL" in d03
    assert "SQLite" in d03
    assert "Fallback" in d03 or "fallback" in d03

    assert "Productive target runtime (DECIDED)" in db_policy
    assert "PostgreSQL only" in db_policy or "PostgreSQL-only" in db_policy
    assert "No productive SQLite fallback" in db_policy
    assert "Ist / legacy SQLite" in db_policy

    assert "PostgreSQL-only" in roadmap or "ausschliesslich PostgreSQL" in roadmap
    assert "kein produktiver SQLite-Fallback" in roadmap
    assert "PostgreSQL bleibt Zielrichtung/offene Entscheidung" not in roadmap


def test_ap029_checkpoint_ledger_is_consistent() -> None:
    text = _read(AP029_PLAN)
    current, rows = _parse_ap029_ledger(text)
    expected_ids = [checkpoint_id for checkpoint_id, _ in AP029_LEDGER_CHECKPOINTS]
    assert [row["id"] for row in rows] == expected_ids
    assert len({row["id"] for row in rows}) == len(expected_ids)

    for (expected_id, expected_title), row in zip(AP029_LEDGER_CHECKPOINTS, rows, strict=True):
        assert row["id"] == expected_id
        assert row["title"] == expected_title
        assert row["status"] in AP029_LEDGER_STATUSES, (
            f"{row['id']} has illegal status {row['status']!r}"
        )

    in_progress = [row["id"] for row in rows if row["status"] == "IN_PROGRESS"]
    assert len(in_progress) <= 1, f"more than one IN_PROGRESS: {in_progress}"

    seen_open = False
    first_open: str | None = None
    for row in rows:
        if row["status"] in AP029_LEDGER_OPEN_STATUSES:
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
            expected_root = _ap029_evidence_root(row["id"])
            assert expected_root in evidence, (
                f"{row['id']} PASS is missing an evidence path under {expected_root}"
            )
            assert "passed" in evidence.lower(), (
                f"{row['id']} PASS is missing a result in Ergebnis/Evidence"
            )

    if first_open is None:
        assert current == "COMPLETE"
        assert all(row["status"] == "PASS" for row in rows)
    else:
        assert current == first_open


def test_ap029_future_checkpoint_evidence_roots_are_checkpoint_specific() -> None:
    assert _ap029_evidence_root("GOV00") == "build/ap-029-gov00/"
    assert _ap029_evidence_root("CB00") == "build/ap-029-cb00/"
    assert _ap029_evidence_root("J04-M1") == "build/ap-029-j04-m1/"


def test_ap029_unqualified_current_checkpoint_claims_match_ledger() -> None:
    """Present-tense '<ID> ist Current checkpoint.' must match ledger Current."""
    text = _read(AP029_PLAN)
    current, _ = _parse_ap029_ledger(text)
    claim_re = re.compile(r"(?m)^([A-Z0-9-]+) ist Current checkpoint\.?\s*$")
    for match in claim_re.finditer(text):
        claimed = match.group(1)
        assert claimed == current, (
            f"unqualified claim {claimed!r} ist Current checkpoint conflicts with "
            f"ledger Current checkpoint {current!r} (line context: {match.group(0)!r})"
        )


def test_ap029_macro_governance_is_explicit_and_serial() -> None:
    plan = _read(AP029_PLAN)
    roadmap = _read(MASTER_ORCHESTRATION_ROADMAP)
    workflow = _read(ROOT / ".cursor" / "rules" / "00-agent-workflow.mdc")

    for required in (
        "### D13",
        "### D14",
        "GOV01",
        "TOOL00",
        "separate Allowlist",
        "separate Evidence",
        "separaten Reviewer-Verdict",
        "separaten lokalen Commit",
        "höchstens zwei normale",
        "genau ein frischer Escalation Review",
    ):
        assert required in plan, f"AP-029 macro contract is missing {required!r}"

    assert "GOV00 → GOV01 → TOOL00 → CB00" in roadmap
    assert "AP-029 macro" in workflow
    assert "first unresolved checkpoint" in workflow
