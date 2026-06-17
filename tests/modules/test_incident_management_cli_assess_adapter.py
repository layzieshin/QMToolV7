from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ROOT / "interfaces" / "cli" / "commands" / "incident_management_commands.py"


class IncidentManagementCliAssessAdapterTest(unittest.TestCase):
    def test_assess_command_has_no_capa_or_rca_derivation(self) -> None:
        source = COMMANDS.read_text(encoding="utf-8")
        assess_block = re.search(
            r'if cmd == "assess":.*?if cmd == "group-create":',
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(assess_block, "assess command block not found")
        block = assess_block.group(0)
        self.assertNotIn("args.critical or args.repeated", block)
        self.assertNotIn("auto-derived", block)
        self.assertNotIn("or capa_required", block)


if __name__ == "__main__":
    unittest.main()
