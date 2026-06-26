from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from qm_platform.licensing.keyring import PublicKeyring
from qm_platform.licensing.license_codec import decode_license_code
from qm_platform.licensing.license_policy import LicensePolicy
from qm_platform.licensing.license_service import LicenseService
from qm_platform.licensing.license_verifier import LicenseVerifier
from qm_platform.runtime import bootstrap as runtime_bootstrap

TEST_MACHINE = "qmt-0123456789abcdef"


class LicensingIntegrationTest(unittest.TestCase):
    def test_core_license_tags_match_module_contracts(self) -> None:
        expected = sorted({c.license_tag for c in runtime_bootstrap.core_module_contracts() if c.license_tag})
        self.assertEqual(runtime_bootstrap.core_license_tags(), expected)
        self.assertEqual(expected, ["incident_management", "training"])

    def test_internal_issuer_outputs_valid_signed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key = Ed25519PrivateKey.generate()
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            private_path = root / "issuer_private.pem"
            private_path.write_bytes(private_pem)
            license_path = root / "license.json"
            code_path = root / "license.txt"

            result = subprocess.run(
                [
                    sys.executable,
                    "tools/internal_license_issuer/create_license.py",
                    "create-license",
                    "--type",
                    "trial",
                    "--customer-id",
                    "CUST-INTERNAL",
                    "--issued-to",
                    "Internal Operations",
                    "--machine-id",
                    TEST_MACHINE,
                    "--enable-module",
                    "training",
                    "--expires-at",
                    "2099-01-01T00:00:00+00:00",
                    "--private-key-pem",
                    str(private_path),
                    "--key-id",
                    "internal-key-1",
                    "--license-id",
                    "LIC-INTERNAL-001",
                    "--out",
                    str(license_path),
                    "--out-code",
                    str(code_path),
                ],
                text=True,
                capture_output=True,
                check=False,
                cwd=Path(__file__).resolve().parents[2],
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            self.assertTrue(license_path.exists())
            self.assertTrue(code_path.exists())

            public_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")
            keyring = PublicKeyring()
            keyring.add_key("internal-key-1", public_pem)
            service = LicenseService(
                license_file=license_path,
                verifier=LicenseVerifier(keyring),
                policy=LicensePolicy(local_machine_id=TEST_MACHINE),
            )
            payload = service.validate()
            self.assertEqual(payload["license_id"], "LIC-INTERNAL-001")
            self.assertTrue(service.is_module_allowed("training"))
            self.assertFalse(service.is_module_allowed("registry"))

            code_payload = decode_license_code(code_path.read_text(encoding="utf-8"))
            self.assertEqual(code_payload["license_id"], "LIC-INTERNAL-001")


if __name__ == "__main__":
    unittest.main()
