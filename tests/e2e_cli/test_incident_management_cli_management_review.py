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


class IncidentManagementCliManagementReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._env = dict(os.environ)
        self._env["QMTOOL_HOME"] = str(Path(self._tmp.name) / "home")
        assert run_cli("init", "--non-interactive", "--admin-password", "admin", env=self._env).returncode == 0
        assert run_cli("login", "--username", "admin", "--password", "admin", env=self._env).returncode == 0

    def tearDown(self) -> None:
        run_cli("logout", env=self._env)
        self._tmp.cleanup()

    def test_management_review_flow(self) -> None:
        run_cli(
            "incident",
            "submit",
            "--title",
            "MR",
            "--description",
            "D",
            "--category",
            "Prozess",
            "--reported-at",
            "2026-06-10T10:00:00+00:00",
            env=self._env,
        )
        create = run_cli(
            "incident",
            "management-review-create",
            "--period-start",
            "2026-06-01T00:00:00+00:00",
            "--period-end",
            "2026-06-30T23:59:59+00:00",
            env=self._env,
        )
        self.assertEqual(create.returncode, 0, create.stderr + create.stdout)
        batch_id = json.loads(create.stdout)["batch_id"]
        discuss = run_cli(
            "incident",
            "management-review-in-discussion",
            "--batch-id",
            batch_id,
            env=self._env,
        )
        self.assertEqual(discuss.returncode, 0)


if __name__ == "__main__":
    unittest.main()
