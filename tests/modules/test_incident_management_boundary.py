from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from modules.incident_management.module import create_incident_management_module_contract

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_INTERNAL_SUFFIXES = (
    "service",
    "sqlite_repository",
    "incident_ops",
    "assessment_ops",
    "inquiry_ops",
    "action_ops",
    "capa_ops",
    "root_cause_ops",
    "effectiveness_ops",
    "artifact_ops",
    "grouping_ops",
    "leadership_ops",
    "management_review_ops",
    "report_ops",
    "query_ops",
    "role_ops",
    "validation",
    "authorization",
    "eventing",
    "capa_rules",
    "status_transitions",
    "settings_rules",
)

BOUNDARY_SCAN_ROOTS = (
    ROOT / "interfaces",
    ROOT / "tests" / "e2e_cli",
    ROOT / "tests" / "interfaces",
)

IMPORT_PATTERN = re.compile(
    r"^\s*(?:from|import)\s+modules\.incident_management(?:\.(\w+))?",
    re.MULTILINE,
)


def _collect_boundary_python_files() -> list[Path]:
    files: list[Path] = []
    for root in BOUNDARY_SCAN_ROOTS:
        if not root.exists():
            continue
        files.extend(sorted(root.rglob("*.py")))
    return files


def _forbidden_suffix_from_import_line(line: str) -> str | None:
    match = IMPORT_PATTERN.search(line)
    if not match:
        return None
    suffix = match.group(1)
    if suffix is None:
        return "__package__"
    if suffix in ("api", "contracts"):
        return None
    if suffix in FORBIDDEN_INTERNAL_SUFFIXES:
        return suffix
    if suffix == "module":
        return suffix
    return suffix


class IncidentManagementBoundaryTest(unittest.TestCase):
    def test_init_py_has_no_reexports(self) -> None:
        init_path = ROOT / "modules" / "incident_management" / "__init__.py"
        source = init_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self.fail("__init__.py must not import or re-export public API/contracts")
            if isinstance(node, ast.Assign):
                self.fail("__init__.py must not assign/re-export symbols")

    def test_service_port_not_public_in_contract(self) -> None:
        contract = create_incident_management_module_contract()
        self.assertEqual(contract.provided_ports, ["incident_management_api"])
        self.assertNotIn("incident_management_service", contract.provided_ports)

    def test_adapters_do_not_import_internal_modules(self) -> None:
        violations: list[str] = []
        for path in _collect_boundary_python_files():
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT).as_posix()
            for line_no, line in enumerate(text.splitlines(), start=1):
                suffix = _forbidden_suffix_from_import_line(line)
                if suffix is None:
                    continue
                violations.append(f"{rel}:{line_no}: imports modules.incident_management.{suffix}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
