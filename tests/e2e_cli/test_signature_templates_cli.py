from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


class SignatureTemplatesCliTest(unittest.TestCase):
    @staticmethod
    def _create_pdf(path: Path) -> None:
        path.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n")

    def test_template_asset_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = dict(os.environ)
            env["QMTOOL_HOME"] = str(root / "home")
            init = run_cli("init", "--non-interactive", "--admin-password", "admin", env=env)
            self.assertEqual(init.returncode, 0, msg=init.stderr + init.stdout)
            gif_path = root / "sig.gif"
            Image.new("RGBA", (32, 16), (0, 0, 0, 255)).save(gif_path, format="GIF")
            pdf = root / "input.pdf"
            self._create_pdf(pdf)

            imported = run_cli("sign", "import-asset", "--owner-user-id", "admin", "--input", str(gif_path), env=env)
            self.assertEqual(imported.returncode, 0, msg=imported.stderr + imported.stdout)
            asset_payload = json.loads(imported.stdout.strip() or "{}")
            asset_id = asset_payload.get("asset_id")
            self.assertTrue(asset_id)

            created = run_cli(
                "sign",
                "template-create",
                "--owner-user-id",
                "admin",
                "--name",
                "std",
                "--asset-id",
                str(asset_id),
                "--x",
                "10",
                "--y",
                "10",
                "--width",
                "80",
                env=env,
            )
            self.assertEqual(created.returncode, 0, msg=created.stderr + created.stdout)
            template_payload = json.loads(created.stdout.strip() or "{}")
            template_id = template_payload.get("template_id")
            self.assertTrue(template_id)

            listed = run_cli("sign", "template-list", "--owner-user-id", "admin", env=env)
            self.assertEqual(listed.returncode, 0, msg=listed.stderr + listed.stdout)
            rows = json.loads(listed.stdout.strip() or "[]")
            self.assertTrue(any(r.get("template_id") == template_id for r in rows))

            signed = run_cli(
                "sign",
                "template-sign",
                "--template-id",
                str(template_id),
                "--input",
                str(pdf),
                "--signer-user",
                "admin",
                "--password",
                "admin",
                "--dry-run",
                env=env,
            )
            self.assertEqual(signed.returncode, 0, msg=signed.stderr + signed.stdout)
            self.assertIn("DRY-RUN", signed.stdout)


if __name__ == "__main__":
    unittest.main()
