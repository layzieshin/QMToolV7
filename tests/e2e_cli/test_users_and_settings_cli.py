from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


class UsersAndSettingsCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._env = dict(os.environ)
        self._env["QMTOOL_HOME"] = str(Path(self._tmp.name) / "home")
        init = run_cli("init", "--non-interactive", "--admin-password", "admin", env=self._env)
        assert init.returncode == 0, init.stderr + init.stdout
        run_cli("logout", env=self._env)

    def tearDown(self) -> None:
        run_cli("logout", env=self._env)
        self._tmp.cleanup()

    def _login(self, username: str, password: str) -> None:
        result = run_cli("login", "--username", username, "--password", password, env=self._env)
        assert result.returncode == 0, result.stderr + result.stdout

    def test_initial_admin_login_works(self) -> None:
        result = run_cli("login", "--username", "admin", "--password", "admin", env=self._env)
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        self.assertIn("authenticated", result.stdout.lower())

    def test_users_cli_create_and_list(self) -> None:
        self._login("admin", "admin")
        username = f"u_{uuid.uuid4().hex[:10]}"
        created = run_cli("users", "create", "--username", username, "--password", "pw123", "--role", "User", env=self._env)
        self.assertEqual(created.returncode, 0, msg=created.stderr + created.stdout)
        payload = json.loads(created.stdout.strip() or "{}")
        self.assertEqual(payload.get("username"), username)
        self.assertEqual(payload.get("role"), "User")

        listed = run_cli("users", "list", env=self._env)
        self.assertEqual(listed.returncode, 0, msg=listed.stderr + listed.stdout)
        rows = json.loads(listed.stdout.strip() or "[]")
        self.assertTrue(any(row.get("username") == username for row in rows))

    def test_settings_cli_list_get_set(self) -> None:
        self._login("admin", "admin")
        listed = run_cli("settings", "list-modules", env=self._env)
        self.assertEqual(listed.returncode, 0, msg=listed.stderr + listed.stdout)
        modules = json.loads(listed.stdout.strip() or "[]")
        self.assertIn("documents", modules)
        self.assertIn("signature", modules)
        self.assertIn("usermanagement", modules)

        got = run_cli("settings", "get", "--module", "documents", env=self._env)
        self.assertEqual(got.returncode, 0, msg=got.stderr + got.stdout)
        documents_settings = json.loads(got.stdout.strip() or "{}")
        self.assertIn("default_profile_id", documents_settings)

        updated = run_cli(
            "settings",
            "set",
            "--module",
            "signature",
            "--values-json",
            json.dumps({"require_password": False, "default_mode": "visual"}),
            env=self._env,
        )
        self.assertNotEqual(updated.returncode, 0, msg="governance_critical update should require explicit acknowledge flag")
        self.assertIn("governance_critical", (updated.stdout + updated.stderr))

        updated = run_cli(
            "settings",
            "set",
            "--module",
            "signature",
            "--values-json",
            json.dumps({"require_password": False, "default_mode": "visual"}),
            "--acknowledge-governance-change",
            env=self._env,
        )
        self.assertEqual(updated.returncode, 0, msg=updated.stderr + updated.stdout)
        saved = json.loads(updated.stdout.strip() or "{}")
        self.assertEqual(saved.get("require_password"), False)
        # Restore default to avoid affecting global CLI behavior tests.
        restored = run_cli(
            "settings",
            "set",
            "--module",
            "signature",
            "--values-json",
            json.dumps({"require_password": True, "default_mode": "visual"}),
            "--acknowledge-governance-change",
            env=self._env,
        )
        self.assertEqual(restored.returncode, 0, msg=restored.stderr + restored.stdout)


if __name__ == "__main__":
    unittest.main()
