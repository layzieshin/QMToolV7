"""File-PEM TLS material loading for the backend service host (OPS00-B).

Loads and validates operator-managed certificate and private-key files referenced by
``QMTOOL_TLS_CERT_FILE`` and ``QMTOOL_TLS_KEY_FILE``. Does not use the Windows
certificate store or any OS trust integration.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes

from src.backend.bootstrap import BackendBootstrapError


@dataclass(frozen=True)
class TlsMaterial:
    cert_file: str
    key_file: str


def resolve_tls_paths() -> tuple[str, str]:
    cert = os.environ.get("QMTOOL_TLS_CERT_FILE", "").strip()
    key = os.environ.get("QMTOOL_TLS_KEY_FILE", "").strip()
    return cert, key


def _public_key_matches(private_key: PrivateKeyTypes, certificate: x509.Certificate) -> bool:
    cert_public = certificate.public_key()
    key_public = private_key.public_key()
    return cert_public.public_numbers() == key_public.public_numbers()


def load_tls_material(
    *,
    cert_path: str | None = None,
    key_path: str | None = None,
) -> TlsMaterial:
    """Load and validate PEM TLS material fail-closed.

    Raises ``BackendBootstrapError`` when files are missing, unreadable, not valid PEM,
    or when the private key does not match the certificate.
    """
    resolved_cert, resolved_key = resolve_tls_paths()
    cert_file = Path((cert_path or resolved_cert).strip())
    key_file = Path((key_path or resolved_key).strip())

    missing = [
        label
        for label, path in (("QMTOOL_TLS_CERT_FILE", cert_file), ("QMTOOL_TLS_KEY_FILE", key_file))
        if not str(path).strip()
    ]
    if missing:
        raise BackendBootstrapError(
            "production profile requires TLS certificate configuration; "
            f"set {', '.join(missing)} (insecure HTTP-only bind is rejected before serving)"
        )

    absent = [
        label
        for label, path in (("QMTOOL_TLS_CERT_FILE", cert_file), ("QMTOOL_TLS_KEY_FILE", key_file))
        if not path.is_file()
    ]
    if absent:
        raise BackendBootstrapError(
            "production profile requires readable TLS certificate files; "
            f"missing or unreadable: {', '.join(absent)}"
        )

    try:
        cert_bytes = cert_file.read_bytes()
    except OSError as exc:
        raise BackendBootstrapError(
            f"QMTOOL_TLS_CERT_FILE is unreadable: {cert_file}"
        ) from exc

    try:
        key_bytes = key_file.read_bytes()
    except OSError as exc:
        raise BackendBootstrapError(
            f"QMTOOL_TLS_KEY_FILE is unreadable: {key_file}"
        ) from exc

    try:
        certificate = x509.load_pem_x509_certificate(cert_bytes)
    except ValueError as exc:
        raise BackendBootstrapError(
            f"QMTOOL_TLS_CERT_FILE is not valid PEM: {cert_file}"
        ) from exc

    try:
        private_key = serialization.load_pem_private_key(key_bytes, password=None)
    except (ValueError, TypeError) as exc:
        raise BackendBootstrapError(
            f"QMTOOL_TLS_KEY_FILE is not valid PEM private key: {key_file}"
        ) from exc

    if not _public_key_matches(private_key, certificate):
        raise BackendBootstrapError(
            "TLS certificate and private key do not match "
            f"({cert_file}, {key_file})"
        )

    return TlsMaterial(cert_file=str(cert_file), key_file=str(key_file))
