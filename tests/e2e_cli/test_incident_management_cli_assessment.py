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


class IncidentManagementCliAssessmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._env = dict(os.environ)
        self._env["QMTOOL_HOME"] = str(Path(self._tmp.name) / "home")
        assert run_cli("init", "--non-interactive", "--admin-password", "adminpass01", env=self._env).returncode == 0
        assert run_cli("login", "--username", "admin", "--password", "adminpass01", env=self._env).returncode == 0
        assert run_cli("users", "create", "--username", "qmb", "--password", "qmbpass001", "--role", "QMB", env=self._env).returncode == 0
        run_cli("logout", env=self._env)
        assert run_cli("login", "--username", "qmb", "--password", "qmbpass001", env=self._env).returncode == 0

    def tearDown(self) -> None:
        run_cli("logout", env=self._env)
        self._tmp.cleanup()

    def test_assess_observation(self) -> None:
        submit = run_cli(
            "incident",
            "submit",
            "--title",
            "Assess",
            "--description",
            "D",
            "--category",
            "Prozess",
            env=self._env,
        )
        incident_id = json.loads(submit.stdout)["incident_id"]
        assess = run_cli(
            "incident",
            "assess",
            "--incident-id",
            incident_id,
            "--classification",
            "OBSERVATION",
            env=self._env,
        )
        self.assertEqual(assess.returncode, 0, assess.stderr + assess.stdout)
        self.assertEqual(json.loads(assess.stdout)["status"], "DOCUMENTATION_ONLY")

    def test_assess_critical_derives_capa_without_cli_flags(self) -> None:
        submit = run_cli(
            "incident",
            "submit",
            "--title",
            "Critical",
            "--description",
            "D",
            "--category",
            "Prozess",
            env=self._env,
        )
        incident_id = json.loads(submit.stdout)["incident_id"]
        assess = run_cli(
            "incident",
            "assess",
            "--incident-id",
            incident_id,
            "--classification",
            "ERROR",
            "--critical",
            "--critical-reason",
            "Patient safety",
            env=self._env,
        )
        self.assertEqual(assess.returncode, 0, assess.stderr + assess.stdout)
        payload = json.loads(assess.stdout)
        self.assertTrue(payload["capa_required"])
        self.assertEqual(payload["status"], "ROOT_CAUSE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
