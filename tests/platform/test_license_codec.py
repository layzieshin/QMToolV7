from __future__ import annotations

import unittest

from qm_platform.licensing.license_codec import decode_license_code, encode_license_code


class LicenseCodecTest(unittest.TestCase):
    def test_roundtrip(self) -> None:
        payload = {
            "schema_version": 1,
            "license_id": "LIC-CODE",
            "license_type": "trial",
            "signature": "abc",
        }
        code = encode_license_code(payload)
        self.assertTrue(code.startswith("QMT1."))
        decoded = decode_license_code(code)
        self.assertEqual(decoded["license_id"], "LIC-CODE")

    def test_invalid_code_rejected(self) -> None:
        with self.assertRaises(ValueError):
            decode_license_code("INVALID")


if __name__ == "__main__":
    unittest.main()
