"""Shared license issuing service for CLI and GUI."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from qm_platform.licensing.keyring import PublicKeyring
from qm_platform.licensing.license_codec import encode_license_code
from qm_platform.licensing.license_schema import unknown_module_tags
from qm_platform.licensing.license_verifier import LicenseVerifier

from .issuer import _load_private_key, create_signed_license
from .validators import is_valid_machine_id, normalize_machine_id


@dataclass(frozen=True)
class IssueLicenseRequest:
    license_type: str
    customer_id: str
    issued_to: str
    machine_id: str
    enabled_modules: list[str]
    private_key_pem: Path
    key_id: str = "prod-key"
    license_id: str | None = None
    expires_at: str | None = None
    output_dir: Path | None = None
    known_module_tags: set[str] | None = None


@dataclass(frozen=True)
class IssueLicenseResult:
    payload: dict[str, Any]
    license_code: str
    license_json_path: Path | None
    license_code_path: Path | None


def _public_pem_from_private(private_key: Ed25519PrivateKey) -> str:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def verify_signed_payload(payload: dict[str, Any], *, public_key_pem: str | None = None) -> bool:
    keyring = PublicKeyring()
    key_id = str(payload.get("key_id", "")).strip()
    if public_key_pem:
        keyring.add_key(key_id, public_key_pem)
    else:
        return False
    verifier = LicenseVerifier(keyring=keyring)
    return verifier.verify_signature(payload)


def validate_issue_request(request: IssueLicenseRequest) -> None:
    if not request.customer_id.strip():
        raise ValueError("customer_id is required")
    if not request.issued_to.strip():
        raise ValueError("issued_to is required")
    machine_id = normalize_machine_id(request.machine_id)
    if not is_valid_machine_id(machine_id):
        raise ValueError("machine_id must match qmt- plus 16 hex characters")
    if not request.enabled_modules:
        raise ValueError("at least one enabled module is required")
    if not request.private_key_pem.is_file():
        raise ValueError(f"private key not found: {request.private_key_pem}")
    if request.license_type == "trial" and not request.expires_at:
        raise ValueError("trial license requires expires_at")
    if request.known_module_tags is not None:
        unknown = unknown_module_tags(list(request.enabled_modules), request.known_module_tags)
        if unknown:
            raise ValueError(f"unknown module tags: {', '.join(unknown)}")


def issue_license(request: IssueLicenseRequest) -> IssueLicenseResult:
    validate_issue_request(request)
    machine_id = normalize_machine_id(request.machine_id)
    signed = create_signed_license(
        license_type=request.license_type,
        customer_id=request.customer_id.strip(),
        issued_to=request.issued_to.strip(),
        machine_id=machine_id,
        enabled_modules=request.enabled_modules,
        private_key_pem=request.private_key_pem,
        key_id=request.key_id,
        license_id=request.license_id,
        expires_at=request.expires_at,
    )
    private_key = _load_private_key(request.private_key_pem)
    if not verify_signed_payload(signed, public_key_pem=_public_pem_from_private(private_key)):
        raise RuntimeError("signature verification failed after signing")

    license_code = encode_license_code(signed)
    json_path: Path | None = None
    code_path: Path | None = None
    if request.output_dir is not None:
        out_dir = request.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_customer = request.customer_id.strip().replace(" ", "_")
        json_path = out_dir / f"{safe_customer}_{machine_id}_license.json"
        code_path = out_dir / f"{safe_customer}_{machine_id}_license.txt"
        json_path.write_text(json.dumps(signed, indent=2, ensure_ascii=True), encoding="utf-8")
        code_path.write_text(license_code + "\n", encoding="utf-8")
    return IssueLicenseResult(
        payload=signed,
        license_code=license_code,
        license_json_path=json_path,
        license_code_path=code_path,
    )
