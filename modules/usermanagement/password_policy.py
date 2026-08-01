"""Central password policy for Usermanagement (AP-028 M5).

All password-setting paths (create, change, bootstrap, reset) must call
``validate_password``. HTTP adapters must not reimplement these rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import WeakPasswordError

TECHNICAL_MIN_LENGTH_FLOOR = 8
DEFAULT_MIN_LENGTH = 10


@dataclass(frozen=True)
class PasswordPolicy:
    min_length: int = DEFAULT_MIN_LENGTH
    require_letter: bool = False
    require_digit: bool = False
    require_uppercase: bool = False
    require_special: bool = False

    def __post_init__(self) -> None:
        if self.min_length < TECHNICAL_MIN_LENGTH_FLOOR:
            raise ValueError(
                f"password_policy.min_length must be >= {TECHNICAL_MIN_LENGTH_FLOOR}"
            )


DEFAULT_PASSWORD_POLICY = PasswordPolicy()


def password_policy_from_mapping(raw: Mapping[str, Any] | None) -> PasswordPolicy:
    """Build a policy from settings; missing keys use defaults."""
    data = dict(raw or {})
    return PasswordPolicy(
        min_length=int(data.get("min_length", DEFAULT_MIN_LENGTH)),
        require_letter=bool(data.get("require_letter", False)),
        require_digit=bool(data.get("require_digit", False)),
        require_uppercase=bool(data.get("require_uppercase", False)),
        require_special=bool(data.get("require_special", False)),
    )


def validate_password(password: str, policy: PasswordPolicy | None = None) -> None:
    """Raise ``WeakPasswordError`` when the password violates the policy.

    Empty strings and whitespace-only values are always rejected here so HTTP
    and service paths share one owner for password-setting validation.
    """
    active = policy or DEFAULT_PASSWORD_POLICY
    raw = password if isinstance(password, str) else ""
    value = raw.strip()
    if not value:
        raise WeakPasswordError("password does not meet policy")
    if len(value) < active.min_length:
        raise WeakPasswordError("password does not meet policy")
    if active.require_letter and not any(ch.isalpha() for ch in value):
        raise WeakPasswordError("password does not meet policy")
    if active.require_digit and not any(ch.isdigit() for ch in value):
        raise WeakPasswordError("password does not meet policy")
    if active.require_uppercase and not any(ch.isupper() for ch in value):
        raise WeakPasswordError("password does not meet policy")
    if active.require_special and not any(not ch.isalnum() and not ch.isspace() for ch in value):
        raise WeakPasswordError("password does not meet policy")
