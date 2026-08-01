"""Password policy unit tests (AP-028 M5)."""
from __future__ import annotations

import pytest

from modules.usermanagement.errors import WeakPasswordError
from modules.usermanagement.password_policy import (
    DEFAULT_PASSWORD_POLICY,
    PasswordPolicy,
    password_policy_from_mapping,
    validate_password,
)
from modules.usermanagement.service import UserManagementService


def test_default_policy_accepts_ten_char_passphrase() -> None:
    validate_password("Sommer im Garten 2026", DEFAULT_PASSWORD_POLICY)
    validate_password("abcdefghij", DEFAULT_PASSWORD_POLICY)


def test_default_policy_rejects_short_password() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password("short", DEFAULT_PASSWORD_POLICY)
    with pytest.raises(WeakPasswordError):
        validate_password("123456789", DEFAULT_PASSWORD_POLICY)


def test_technical_floor_rejects_unsafe_min_length() -> None:
    with pytest.raises(ValueError, match="min_length"):
        PasswordPolicy(min_length=7)


def test_optional_character_classes() -> None:
    policy = PasswordPolicy(min_length=10, require_digit=True, require_letter=True)
    validate_password("abcdefghij1", policy)
    with pytest.raises(WeakPasswordError):
        validate_password("abcdefghij", policy)


def test_service_create_and_change_use_same_policy() -> None:
    service = UserManagementService()
    with pytest.raises(WeakPasswordError):
        service.create_user("alice", "short", "User")
    user = service.create_user("alice", "longenough1", "User")
    assert user.username == "alice"
    with pytest.raises(WeakPasswordError):
        service.change_password("alice", "tiny")
    service.change_password("alice", "newpassword")


def test_password_policy_from_mapping_defaults() -> None:
    policy = password_policy_from_mapping({})
    assert policy.min_length == 10
    assert policy.require_letter is False
