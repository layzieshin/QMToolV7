from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from qm_platform.licensing.license_codec import encode_license_code
from qm_platform.licensing.license_schema import SCHEMA_VERSION, normalize_enabled_modules
from qm_platform.licensing.license_verifier import LicenseVerifier


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    loaded = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise ValueError("provided key is not an Ed25519 private key")
    return loaded


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_payload(
    *,
    license_id: str,
    license_type: str,
    issued_to: str,
    customer_id: str,
    issued_at: str,
    expires_at: str | None,
    enabled_modules: list[str],
    machine_id: str,
    key_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "license_id": license_id,
        "license_type": license_type,
        "issued_to": issued_to,
        "customer_id": customer_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "enabled_modules": normalize_enabled_modules(enabled_modules),
        "machine_id": machine_id,
        "key_id": key_id,
    }


def sign_payload(payload: dict[str, Any], private_key: Ed25519PrivateKey) -> dict[str, Any]:
    signed = dict(payload)
    message = LicenseVerifier.canonical_payload_bytes(signed)
    signed["signature"] = base64.b64encode(private_key.sign(message)).decode("ascii")
    return signed


def create_signed_license(
    *,
    license_type: str,
    customer_id: str,
    issued_to: str,
    machine_id: str,
    enabled_modules: list[str],
    private_key_pem: Path,
    key_id: str,
    license_id: str | None = None,
    expires_at: str | None = None,
    issued_at: str | None = None,
) -> dict[str, Any]:
    if license_type == "trial" and not expires_at:
        raise ValueError("trial license requires --expires-at")
    if license_type == "full":
        expires_at = None
    private_key = _load_private_key(private_key_pem)
    payload = build_payload(
        license_id=license_id or f"LIC-{uuid.uuid4().hex[:12].upper()}",
        license_type=license_type,
        issued_to=issued_to,
        customer_id=customer_id,
        issued_at=issued_at or _now_utc_iso(),
        expires_at=expires_at,
        enabled_modules=enabled_modules,
        machine_id=machine_id,
        key_id=key_id,
    )
    return sign_payload(payload, private_key)
