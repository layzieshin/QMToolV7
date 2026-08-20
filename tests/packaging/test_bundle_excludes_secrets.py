from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _load_verify():
    path = _REPO / "packaging" / "verify_customer_bundle.py"
    spec = importlib.util.spec_from_file_location("verify_customer_bundle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load verify_customer_bundle")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BundleExcludesSecretsTest(unittest.TestCase):
    def test_detects_private_key_and_issuer(self) -> None:
        verify_bundle = _load_verify().verify_bundle
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            priv = root / "storage/platform/license/prod_ed25519_private.pem"
            priv.parent.mkdir(parents=True, exist_ok=True)
            priv.write_text(
                "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
                encoding="utf-8",
            )
            issuer = root / "tools/internal_license_issuer/create_license.py"
            issuer.parent.mkdir(parents=True, exist_ok=True)
            issuer.write_text("# issuer", encoding="utf-8")
            errors = verify_bundle(root)
            self.assertGreater(len(errors), 0)

    def test_detects_env_db_and_evidence_artifacts(self) -> None:
        verify_bundle = _load_verify().verify_bundle
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_file = root / ".env"
            env_file.write_text("QMTOOL_PG_PASSWORD=secret\n", encoding="utf-8")
            db_file = root / "storage/documents/documents.db"
            db_file.parent.mkdir(parents=True, exist_ok=True)
            db_file.write_bytes(b"sqlite")
            evidence = root / ".j04_g3_evidence/run.txt"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text("log", encoding="utf-8")
            errors = verify_bundle(root)
            joined = "\n".join(errors)
            self.assertIn(".env", joined)
            self.assertIn(".db", joined)
            self.assertIn("evidence", joined)

    def test_clean_bundle_passes(self) -> None:
        verify_bundle = _load_verify().verify_bundle
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pub = root / "qm_platform/licensing/keys/prod_ed25519_public.pem"
            pub.parent.mkdir(parents=True, exist_ok=True)
            pub.write_text("-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----\n", encoding="utf-8")
            errors = verify_bundle(root)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
