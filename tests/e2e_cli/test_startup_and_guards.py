from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import os
import json
import importlib.util
from pathlib import Path

from PIL import Image


def run_cli(*args: str, cwd: str | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", *args],
        text=True,
        capture_output=True,
        cwd=cwd,
        check=False,
        env=env,
    )


class StartupAndGuardsCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._env = dict(os.environ)
        self._env["QMTOOL_HOME"] = str(Path(self._tmp.name) / "home")
        init = run_cli("init", "--non-interactive", "--admin-password", "admin", env=self._env)
        assert init.returncode == 0, init.stderr + init.stdout

    def tearDown(self) -> None:
        run_cli("logout", env=self._env)
        self._tmp.cleanup()

    @staticmethod
    def _write_test_pdf(path: Path) -> None:
        if importlib.util.find_spec("pypdf") is not None:
            from pypdf import PdfWriter

            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            with path.open("wb") as fh:
                writer.write(fh)
            return
        path.write_bytes(
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000062 00000 n \n0000000117 00000 n \n"
            b"trailer << /Root 1 0 R /Size 4 >>\nstartxref\n188\n%%EOF\n"
        )

    @staticmethod
    def _write_test_png(path: Path) -> None:
        img = Image.new("RGBA", (120, 40), (255, 255, 255, 0))
        for x in range(10, 110):
            img.putpixel((x, 20), (0, 0, 0, 255))
        img.save(path, format="PNG")

    def test_health_command_runs(self) -> None:
        result = run_cli("health", env=self._env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("platform health", result.stdout)

    def test_login_success_with_default_admin(self) -> None:
        result = run_cli("login", "--username", "admin", "--password", "admin", env=self._env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("authenticated", result.stdout)

    def test_sign_visual_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "input.pdf"
            out = root / "output.pdf"
            sig = root / "sig.png"
            self._write_test_pdf(pdf)
            self._write_test_png(sig)

            result = run_cli(
                "sign",
                "visual",
                "--input",
                str(pdf),
                "--output",
                str(out),
                "--signature-png",
                str(sig),
                "--page",
                "0",
                "--x",
                "100",
                "--y",
                "100",
                "--width",
                "120",
                "--signer-user",
                "admin",
                "--password",
                "admin",
                "--dry-run",
                env=self._env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            self.assertIn("DRY-RUN", result.stdout)

    def test_sign_visual_non_dry_run_creates_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "input.pdf"
            out = root / "output.signed.pdf"
            sig = root / "sig.png"
            self._write_test_pdf(pdf)
            self._write_test_png(sig)

            result = run_cli(
                "sign",
                "visual",
                "--input",
                str(pdf),
                "--output",
                str(out),
                "--signature-png",
                str(sig),
                "--page",
                "0",
                "--x",
                "120",
                "--y",
                "120",
                "--width",
                "120",
                "--signer-user",
                "admin",
                "--password",
                "admin",
                "--name-text",
                "Admin User",
                "--date-text",
                "2026-04-08",
                env=self._env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            self.assertIn("OK: signed pdf", result.stdout)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)

    def test_sign_visual_requires_password_when_policy_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "input.pdf"
            sig = root / "sig.png"
            self._write_test_pdf(pdf)
            self._write_test_png(sig)

            result = run_cli(
                "sign",
                "visual",
                "--input",
                str(pdf),
                "--signature-png",
                str(sig),
                "--page",
                "0",
                "--x",
                "100",
                "--y",
                "100",
                "--width",
                "120",
                "--signer-user",
                "admin",
                "--dry-run",
                env=self._env,
            )
            self.assertEqual(result.returncode, 4)
            self.assertIn("password required", result.stdout.lower())

    def test_init_non_interactive_sets_hardened_seed_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["QMTOOL_HOME"] = tmp
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interfaces.cli.main",
                    "init",
                    "--non-interactive",
                    "--admin-password",
                    "strong-admin",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            payload = json.loads(result.stdout.strip() or "{}")
            self.assertEqual(payload.get("seed_mode"), "hardened")

            login = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interfaces.cli.main",
                    "login",
                    "--username",
                    "admin",
                    "--password",
                    "strong-admin",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(login.returncode, 0, msg=login.stderr + login.stdout)

    def test_doctor_reports_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["QMTOOL_HOME"] = tmp
            init_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interfaces.cli.main",
                    "init",
                    "--non-interactive",
                    "--admin-password",
                    "admin",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr + init_result.stdout)

            doctor = subprocess.run(
                [sys.executable, "-m", "interfaces.cli.main", "doctor"],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(doctor.returncode, 0, msg=doctor.stderr + doctor.stdout)
            payload = json.loads(doctor.stdout.strip() or "{}")
            self.assertTrue(payload.get("ok"), msg=doctor.stdout)

    def test_doctor_blocks_production_profile_with_legacy_seed_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["QMTOOL_HOME"] = tmp
            env["QMTOOL_RUNTIME_PROFILE"] = "production"
            doctor = subprocess.run(
                [sys.executable, "-m", "interfaces.cli.main", "doctor"],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertNotEqual(doctor.returncode, 0, msg=doctor.stderr + doctor.stdout)
            self.assertIn("seed_mode='hardened'", (doctor.stdout + doctor.stderr))

    def test_doctor_strict_reports_ok_after_hardened_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["QMTOOL_HOME"] = tmp
            init_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interfaces.cli.main",
                    "init",
                    "--non-interactive",
                    "--admin-password",
                    "admin",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr + init_result.stdout)
            doctor = subprocess.run(
                [sys.executable, "-m", "interfaces.cli.main", "doctor", "--strict"],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(doctor.returncode, 0, msg=doctor.stderr + doctor.stdout)
            payload = json.loads(doctor.stdout.strip() or "{}")
            self.assertTrue(payload.get("strict_mode"), msg=doctor.stdout)
            self.assertTrue(payload.get("checks", {}).get("security:seed_mode_hardened"), msg=doctor.stdout)
            self.assertTrue(payload.get("checks", {}).get("security:password_hashes_only"), msg=doctor.stdout)


if __name__ == "__main__":
    unittest.main()

