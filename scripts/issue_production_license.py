#!/usr/bin/env python3
"""Create prod Ed25519 keys and a signed license/license.json (release-time helper; not bundled in the app).

Example:
  python scripts/issue_production_license.py --output-dir ./dist/QM-Tool
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from qm_platform.licensing.license_verifier import LicenseVerifier
from qm_platform.runtime import bootstrap as runtime_bootstrap


def _write_keys(out_dir: Path, reuse_private: Path | None) -> Ed25519PrivateKey:
    lic_dir = out_dir / "storage" / "platform" / "license"
    lic_dir.mkdir(parents=True, exist_ok=True)
    priv_path = lic_dir / "prod_ed25519_private.pem"
    pub_path = lic_dir / "prod_ed25519_public.pem"
    if reuse_private is not None:
        private_key = serialization.load_pem_private_key(reuse_private.read_bytes(), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise SystemExit("Private key must be Ed25519")
    else:
        private_key = Ed25519PrivateKey.generate()
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path.write_bytes(priv_bytes)
    pub_path.write_bytes(pub_bytes)
    return private_key


def issue_bundle(output_dir: Path, *, reuse_private: Path | None = None) -> Path:
    output_dir = output_dir.resolve()
    private_key = _write_keys(output_dir, reuse_private)
    modules = sorted(set(runtime_bootstrap.core_license_tags()))
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "license_id": "PROD-LICENSE-001",
        "issued_to": "QM-Tool Customer",
        "customer_id": "CUSTOMER",
        "plan": "production",
        "issued_at": now,
        "expires_at": "2099-12-31T23:59:59+00:00",
        "enabled_modules": modules,
        "device_binding": {"mode": "optional"},
        "constraints": {},
        "key_id": "prod-key",
    }
    message = LicenseVerifier.canonical_payload_bytes(payload)
    payload["signature"] = base64.b64encode(private_key.sign(message)).decode("ascii")
    lic_file = output_dir / "license" / "license.json"
    lic_file.parent.mkdir(parents=True, exist_ok=True)
    lic_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return lic_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue production license.json and prod Ed25519 keys.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="App root (will contain license/ and storage/platform/license/).",
    )
    parser.add_argument(
        "--reuse-private-key",
        type=Path,
        default=None,
        help="Existing prod Ed25519 PKCS8 PEM to reuse instead of generating a new key.",
    )
    args = parser.parse_args()
    path = issue_bundle(args.output_dir, reuse_private=args.reuse_private_key)
    print(f"OK: wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
