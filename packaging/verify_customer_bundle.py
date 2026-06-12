#!/usr/bin/env python3
"""Fail the customer build if secrets or internal issuer tools are bundled."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

FORBIDDEN_PATH_PARTS = (
    "tools/internal_license_issuer",
    "tools\\internal_license_issuer",
    "scripts/license_generate.py",
    "scripts\\license_generate.py",
    "scripts/issue_production_license.py",
    "scripts\\issue_production_license.py",
)

FORBIDDEN_NAME_FRAGMENTS = (
    "private_key",
    "private.pem",
    "_private.pem",
    "_private.key",
)


def _is_private_pem(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "BEGIN PRIVATE KEY" in text or "BEGIN ENCRYPTED PRIVATE KEY" in text


def verify_bundle(bundle_dir: Path) -> list[str]:
    errors: list[str] = []
    if not bundle_dir.is_dir():
        return [f"bundle directory not found: {bundle_dir}"]

    for path in bundle_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(bundle_dir)).replace("\\", "/")
        rel_lower = rel.lower()
        for part in FORBIDDEN_PATH_PARTS:
            if part.replace("\\", "/") in rel_lower:
                errors.append(f"forbidden bundled path: {rel}")
        name_lower = path.name.lower()
        for fragment in FORBIDDEN_NAME_FRAGMENTS:
            if fragment in name_lower:
                errors.append(f"forbidden filename: {rel}")
        if path.suffix.lower() == ".pem" and _is_private_pem(path):
            errors.append(f"private key material in bundle: {rel}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify customer bundle contains no license secrets")
    parser.add_argument("bundle_dir", type=Path, help="Path to QM-Tool bundle root")
    args = parser.parse_args()
    errors = verify_bundle(args.bundle_dir.resolve())
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"OK: bundle clean ({args.bundle_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
