from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GoLiveGateScriptTest(unittest.TestCase):
    def test_golive_gate_static_checks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "golive.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/golive_gate.py",
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            payload = json.loads(result.stdout.strip() or "{}")
            self.assertTrue(payload.get("ok"), msg=result.stdout)
            checks = payload.get("checks", {})
            self.assertTrue(checks.get("central_governance_service_enforced"), msg=result.stdout)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
