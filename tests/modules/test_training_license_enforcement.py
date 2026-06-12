from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from qm_platform.licensing.keyring import PublicKeyring
from qm_platform.licensing.license_guard import LicenseGuard
from qm_platform.licensing.license_policy import LicensePolicy
from qm_platform.licensing.license_service import LicenseService, ModuleNotLicensedError
from qm_platform.licensing.license_verifier import LicenseVerifier
from qm_platform.licensing.licensed_proxy import LicensedPortProxy
from tests.platform.test_license_service import TEST_MACHINE, _build_signed_payload


class _TrainingStub:
    def ping(self) -> str:
        return "ok"


class TrainingLicenseEnforcementTest(unittest.TestCase):
    def test_proxy_blocks_without_license(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        keyring = PublicKeyring()
        keyring.add_key("test-key", public_pem.decode("utf-8"))
        service = LicenseService(
            license_file=Path("missing.json"),
            verifier=LicenseVerifier(keyring),
            policy=LicensePolicy(local_machine_id=TEST_MACHINE),
        )
        guard = LicenseGuard(service)
        proxy = LicensedPortProxy(_TrainingStub(), guard, "training")
        with self.assertRaises(ModuleNotLicensedError):
            proxy.ping()

    def test_proxy_allows_with_valid_license(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        payload = _build_signed_payload(private_key)
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        keyring = PublicKeyring()
        keyring.add_key("test-key", public_pem.decode("utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            license_file = Path(tmp) / "license.json"
            license_file.write_text(__import__("json").dumps(payload), encoding="utf-8")
            service = LicenseService(
                license_file=license_file,
                verifier=LicenseVerifier(keyring),
                policy=LicensePolicy(local_machine_id=TEST_MACHINE),
            )
            guard = LicenseGuard(service)
            proxy = LicensedPortProxy(_TrainingStub(), guard, "training")
            self.assertEqual(proxy.ping(), "ok")

if __name__ == "__main__":
    unittest.main()
