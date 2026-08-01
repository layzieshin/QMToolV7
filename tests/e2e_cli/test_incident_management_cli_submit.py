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


class IncidentManagementCliSubmitTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._env = dict(os.environ)
        self._env["QMTOOL_HOME"] = str(Path(self._tmp.name) / "home")
        init = run_cli("init", "--non-interactive", "--admin-password", "adminpass01", env=self._env)
        assert init.returncode == 0, init.stderr + init.stdout
        assert run_cli("login", "--username", "admin", "--password", "adminpass01", env=self._env).returncode == 0

    def tearDown(self) -> None:
        run_cli("logout", env=self._env)
        self._tmp.cleanup()

    def test_submit_get_list(self) -> None:
        submit = run_cli(
            "incident",
            "submit",
            "--title",
            "CLI Event",
            "--description",
            "From CLI",
            "--category",
            "Prozess",
            env=self._env,
        )
        self.assertEqual(submit.returncode, 0, submit.stderr + submit.stdout)
        payload = json.loads(submit.stdout)
        incident_id = payload["incident_id"]
        get = run_cli("incident", "get", "--incident-id", incident_id, env=self._env)
        self.assertEqual(get.returncode, 0)
        listed = run_cli("incident", "list", env=self._env)
        self.assertEqual(listed.returncode, 0)
        rows = json.loads(listed.stdout)
        self.assertTrue(any(r["incident_id"] == incident_id for r in rows))


if __name__ == "__main__":
    unittest.main()
