from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


class IncidentManagementCliSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._env = dict(os.environ)
        self._env["QMTOOL_HOME"] = str(Path(self._tmp.name) / "home")
        assert run_cli("init", "--non-interactive", "--admin-password", "admin", env=self._env).returncode == 0
        assert run_cli("login", "--username", "admin", "--password", "admin", env=self._env).returncode == 0

    def tearDown(self) -> None:
        run_cli("logout", env=self._env)
        self._tmp.cleanup()

    def test_settings_get(self) -> None:
        result = run_cli("incident", "settings-get", env=self._env)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertIn("categories", payload)


if __name__ == "__main__":
    unittest.main()
