from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import AuthenticatedUser


class UserRepository(ABC):
    @abstractmethod
    def get_by_username(self, username: str) -> tuple[str, str, str] | None:
        """
        Returns (user_id, password, role) for username.
        """

    @abstractmethod
    def get_user(self, username: str) -> AuthenticatedUser | None:
        pass

    @abstractmethod
    def list_users(self) -> list[AuthenticatedUser]:
        pass

    @abstractmethod
    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        *,
        is_active: bool = True,
        is_qmb: bool = False,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> AuthenticatedUser:
        pass

    @abstractmethod
    def change_password(self, username: str, new_password: str) -> None:
        pass

    @abstractmethod
    def update_user_profile(
        self,
        username: str,
        *,
        first_name: str | None,
        last_name: str | None,
        email: str | None,
        display_name: str | None = None,
    ) -> AuthenticatedUser:
        pass

    @abstractmethod
    def update_user_admin_fields(
        self,
        username: str,
        *,
        department: str | None,
        scope: str | None,
        organization_unit: str | None,
        role: str | None,
        is_active: bool | None,
        is_qmb: bool | None,
    ) -> AuthenticatedUser:
        pass

    @abstractmethod
    def ensure_seed_users(self, users: list[tuple[str, str, str]]) -> None:
        """
        Users in format: (username, password, role)
        """
