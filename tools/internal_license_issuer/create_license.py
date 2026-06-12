#!/usr/bin/env python3
"""Internal license issuer — NOT shipped to customers."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qm_platform.licensing.license_codec import encode_license_code
from tools.internal_license_issuer.issuer import create_signed_license


def _cmd_create_license(args: argparse.Namespace) -> int:
    private_key = Path(args.private_key_pem or os.environ.get("QMT_LICENSE_ISSUER_KEY", ""))
    if not private_key or not private_key.is_file():
        raise SystemExit(
            "Private key required: --private-key-pem or env QMT_LICENSE_ISSUER_KEY pointing to prod Ed25519 PEM"
        )
    if not args.enable_module:
        raise SystemExit("at least one --enable-module is required")
    signed = create_signed_license(
        license_type=args.type,
        customer_id=args.customer_id,
        issued_to=args.issued_to,
        machine_id=args.machine_id,
        enabled_modules=args.enable_module,
        private_key_pem=private_key,
        key_id=args.key_id,
        license_id=args.license_id,
        expires_at=args.expires_at,
    )
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(signed, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"OK: wrote {out}")
    code = encode_license_code(signed)
    if args.out_code:
        code_path = Path(args.out_code)
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text(code + "\n", encoding="utf-8")
        print(f"OK: wrote {code_path}")
    elif not args.out:
        print(code)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Internal QM-Tool license issuer (not for customer bundles)")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-license", help="Create a signed customer license")
    create.add_argument("--type", required=True, choices=["trial", "full"])
    create.add_argument("--customer-id", required=True)
    create.add_argument("--issued-to", required=True)
    create.add_argument("--machine-id", required=True)
    create.add_argument("--enable-module", action="append", required=True)
    create.add_argument("--expires-at", default=None, help="Required for trial (ISO8601)")
    create.add_argument("--private-key-pem", default=None)
    create.add_argument("--key-id", default="prod-key")
    create.add_argument("--license-id", default=None)
    create.add_argument("--out", default=None, help="Output license.json path")
    create.add_argument("--out-code", default=None, help="Output license code text file")
    create.set_defaults(func=_cmd_create_license)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
