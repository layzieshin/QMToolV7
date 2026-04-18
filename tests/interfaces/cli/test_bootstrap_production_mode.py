from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_issue_module():
    path = _REPO_ROOT / "scripts" / "issue_production_license.py"
    spec = importlib.util.spec_from_file_location("issue_production_license", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load issue_production_license")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BootstrapProductionModeTest(unittest.TestCase):
    def test_missing_license_raises_clear_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            old_environ = os.environ.copy()
            os.environ["QMTOOL_HOME"] = str(home)
            os.environ["QMTOOL_LICENSE_MODE"] = "production"
            try:
                from interfaces.cli.bootstrap import build_container

                with self.assertRaises(RuntimeError) as ctx:
                    build_container()
                self.assertIn("Produktionslizenz", str(ctx.exception))
            finally:
                os.environ.clear()
                os.environ.update(old_environ)

    def test_valid_production_license_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            mod = _load_issue_module()
            mod.issue_bundle(home)
            old_environ = os.environ.copy()
            os.environ["QMTOOL_HOME"] = str(home)
            os.environ["QMTOOL_LICENSE_MODE"] = "production"
            try:
                from interfaces.cli.bootstrap import build_container

                container = build_container()
                lic = container.get_port("license_service")
                payload = lic.validate()
                self.assertEqual(payload.get("plan"), "production")
            finally:
                os.environ.clear()
                os.environ.update(old_environ)


if __name__ == "__main__":
    unittest.main()
