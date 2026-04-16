"""User administration operations for the usermanagement module (SRP split B3)."""
from __future__ import annotations

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import AuthenticatedUser
from .repository import UserRepository


class UserAdminOps:
    """CRUD and admin operations on user accounts."""

    def __init__(
        self,
        repository: UserRepository | None,
        event_bus: object | None = None,
        fallback_users: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus
        self._fallback_users = fallback_users or {}

    def list_users(self) -> list[AuthenticatedUser]:
        if self._repository is not None:
            return self._repository.list_users()
        return [
            AuthenticatedUser(user_id=username, username=username, role=role)
            for username, (_password, role) in sorted(self._fallback_users.items())
        ]

    def create_user(self, username: str, password: str, role: str) -> AuthenticatedUser:
        username = username.strip()
        password = password.strip()
        role = role.strip()
        if not username:
            raise ValueError("username is required")
        if not password:
            raise ValueError("password is required")
        if role not in ("Admin", "QMB", "User"):
            raise ValueError("role must be one of: Admin, QMB, User")
        if self._repository is not None:
            user = self._repository.create_user(username, password, role)
        else:
            if username in self._fallback_users:
                raise ValueError("user already exists")
            self._fallback_users[username] = (password, role)
            user = AuthenticatedUser(user_id=username, username=username, role=role)
        self._publish(
            "domain.usermanagement.user.created.v1",
            {"username": user.username, "role": user.role},
            actor_user_id=user.user_id,
        )
        return user

    def update_user_profile(
        self,
        username: str,
        *,
        first_name: str | None,
        last_name: str | None,
        email: str | None,
        display_name: str | None = None,
    ) -> AuthenticatedUser:
        username = username.strip()
        if not username:
            raise ValueError("username is required")
        resolved_first = (first_name or "").strip() or None
        resolved_last = (last_name or "").strip() or None
        if resolved_first is None and resolved_last is None and display_name:
            parts = [p.strip() for p in display_name.split(",", 1)]
            resolved_first = parts[0] or None
            resolved_last = parts[1] if len(parts) > 1 and parts[1] else None
        name_parts = [part for part in (resolved_first, resolved_last) if part is not None]
        resolved_display = ", ".join(name_parts) if name_parts else None
        if self._repository is None:
            existing = self._fallback_users.get(username)
            if existing is None:
                raise KeyError(f"unknown user: {username}")
            _password, role = existing
            return AuthenticatedUser(
                user_id=username,
                username=username,
                role=role,
                first_name=resolved_first,
                last_name=resolved_last,
                display_name=resolved_display,
                email=email,
            )
        return self._repository.update_user_profile(
            username,
            first_name=resolved_first,
            last_name=resolved_last,
            display_name=resolved_display,
            email=email,
        )

    def update_user_admin_fields(
        self,
        username: str,
        *,
        department: str | None,
        scope: str | None,
        organization_unit: str | None,
        role: str | None,
        is_active: bool | None,
    ) -> AuthenticatedUser:
        username = username.strip()
        if not username:
            raise ValueError("username is required")
        if role is not None and role not in ("Admin", "QMB", "User"):
            raise ValueError("role must be one of: Admin, QMB, User")
        if self._repository is None:
            existing = self._fallback_users.get(username)
            if existing is None:
                raise KeyError(f"unknown user: {username}")
            password, current_role = existing
            new_role = role or current_role
            self._fallback_users[username] = (password, new_role)
            return AuthenticatedUser(
                user_id=username,
                username=username,
                role=new_role,
                department=department,
                scope=scope,
                organization_unit=organization_unit,
                is_active=is_active if is_active is not None else True,
            )
        return self._repository.update_user_admin_fields(
            username,
            department=department,
            scope=scope,
            organization_unit=organization_unit,
            role=role,
            is_active=is_active,
        )

    def set_user_active(self, username: str, is_active: bool) -> AuthenticatedUser:
        return self.update_user_admin_fields(
            username,
            department=None,
            scope=None,
            organization_unit=None,
            role=None,
            is_active=is_active,
        )

    def change_password(self, username: str, new_password: str) -> None:
        username = username.strip()
        new_password = new_password.strip()
        if not username:
            raise ValueError("username is required")
        if not new_password:
            raise ValueError("new_password is required")
        if self._repository is not None:
            self._repository.change_password(username, new_password)
            user = self._repository.get_by_username(username)
            actor_user_id = user[0] if user else None
        else:
            if username not in self._fallback_users:
                raise KeyError(f"unknown user: {username}")
            _old_password, role = self._fallback_users[username]
            self._fallback_users[username] = (new_password, role)
            actor_user_id = username
        self._publish(
            "domain.usermanagement.user.password_changed.v1",
            {"username": username},
            actor_user_id=actor_user_id,
        )

    def ensure_admin_credentials(self, username: str, password: str, role: str = "Admin") -> AuthenticatedUser:
        username = username.strip()
        password = password.strip()
        role = role.strip()
        if not username:
            raise ValueError("username is required")
        if not password:
            raise ValueError("password is required")
        if role not in ("Admin", "QMB", "User"):
            raise ValueError("role must be one of: Admin, QMB, User")
        existing = None
        if self._repository is not None:
            existing = self._repository.get_by_username(username)
        else:
            in_memory = self._fallback_users.get(username)
            existing = (username, in_memory[0], in_memory[1]) if in_memory else None
        if existing is None:
            return self.create_user(username, password, role)
        self.change_password(username, password)
        if self._repository is not None:
            return self._repository.get_user(username) or AuthenticatedUser(user_id=existing[0], username=username, role=existing[2])
        current = self._fallback_users.get(username)
        resolved_role = current[1] if current is not None else existing[2]
        return AuthenticatedUser(user_id=existing[0], username=username, role=resolved_role)

    # -- internal ------------------------------------------------------------

    def _publish(self, name: str, payload: dict, actor_user_id: str | None = None) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if not callable(publish):
            return
        publish(
            EventEnvelope.create(
                name=name,
                module_id="usermanagement",
                payload=payload,
                actor_user_id=actor_user_id,
            )
        )

