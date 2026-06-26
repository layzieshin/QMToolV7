"""Training workspace - dreigeteilte Ansicht.

Upper bar: Admin/QMB actions (Import Quiz, Quiz zuordnen, Statistik/Logs, Kommentare)
Middle: Nutzerabhaengige Dokumentenliste (materialisierte Inbox)
Lower bar: Kontextbezogene Aktionen (Quiz starten, Lesen, Quiz kommentieren)
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.training_sections.admin_section import TrainingAdminSection
from interfaces.pyqt.contributions.training_sections.inbox_section import TrainingInboxSection
from interfaces.pyqt.contributions.training_sections.user_actions_section import TrainingUserActionsSection
from interfaces.pyqt.logging_adapter import get_logger
from interfaces.pyqt.presenters.training_presenter import TrainingPresenter
from interfaces.pyqt.registry.contribution import QtModuleContribution
from qm_platform.runtime.container import RuntimeContainer


# ---------------------------------------------------------------------------
# Main workspace widget
# ---------------------------------------------------------------------------

class TrainingWorkspace(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._logger = get_logger(__name__)
        self._container = container
        self._api = container.get_port("training_api")
        self._um = container.get_port("usermanagement_service")
        self._read_api = container.get_port("documents_read_api")
        self._artifacts = container.get_port("documents_artifacts_api")
        self._presenter = TrainingPresenter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- UPPER: Admin bar ---
        self._admin_bar = TrainingAdminSection(
            training_admin_api=container.get_port("training_admin_api"),
            usermanagement_service=self._um,
            selected_item_provider=lambda: self._inbox_section.current_item(),
            reload_inbox=lambda: self._inbox_section.load_inbox(),
            append_status_log=self._append_status_log,
            show_error=self._show_error,
            parent=self,
        )
        layout.addWidget(self._admin_bar)

        # --- MIDDLE: Inbox table ---
        self._inbox_section = TrainingInboxSection(
            training_api=self._api,
            presenter=self._presenter,
            current_user_provider=self._current_user_or_none,
            append_status_log=self._append_status_log,
            show_error=self._show_error,
            set_output_text=self._set_output_text,
            clear_output=self._clear_output,
            update_action_state=self._update_action_state,
            parent=self,
        )
        layout.addWidget(self._inbox_section, stretch=3)

        # --- LOWER: Context action bar ---
        self._user_actions_section = TrainingUserActionsSection(
            training_api=self._api,
            documents_read_api=self._read_api,
            documents_artifacts_api=self._artifacts,
            usermanagement_service=self._um,
            presenter=self._presenter,
            current_item_provider=self._inbox_section.current_item,
            reload_inbox=self._inbox_section.load_inbox,
            append_status_log=self._append_status_log,
            show_error=self._show_error,
            parent=self,
        )
        layout.addWidget(self._user_actions_section)

        # --- Output log ---
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setMaximumHeight(120)
        self._out.setVisible(False)
        self._btn_toggle_log = QPushButton("Protokoll anzeigen")
        self._btn_toggle_log.clicked.connect(self._toggle_log_visibility)
        layout.addWidget(self._btn_toggle_log)
        layout.addWidget(self._out, stretch=1)

        # --- Init ---
        self.refresh_for_session()

    # ---- Role visibility ----

    def _current_user_or_none(self):
        return self._um.get_current_user()

    def refresh_for_session(self) -> None:
        self._apply_role_visibility()
        self._inbox_section.load_inbox()
        self._update_action_state()

    def _apply_role_visibility(self) -> None:
        user = self._current_user_or_none()
        is_admin = self._presenter.is_privileged_for_training(user)
        self._admin_bar.setVisible(is_admin)

    # ---- Selection / action state ----

    def _update_action_state(self) -> None:
        self._user_actions_section.update_action_state()

    # ---- Helpers ----

    def _append_status_log(self, msg: str) -> None:
        """Append to the training protocol widget and mirror to the main window status bar."""
        self._out.appendPlainText(msg)
        window = self.window()
        if hasattr(window, "statusBar"):
            try:
                window.statusBar().showMessage(msg, 10000)
            except Exception:  # noqa: BLE001
                self._logger.exception("Training status bar update failed")

    def _set_output_text(self, text: str) -> None:
        self._out.setPlainText(text)

    def _clear_output(self) -> None:
        self._out.clear()

    def _show_error(self, exc: Exception) -> None:
        QMessageBox.warning(self, "Training", str(exc))
        self._out.appendPlainText(f"FEHLER: {exc}")
        window = self.window()
        if hasattr(window, "statusBar"):
            try:
                window.statusBar().showMessage(f"FEHLER: {exc}", 10000)
            except Exception:  # noqa: BLE001
                self._logger.exception("Training status bar error update failed")

    def _toggle_log_visibility(self) -> None:
        visible = not self._out.isVisible()
        self._out.setVisible(visible)
        self._btn_toggle_log.setText("Protokoll ausblenden" if visible else "Protokoll anzeigen")


# ---------------------------------------------------------------------------
# Contribution registration
# ---------------------------------------------------------------------------

def _build(container: RuntimeContainer) -> QWidget:
    return TrainingWorkspace(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="training.workspace",
            module_id="training",
            title="Schulung",
            sort_order=40,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
