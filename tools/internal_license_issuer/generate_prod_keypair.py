#!/usr/bin/env python3
"""Generate or verify the production Ed25519 key pair (operator tool, not shipped)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qm_platform.licensing.keyring import PublicKeyring
from qm_platform.licensing.license_verifier import LicenseVerifier

DEFAULT_BUNDLED_PUBLIC = ROOT / "qm_platform" / "licensing" / "keys" / "prod_ed25519_public.pem"
PRIVATE_FILENAME = "prod_ed25519_private.pem"
PUBLIC_FILENAME = "prod_ed25519_public.pem"


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    loaded = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise ValueError("provided key is not an Ed25519 private key")
    return loaded


def _public_pem_from_private(private_key: Ed25519PrivateKey) -> str:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def _read_public_pem(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"bundled public key not found: {path}")
    return path.read_text(encoding="utf-8")


def cmd_generate(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    private_path = out_dir / PRIVATE_FILENAME
    public_path = out_dir / PUBLIC_FILENAME
    if private_path.exists() or public_path.exists():
        raise SystemExit(f"refusing to overwrite existing key files in {out_dir}")

    private_key = Ed25519PrivateKey.generate()
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_text(_public_pem_from_private(private_key), encoding="utf-8")

    print(f"OK: wrote {private_path}")
    print(f"OK: wrote {public_path}")
    print()
    print("Next steps:")
    print(f"  1. Back up {PRIVATE_FILENAME} outside the repository (never commit it).")
    print(f"  2. Copy {PUBLIC_FILENAME} to {DEFAULT_BUNDLED_PUBLIC}")
    print("  3. Rebuild the customer bundle: python packaging/build_onedir.py")
    print("  4. Point the license issuer at the private key (QMT_LICENSE_ISSUER_KEY or GUI path).")
    print(
        f"  5. Verify: python tools/internal_license_issuer/generate_prod_keypair.py "
        f"verify-key --private-key-pem {private_path}"
    )
    return 0


def cmd_verify_key(args: argparse.Namespace) -> int:
    private_path = Path(args.private_key_pem)
    bundled_public_path = Path(args.bundled_public or DEFAULT_BUNDLED_PUBLIC)
    derived_public = _public_pem_from_private(_load_private_key(private_path))
    bundled_public = _read_public_pem(bundled_public_path)
    match = derived_public.strip() == bundled_public.strip()
    print(f"private key: {private_path}")
    print(f"bundled public: {bundled_public_path}")
    print(f"keys match: {match}")
    if not match:
        print()
        print("This private key cannot sign licenses for the current customer build.")
        print("Use the matching prod private key, or install a new public key and rebuild QM-Tool.")
        return 1
    return 0


def cmd_verify_license(args: argparse.Namespace) -> int:
    license_path = Path(args.license_json)
    bundled_public_path = Path(args.bundled_public or DEFAULT_BUNDLED_PUBLIC)
    payload = json.loads(license_path.read_text(encoding="utf-8"))
    key_id = str(payload.get("key_id", "")).strip() or "prod-key"
    keyring = PublicKeyring()
    keyring.add_key(key_id, _read_public_pem(bundled_public_path))
    ok = LicenseVerifier(keyring=keyring).verify_signature(payload)
    print(f"license: {license_path}")
    print(f"bundled public: {bundled_public_path}")
    print(f"key_id: {key_id}")
    print(f"signature valid for customer build: {ok}")
    if not ok:
        print()
        print("Typical cause: license signed with a different private key (often the auto-generated dev key).")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the production Ed25519 key pair (operator tool, not for customer bundles)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="Create a new prod Ed25519 key pair in an output directory")
    generate.add_argument(
        "--output-dir",
        required=True,
        help="Directory outside the repo, e.g. ../qmtool-license-secrets",
    )
    generate.set_defaults(func=cmd_generate)

    verify_key = sub.add_parser(
        "verify-key",
        help="Check whether a private key matches the bundled prod public key in this repository",
    )
    verify_key.add_argument("--private-key-pem", required=True)
    verify_key.add_argument("--bundled-public", default=None)
    verify_key.set_defaults(func=cmd_verify_key)

    verify_license = sub.add_parser(
        "verify-license",
        help="Check whether a license.json verifies against the bundled prod public key",
    )
    verify_license.add_argument("--license-json", required=True)
    verify_license.add_argument("--bundled-public", default=None)
    verify_license.set_defaults(func=cmd_verify_license)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
