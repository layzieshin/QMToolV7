#!/usr/bin/env python3
"""Verify internal license issuer bundle contains no private keys."""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

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


def verify_issuer_bundle(bundle_dir: Path) -> list[str]:
    errors: list[str] = []
    if not bundle_dir.is_dir():
        return [f"bundle directory not found: {bundle_dir}"]

    for path in bundle_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(bundle_dir)).replace("\\", "/")
        name_lower = path.name.lower()
        for fragment in FORBIDDEN_NAME_FRAGMENTS:
            if fragment in name_lower:
                errors.append(f"forbidden filename: {rel}")
        if path.suffix.lower() == ".pem" and _is_private_pem(path):
            errors.append(f"private key material in bundle: {rel}")

    internal = bundle_dir / "_internal"
    if internal.is_dir():
        internal_str = str(internal.resolve())
        if internal_str not in sys.path:
            sys.path.insert(0, internal_str)
        try:
            importlib.import_module("cryptography")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cryptography import failed: {exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify license issuer bundle has no private keys")
    parser.add_argument("bundle_dir", type=Path, help="Path to QM-Tool-LicenseIssuer bundle root")
    args = parser.parse_args()
    errors = verify_issuer_bundle(args.bundle_dir.resolve())
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"OK: issuer bundle clean ({args.bundle_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
