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
            if selected_role != "Alle" and str(getattr(user, "role", "")) != selected_role:
                continue
            if normalized_search:
                haystack = " ".join(
                    [
                        str(getattr(user, "username", "")),
                        str(getattr(user, "user_id", "")),
                        str(getattr(user, "first_name", "") or ""),
                        str(getattr(user, "last_name", "") or ""),
                    ]
                ).lower()
                if normalized_search not in haystack:
                    continue
            rows.append(user)
        return rows
