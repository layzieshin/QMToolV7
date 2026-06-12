from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


class BootstrapProductionModeTest(unittest.TestCase):
    def test_missing_license_does_not_block_startup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            old_environ = os.environ.copy()
            os.environ["QMTOOL_HOME"] = str(home)
            os.environ["QMTOOL_LICENSE_MODE"] = "production"
            try:
                from interfaces.cli.bootstrap import build_container
                from qm_platform.runtime import bootstrap as runtime_bootstrap

                container = build_container()
                lifecycle = runtime_bootstrap.register_core_modules(container)
                lifecycle.start(strict=False)
                self.assertIn("training", lifecycle.failed_modules())
            finally:
                os.environ.clear()
                os.environ.update(old_environ)

    def test_dev_autogen_enables_training_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            old_environ = os.environ.copy()
            os.environ["QMTOOL_HOME"] = str(home)
            os.environ["QMTOOL_LICENSE_MODE"] = "dev"
            try:
                from interfaces.cli.bootstrap import build_container
                from qm_platform.runtime import bootstrap as runtime_bootstrap

                container = build_container()
                lifecycle = runtime_bootstrap.register_core_modules(container)
                lifecycle.start(strict=False)
                self.assertNotIn("training", lifecycle.failed_modules())
                lic = container.get_port("license_service")
                self.assertTrue(lic.is_module_allowed("training"))
            finally:
                os.environ.clear()
                os.environ.update(old_environ)


if __name__ == "__main__":
    unittest.main()
