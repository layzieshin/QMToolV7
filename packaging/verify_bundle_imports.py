#!/usr/bin/env python3
"""Fail the customer build if critical runtime modules are missing from the bundle."""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

_REQUIRED_MODULES: tuple[str, ...] = (
    "fitz",
    "pypdf",
    "psycopg",
    "psycopg_binary",
)

_WINDOWS_MODULES: tuple[str, ...] = (
    "win32com.client",
    "pythoncom",
)


def _prepend_bundle_internal(bundle_dir: Path) -> Path:
    internal = bundle_dir / "_internal"
    if not internal.is_dir():
        raise FileNotFoundError(f"bundle _internal directory not found: {internal}")
    internal_str = str(internal.resolve())
    if internal_str not in sys.path:
        sys.path.insert(0, internal_str)
    return internal


def verify_bundle_imports(bundle_dir: Path) -> list[str]:
    errors: list[str] = []
    try:
        _prepend_bundle_internal(bundle_dir)
    except FileNotFoundError as exc:
        return [str(exc)]

    for module_name in _REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"missing or broken import {module_name!r}: {exc}")

    if os.name == "nt":
        for module_name in _WINDOWS_MODULES:
            try:
                importlib.import_module(module_name)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"missing or broken import {module_name!r}: {exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify critical imports in a PyInstaller onedir bundle")
    parser.add_argument("bundle_dir", type=Path, help="Path to QM-Tool bundle root")
    args = parser.parse_args()
    errors = verify_bundle_imports(args.bundle_dir.resolve())
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"OK: bundle imports ({args.bundle_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
