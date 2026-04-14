from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from qm_platform.licensing.keyring import PublicKeyring
from qm_platform.licensing.license_policy import LicensePolicy
from qm_platform.licensing.license_service import LicenseExpiredError, LicenseService
from qm_platform.licensing.license_verifier import LicenseVerifier


def _build_signed_payload(private_key: Ed25519PrivateKey) -> dict:
    payload = {
        "license_id": "LIC-001",
        "issued_to": "Demo GmbH",
        "customer_id": "CUST-1",
        "plan": "pro",
        "issued_at": "2026-01-01T00:00:00+00:00",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "enabled_modules": ["documents", "signature"],
        "device_binding": {"mode": "optional"},
        "constraints": {},
        "key_id": "test-key",
    }
    message = LicenseVerifier.canonical_payload_bytes(payload)
    signature = private_key.sign(message)
    payload["signature"] = base64.b64encode(signature).decode("ascii")
    return payload


class LicenseServiceTest(unittest.TestCase):
    def test_valid_license_allows_module(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        keyring = PublicKeyring()
        keyring.add_key("test-key", public_key.decode("utf-8"))
        service = LicenseService(
            license_file=Path("unused.json"),
            verifier=LicenseVerifier(keyring),
            policy=LicensePolicy(),
            _payload=_build_signed_payload(private_key),
        )
        self.assertTrue(service.is_module_allowed("documents"))
        self.assertFalse(service.is_module_allowed("word_meta"))

    def test_expired_license_blocks(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        payload = _build_signed_payload(private_key)
        payload["expires_at"] = "2000-01-01T00:00:00+00:00"
        # Re-sign because payload changed.
        payload_no_sig = dict(payload)
        payload_no_sig.pop("signature", None)
        payload["signature"] = base64.b64encode(private_key.sign(LicenseVerifier.canonical_payload_bytes(payload_no_sig))).decode(
            "ascii"
        )

        keyring = PublicKeyring()
        keyring.add_key("test-key", public_key.decode("utf-8"))
        service = LicenseService(
            license_file=Path("unused.json"),
            verifier=LicenseVerifier(keyring),
            policy=LicensePolicy(),
            _payload=payload,
        )
        with self.assertRaises(LicenseExpiredError):
            service.validate()

    def test_load_license_from_file(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        payload = _build_signed_payload(private_key)

        with tempfile.TemporaryDirectory() as tmp:
            license_file = Path(tmp) / "license.json"
            license_file.write_text(json.dumps(payload), encoding="utf-8")
            keyring = PublicKeyring()
            keyring.add_key("test-key", public_key.decode("utf-8"))
            service = LicenseService(
                license_file=license_file,
                verifier=LicenseVerifier(keyring),
                policy=LicensePolicy(),
            )
            loaded = service.validate()
            self.assertEqual(loaded["license_id"], "LIC-001")


if __name__ == "__main__":
    unittest.main()

