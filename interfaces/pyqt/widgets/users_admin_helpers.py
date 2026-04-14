from __future__ import annotations


class UsersAdminPresenter:
    """Extract table/filter logic from UsersAdminWidget."""

    def __init__(self) -> None:
        self._all_users: list[object] = []

    def set_users(self, users: list[object]) -> None:
        self._all_users = list(users)

    def filtered_users(self, *, search: str, selected_role: str) -> list[object]:
        normalized_search = search.strip().lower()
        rows: list[object] = []
        for user in self._all_users:
            if selected_role != "Alle" and str(user.role) != selected_role:
                continue
            if normalized_search and normalized_search not in str(user.username).lower() and normalized_search not in str(user.user_id).lower():
                continue
            rows.append(user)
        return rows
