from __future__ import annotations


class SettingsProfilePresenter:
    @staticmethod
    def describe_session(user: object) -> str:
        return "\n".join(
            [
                f"Benutzer: {user.username}",
                f"Rolle: {user.role}",
                "Vorname, Nachname und E-Mail koennen selbst gepflegt werden.",
                "Weitere Stammdaten werden administrativ verwaltet.",
            ]
        )

    @staticmethod
    def save_result(*, username: str, profile_changed: bool, password_changed: bool) -> str:
        return (
            f"Gespeichert fuer {username}. "
            f"Profil aktualisiert: {'ja' if profile_changed else 'nein'}, "
            f"Passwort geaendert: {'ja' if password_changed else 'nein'}."
        )
