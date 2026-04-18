from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    username: str
    role: str
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    email: str | None = None
    department: str | None = None
    scope: str | None = None
    organization_unit: str | None = None
    is_active: bool = True
    is_qmb: bool = False
    must_change_password: bool = False

