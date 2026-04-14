from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    username: str
    role: str
    display_name: str | None = None
    email: str | None = None
    department: str | None = None
    scope: str | None = None
    organization_unit: str | None = None
    is_active: bool = True

