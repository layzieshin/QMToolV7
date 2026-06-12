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
from qm_platform.licensing.license_schema import SCHEMA_VERSION
from qm_platform.licensing.license_service import (
    LicenseExpiredError,
    LicenseMachineMismatchError,
    LicenseService,
)
from qm_platform.licensing.license_verifier import LicenseVerifier

TEST_MACHINE = "qmt-test1234567890"


def _build_signed_payload(
    private_key: Ed25519PrivateKey,
    *,
    license_type: str = "full",
    expires_at: str | None = None,
    enabled_modules: list[str] | None = None,
    machine_id: str = TEST_MACHINE,
    key_id: str = "test-key",
) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "license_id": "LIC-001",
        "license_type": license_type,
        "issued_to": "Demo GmbH",
        "customer_id": "CUST-1",
        "issued_at": "2026-01-01T00:00:00+00:00",
        "expires_at": expires_at,
        "enabled_modules": enabled_modules or ["training"],
        "machine_id": machine_id,
        "key_id": key_id,
    }
    message = LicenseVerifier.canonical_payload_bytes(payload)
    signature = private_key.sign(message)
    payload["signature"] = base64.b64encode(signature).decode("ascii")
    return payload


def _service(private_key: Ed25519PrivateKey, payload: dict, license_file: Path | None = None) -> LicenseService:
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    keyring = PublicKeyring()
    keyring.add_key("test-key", public_key.decode("utf-8"))
    return LicenseService(
        license_file=license_file or Path("unused.json"),
        verifier=LicenseVerifier(keyring),
        policy=LicensePolicy(local_machine_id=TEST_MACHINE),
        _payload=payload,
    )


class LicenseServiceTest(unittest.TestCase):
    def test_valid_trial_license_allows_training(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        service = _service(
            private_key,
            _build_signed_payload(
                private_key,
                license_type="trial",
                expires_at="2099-01-01T00:00:00+00:00",
            ),
        )
        self.assertTrue(service.is_module_allowed("training"))
        self.assertFalse(service.is_module_allowed("unknown"))

    def test_valid_full_license_without_expiry(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        service = _service(private_key, _build_signed_payload(private_key, license_type="full", expires_at=None))
        payload = service.validate()
        self.assertEqual(payload["license_type"], "full")
        self.assertIsNone(payload["expires_at"])

    def test_expired_trial_license_blocks(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        payload = _build_signed_payload(
            private_key,
            license_type="trial",
            expires_at="2000-01-01T00:00:00+00:00",
        )
        service = _service(private_key, payload)
        with self.assertRaises(LicenseExpiredError):
            service.validate()

    def test_wrong_machine_id_blocks(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        payload = _build_signed_payload(private_key, machine_id="qmt-wrongmachineid")
        service = _service(private_key, payload)
        with self.assertRaises(LicenseMachineMismatchError):
            service.validate()

    def test_invalid_signature_blocks(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        payload = _build_signed_payload(private_key)
        payload["signature"] = base64.b64encode(b"invalid").decode("ascii")
        service = _service(private_key, payload)
        with self.assertRaises(Exception):
            service.validate()

    def test_load_and_reload_from_file(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        payload = _build_signed_payload(private_key)
        with tempfile.TemporaryDirectory() as tmp:
            license_file = Path(tmp) / "license.json"
            license_file.write_text(json.dumps(payload), encoding="utf-8")
            public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            keyring = PublicKeyring()
            keyring.add_key("test-key", public_key.decode("utf-8"))
            service = LicenseService(
                license_file=license_file,
                verifier=LicenseVerifier(keyring),
                policy=LicensePolicy(local_machine_id=TEST_MACHINE),
            )
            loaded = service.validate()
            self.assertEqual(loaded["license_id"], "LIC-001")
            payload["customer_id"] = "CUST-2"
            license_file.write_text(json.dumps(payload), encoding="utf-8")
            reloaded = service.reload()
            self.assertEqual(reloaded["customer_id"], "CUST-2")

    def test_import_code_roundtrip(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        payload = _build_signed_payload(private_key)
        service = _service(private_key, payload)
        code = service.encode_current_code()
        with tempfile.TemporaryDirectory() as tmp:
            license_file = Path(tmp) / "license.json"
            public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            keyring = PublicKeyring()
            keyring.add_key("test-key", public_key.decode("utf-8"))
            target = LicenseService(
                license_file=license_file,
                verifier=LicenseVerifier(keyring),
                policy=LicensePolicy(local_machine_id=TEST_MACHINE),
            )
            imported = target.import_code(code)
            self.assertEqual(imported["license_id"], "LIC-001")


if __name__ == "__main__":
    unittest.main()
