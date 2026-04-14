from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CryptoSignRequest:
    input_pdf: Path
    output_pdf: Path
    reason: str


class CryptoSignerPort(Protocol):
    def sign(self, request: CryptoSignRequest) -> Path:
        """Apply cryptographic signature and return output path."""

