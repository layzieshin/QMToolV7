"""Register signature ports backed by HTTP (desktop/CLI - no local signature DB)."""
from __future__ import annotations

from interfaces.clients.signature_http import HttpSignatureApi


def register_signature_http_ports(container) -> None:
    api = HttpSignatureApi()
    container.register_port("signature_api", api)
    container.register_port("signature_service", api)
