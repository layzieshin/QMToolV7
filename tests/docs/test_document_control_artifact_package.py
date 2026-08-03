from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs" / "QMToolV7_Dokumentenlenkung_Artefaktpaket_v2"
MANIFEST_NAME = "QMToolV7_Dokumentenlenkung_MANIFEST_v2.txt"
README_NAME = "QMToolV7_Dokumentenlenkung_Artefakte_README_v2.md"
CURSOR_AUFTRAG_NAME = "QMToolV7_Dokumentenlenkung_Cursor_Arbeitsauftrag_v2.md"

EXPECTED_PACKAGE_FILES = frozenset(
    {
        README_NAME,
        "QMToolV7_Dokumentenlenkung_Nachschärfung_v2.md",
        CURSOR_AUFTRAG_NAME,
        "QMToolV7_Dokumentenlenkung_Sollmodell_v2.md",
        "QMToolV7_Dokumentenlenkung_Ist_Soll_Umbauplan_v2.md",
        "QMToolV7_Dokumentenlenkung_Eventkatalog.md",
        "QMToolV7_Dokumentenlenkung_Use_Case_Kandidaten.md",
        "QMToolV7_Dokumentenlenkung_Edge_Cases.md",
        "QMToolV7_Dokumentenlenkung_Entscheidungsmodell_v2.yaml",
        "QMToolV7_Fachlogik_Dokumentenlenkung_Ausgefüllt_v2.xlsx",
        "JSON_STORAGE_INVENTORY.md",
        "JSON_STORAGE_OPEN_QUESTIONS.md",
        "JSON_VS_DATABASE_ADR.md",
        "TARGET_PERSISTENCE_MODEL.md",
        "JSON_TO_DATABASE_MIGRATION_PLAN.md",
        MANIFEST_NAME,
    }
)

JSON_BASELINE_FILES = (
    "JSON_STORAGE_INVENTORY.md",
    "JSON_STORAGE_OPEN_QUESTIONS.md",
    "JSON_VS_DATABASE_ADR.md",
    "TARGET_PERSISTENCE_MODEL.md",
    "JSON_TO_DATABASE_MIGRATION_PLAN.md",
)

_BACKTICK_REF = re.compile(r"`([^`]+)`")
_MANIFEST_LINE = re.compile(r"^([0-9a-f]{64})\s+(.+)$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _MANIFEST_LINE.match(line)
        assert match, f"invalid manifest line: {raw!r}"
        digest, name = match.group(1), match.group(2)
        assert name not in entries, f"duplicate manifest entry: {name}"
        entries[name] = digest
    return entries


def _referenced_package_files(text: str) -> set[str]:
    names: set[str] = set()
    for token in _BACKTICK_REF.findall(text):
        candidate = Path(token).name
        if candidate in EXPECTED_PACKAGE_FILES or candidate.endswith(
            (".md", ".yaml", ".xlsx", ".txt")
        ):
            # Only assert package-local names that look like package artifacts.
            if candidate in EXPECTED_PACKAGE_FILES or (
                candidate.startswith(("QMToolV7_", "JSON_", "TARGET_"))
            ):
                names.add(candidate)
    return names


def test_package_contains_exact_expected_files() -> None:
    assert PACKAGE.is_dir(), f"missing package directory: {PACKAGE}"
    present = {path.name for path in PACKAGE.iterdir() if path.is_file()}
    assert present == EXPECTED_PACKAGE_FILES


def test_manifest_lists_every_file_except_itself_exactly_once() -> None:
    manifest_path = PACKAGE / MANIFEST_NAME
    entries = _parse_manifest(manifest_path)
    expected = EXPECTED_PACKAGE_FILES - {MANIFEST_NAME}
    assert set(entries) == expected
    assert MANIFEST_NAME not in entries


def test_manifest_sha256_values_match_file_contents() -> None:
    entries = _parse_manifest(PACKAGE / MANIFEST_NAME)
    for name, expected_digest in entries.items():
        path = PACKAGE / name
        assert path.is_file(), f"manifest entry missing on disk: {name}"
        assert _sha256(path) == expected_digest, f"SHA-256 mismatch for {name}"


def test_readme_and_cursor_auftrag_reference_existing_package_files() -> None:
    for doc_name in (README_NAME, CURSOR_AUFTRAG_NAME):
        text = (PACKAGE / doc_name).read_text(encoding="utf-8")
        for name in _referenced_package_files(text):
            assert (PACKAGE / name).is_file(), f"{doc_name} references missing {name}"


def test_readme_and_cursor_auftrag_reference_all_json_baseline_files() -> None:
    for doc_name in (README_NAME, CURSOR_AUFTRAG_NAME):
        text = (PACKAGE / doc_name).read_text(encoding="utf-8")
        referenced = _referenced_package_files(text)
        for name in JSON_BASELINE_FILES:
            assert name in referenced, f"{doc_name} must reference {name}"


def test_json_baseline_files_are_present_and_manifested() -> None:
    entries = _parse_manifest(PACKAGE / MANIFEST_NAME)
    for name in JSON_BASELINE_FILES:
        assert name in EXPECTED_PACKAGE_FILES
        assert (PACKAGE / name).is_file()
        assert name in entries
