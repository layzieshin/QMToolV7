from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.internal_license_issuer.service import IssueLicenseRequest, issue_license
from tools.internal_license_issuer.validators import (
    is_valid_machine_id,
    suggest_next_customer_id,
    trial_expires_at_days,
)
from tools.license_issuer_gui.presets import preset_by_id

_REPO_ROOT = Path(__file__).resolve().parents[2]


TEST_MACHINE = "qmt-0123456789abcdef"


def _write_temp_private_key(tmp: Path) -> Path:
    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path = tmp / "test_private.pem"
    key_path.write_bytes(pem)
    return key_path


class InternalLicenseIssuerValidatorsTest(unittest.TestCase):
    def test_machine_id_validation(self) -> None:
        self.assertTrue(is_valid_machine_id(TEST_MACHINE))
        self.assertFalse(is_valid_machine_id("qmt-short"))
        self.assertFalse(is_valid_machine_id("invalid"))

    def test_suggest_next_customer_id(self) -> None:
        self.assertEqual(suggest_next_customer_id(None), "CUST-001")
        self.assertEqual(suggest_next_customer_id("CUST-009"), "CUST-010")
        self.assertEqual(suggest_next_customer_id("other"), "CUST-001")

    def test_trial_expires_at_days_format(self) -> None:
        value = trial_expires_at_days(30)
        self.assertIn("T", value)
        self.assertTrue(value.endswith("+00:00") or value.endswith("Z") or "+" in value)

    def test_presets_exist(self) -> None:
        self.assertIsNotNone(preset_by_id("trial_30"))
        self.assertIsNotNone(preset_by_id("full"))


class InternalLicenseIssuerServiceTest(unittest.TestCase):
    def test_issue_license_writes_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key_path = _write_temp_private_key(root)
            out_dir = root / "out"
            result = issue_license(
                IssueLicenseRequest(
                    license_type="full",
                    customer_id="CUST-001",
                    issued_to="Test GmbH",
                    machine_id=TEST_MACHINE,
                    enabled_modules=["training"],
                    private_key_pem=key_path,
                    output_dir=out_dir,
                    known_module_tags={"training"},
                )
            )
            self.assertTrue(result.license_json_path and result.license_json_path.is_file())
            self.assertTrue(result.license_code_path and result.license_code_path.is_file())
            self.assertTrue(result.license_code.startswith("QMT1."))
            self.assertIn("signature", result.payload)

    def test_trial_requires_expires_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key_path = _write_temp_private_key(root)
            with self.assertRaises(ValueError):
                issue_license(
                    IssueLicenseRequest(
                        license_type="trial",
                        customer_id="CUST-001",
                        issued_to="Test GmbH",
                        machine_id=TEST_MACHINE,
                        enabled_modules=["training"],
                        private_key_pem=key_path,
                        expires_at=None,
                        known_module_tags={"training"},
                    )
                )


class GenerateProdKeypairTest(unittest.TestCase):
    def test_generate_and_verify_key_roundtrip(self) -> None:
        from tools.internal_license_issuer.generate_prod_keypair import (
            PRIVATE_FILENAME,
            PUBLIC_FILENAME,
            cmd_generate,
            cmd_verify_key,
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "secrets"
            args_generate = argparse.Namespace(output_dir=str(out_dir))
            self.assertEqual(cmd_generate(args_generate), 0)
            private_path = out_dir / PRIVATE_FILENAME
            public_path = out_dir / PUBLIC_FILENAME
            self.assertTrue(private_path.is_file())
            self.assertTrue(public_path.is_file())

            bundled_public = out_dir / "bundled_public.pem"
            bundled_public.write_text(public_path.read_text(encoding="utf-8"), encoding="utf-8")
            args_verify = argparse.Namespace(
                private_key_pem=str(private_path),
                bundled_public=str(bundled_public),
            )
            self.assertEqual(cmd_verify_key(args_verify), 0)

    def test_verify_key_fails_for_mismatched_private_key(self) -> None:
        from tools.internal_license_issuer.generate_prod_keypair import cmd_verify_key

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrong_private = _write_temp_private_key(root)
            bundled_public = _REPO_ROOT / "qm_platform" / "licensing" / "keys" / "prod_ed25519_public.pem"
            if not bundled_public.is_file():
                self.skipTest("bundled prod public key not present")
            args_verify = argparse.Namespace(
                private_key_pem=str(wrong_private),
                bundled_public=str(bundled_public),
            )
            self.assertEqual(cmd_verify_key(args_verify), 1)

    def test_verify_license_with_matching_keys(self) -> None:
        from tools.internal_license_issuer.generate_prod_keypair import (
            PRIVATE_FILENAME,
            PUBLIC_FILENAME,
            cmd_generate,
            cmd_verify_license,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "secrets"
            cmd_generate(argparse.Namespace(output_dir=str(out_dir)))
            private_path = out_dir / PRIVATE_FILENAME
            public_path = out_dir / PUBLIC_FILENAME
            result = issue_license(
                IssueLicenseRequest(
                    license_type="full",
                    customer_id="CUST-001",
                    issued_to="Verify Test",
                    machine_id=TEST_MACHINE,
                    enabled_modules=["training"],
                    private_key_pem=private_path,
                    output_dir=root / "licenses",
                    known_module_tags={"training"},
                )
            )
            assert result.license_json_path is not None
            args_verify = argparse.Namespace(
                license_json=str(result.license_json_path),
                bundled_public=str(public_path),
            )
            self.assertEqual(cmd_verify_license(args_verify), 0)
