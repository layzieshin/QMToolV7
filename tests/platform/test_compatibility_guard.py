from __future__ import annotations

import unittest

from qm_platform.runtime.versions import is_platform_compatible


class CompatibilityGuardTest(unittest.TestCase):
    def test_compatible_range(self) -> None:
        result = is_platform_compatible("1.0.0", None, current_version="1.0.0")
        self.assertTrue(result.ok)

    def test_incompatible_lower_bound(self) -> None:
        result = is_platform_compatible("1.1.0", None, current_version="1.0.0")
        self.assertFalse(result.ok)

    def test_incompatible_upper_bound(self) -> None:
        result = is_platform_compatible("0.9.0", "0.9.9", current_version="1.0.0")
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()

