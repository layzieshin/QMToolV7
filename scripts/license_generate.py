from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qm_platform.licensing.license_verifier import LicenseVerifier


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    loaded = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise ValueError("provided key is not an Ed25519 private key")
    return loaded


def build_payload(
    *,
    license_id: str,
    issued_to: str,
    customer_id: str,
    plan: str,
    issued_at: str,
    expires_at: str,
    enabled_modules: list[str],
    key_id: str,
) -> dict[str, object]:
    return {
        "license_id": license_id,
        "issued_to": issued_to,
        "customer_id": customer_id,
        "plan": plan,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "enabled_modules": sorted(set(enabled_modules)),
        "device_binding": {"mode": "optional"},
        "constraints": {},
        "key_id": key_id,
    }


def sign_payload(payload: dict[str, object], private_key: Ed25519PrivateKey) -> dict[str, object]:
    signed = dict(payload)
    message = LicenseVerifier.canonical_payload_bytes(signed)
    signed["signature"] = base64.b64encode(private_key.sign(message)).decode("ascii")
    return signed


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate signed module license JSON")
    parser.add_argument("--output", required=True, help="Output path for generated license.json")
    parser.add_argument("--private-key-pem", required=True, help="Path to Ed25519 private key (PEM)")
    parser.add_argument("--key-id", required=True, help="Key id referenced by runtime keyring")
    parser.add_argument("--license-id", required=True)
    parser.add_argument("--issued-to", required=True)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--plan", default="internal")
    parser.add_argument("--issued-at", default=_now_utc_iso())
    parser.add_argument("--expires-at", required=True)
    parser.add_argument(
        "--enable-module",
        dest="enabled_modules",
        action="append",
        default=[],
        help="Enable one module tag; can be repeated",
    )
    args = parser.parse_args()

    if not args.enabled_modules:
        raise ValueError("at least one --enable-module is required")

    private_key = _load_private_key(Path(args.private_key_pem))
    payload = build_payload(
        license_id=args.license_id,
        issued_to=args.issued_to,
        customer_id=args.customer_id,
        plan=args.plan,
        issued_at=args.issued_at,
        expires_at=args.expires_at,
        enabled_modules=args.enabled_modules,
        key_id=args.key_id,
    )
    signed = sign_payload(payload, private_key)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(signed, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "enabled_modules": signed["enabled_modules"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
