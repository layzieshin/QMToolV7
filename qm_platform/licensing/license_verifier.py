from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .keyring import PublicKeyring


@dataclass
class LicenseVerifier:
    keyring: PublicKeyring

    @staticmethod
    def canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
        signing_payload = dict(payload)
        signing_payload.pop("signature", None)
        canonical_json = json.dumps(signing_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return canonical_json.encode("utf-8")

    def verify_signature(self, payload: dict[str, Any]) -> bool:
        key_id = str(payload.get("key_id", "")).strip()
        signature = str(payload.get("signature", "")).strip()
        if not key_id or not signature:
            return False
        try:
            pem = self.keyring.get_key(key_id).encode("utf-8")
            public_key = serialization.load_pem_public_key(pem)
            if not isinstance(public_key, Ed25519PublicKey):
                return False
            signature_bytes = base64.b64decode(signature, validate=True)
            message = self.canonical_payload_bytes(payload)
            public_key.verify(signature_bytes, message)
            return True
        except (KeyError, ValueError, InvalidSignature, TypeError):
            return False

