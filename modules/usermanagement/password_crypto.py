from __future__ import annotations

import bcrypt


def is_password_hash(value: str) -> bool:
    return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(stored_password: str, provided_password: str) -> bool:
    if is_password_hash(stored_password):
        return bcrypt.checkpw(
            provided_password.encode("utf-8"),
            stored_password.encode("utf-8"),
        )
    return provided_password == stored_password
