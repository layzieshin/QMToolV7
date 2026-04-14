from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from qm_platform.runtime.paths import path_writable, resolve_home_path, resource_root, runtime_home


class RuntimePathsTest(unittest.TestCase):
    def test_runtime_home_prefers_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"QMTOOL_HOME": tmp}, clear=False):
                self.assertEqual(runtime_home(), Path(tmp).resolve())

    def test_runtime_home_strips_powershell_filesystem_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prefixed = f"Microsoft.PowerShell.Core\\FileSystem::{tmp}"
            with mock.patch.dict(os.environ, {"QMTOOL_HOME": prefixed}, clear=False):
                self.assertEqual(runtime_home(), Path(tmp).resolve())

    def test_resolve_home_path_relative_and_absolute(self) -> None:
        root = Path("C:/tmp-root")
        rel = resolve_home_path(root, "storage/platform/settings.json")
        self.assertEqual(rel, root / "storage/platform/settings.json")
        abs_path = resolve_home_path(root, str(Path("C:/abs/path/file.txt")))
        self.assertEqual(abs_path, Path("C:/abs/path/file.txt"))
        win_backslash = resolve_home_path(root, "D:\\data\\file.txt")
        self.assertEqual(win_backslash, Path("D:\\data\\file.txt"))
        unc = resolve_home_path(root, "\\\\server\\share\\file.txt")
        self.assertEqual(unc, Path("\\\\server\\share\\file.txt"))

    def test_path_writable_on_temp_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "logs" / "platform.log"
            self.assertTrue(path_writable(target))

    def test_resource_root_defaults_to_cwd_in_dev(self) -> None:
        expected = Path.cwd().resolve()
        self.assertEqual(resource_root(), expected)


if __name__ == "__main__":
    unittest.main()
