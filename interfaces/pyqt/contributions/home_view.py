from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from interfaces.pyqt.contributions.common import normalize_role
from interfaces.pyqt.presenters.home_presenter import HomeDashboardPresenter
from interfaces.pyqt.registry.contribution import QtModuleContribution
from interfaces.pyqt.widgets.entity_cards import EntityCard
from qm_platform.runtime.container import RuntimeContainer


class HomeDashboardWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._um = container.get_port("usermanagement_service")
        self._pool = container.get_port("documents_pool_api")
        self._training = container.get_port("training_api")
        self._presenter = HomeDashboardPresenter()

        layout = QVBoxLayout(self)
        title = QLabel("Start - Persoenliches Dashboard")
        title.setObjectName("heroTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        intro = QLabel(
            "Schnellzugriff auf offene Arbeitspunkte. Die Werte werden aus bestehenden APIs gelesen, "
            "ohne eigene fachliche Logik in der GUI."
        )
        intro.setWordWrap(True)
        intro.setObjectName("heroBody")
        layout.addWidget(title)
        layout.addWidget(intro)

        refresh = QPushButton("Dashboard aktualisieren")
        refresh.clicked.connect(self._reload)
        layout.addWidget(refresh)

        self._cards: dict[str, EntityCard] = {}
        grid = QGridLayout()
        labels = [
            ("tasks", "Meine Aufgaben"),
            ("reviews", "Offene Pruefungen und Freigaben"),
            ("training", "Offene Schulungen"),
            ("recent", "Zuletzt relevante Dokumente"),
        ]
        for idx, (key, label) in enumerate(labels):
            card = EntityCard(label, on_open=lambda k=key: self._open_target_for_card(k))
            self._cards[key] = card
            col = idx % 2
            row = idx // 2
            grid.addWidget(card, row, col)
        layout.addLayout(grid, stretch=1)
        self._reload()

    def _current_user(self):
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        return user

    def _set(self, key: str, count: int, items: list[str]) -> None:
        self._cards[key].set_items(count, items)

    def _open_target_for_card(self, key: str) -> None:
        target_id = self._presenter.CARD_TARGETS.get(key)
        if target_id is None:
            return
        parent = self.parent()
        while parent is not None:
            navigate = getattr(parent, "navigate_to_contribution", None)
            if callable(navigate):
                navigate(target_id)
                return
            parent = parent.parent()

    def _reload(self) -> None:
        user = self._current_user()
        role = normalize_role(user.role)
        tasks = self._pool.list_tasks_for_user(user.user_id, role)
        review_items = self._pool.list_review_actions_for_user(user.user_id, role)
        recent_docs = self._pool.list_recent_documents_for_user(user.user_id, role)
        training_required = self._training.list_required_for_user(user.user_id)
        self._set(
            "tasks",
            len(tasks),
            self._presenter.tasks_rows(tasks),
        )
        self._set(
            "reviews",
            len(review_items),
            self._presenter.review_rows(review_items),
        )
        self._set(
            "training",
            len(training_required),
            self._presenter.training_rows(training_required),
        )
        self._set(
            "recent",
            len(recent_docs),
            self._presenter.recent_rows(recent_docs),
        )


def _build(container: RuntimeContainer) -> QWidget:
    return HomeDashboardWidget(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="shell.home",
            module_id="shell",
            title="Start",
            sort_order=0,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
