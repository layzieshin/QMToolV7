from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PublicKeyring:
    _keys: dict[str, str] = field(default_factory=dict)

    def add_key(self, key_id: str, public_key_pem: str) -> None:
        self._keys[key_id] = public_key_pem

    def has_key(self, key_id: str) -> bool:
        return key_id in self._keys

    def get_key(self, key_id: str) -> str:
        if key_id not in self._keys:
            raise KeyError(f"unknown key_id: {key_id}")
        return self._keys[key_id]

