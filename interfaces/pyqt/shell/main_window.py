from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.registry.catalog import all_contributions
from interfaces.pyqt.registry.contribution import QtModuleContribution
from interfaces.pyqt.runtime.host import RuntimeHost
from interfaces.pyqt.shell.preferences import ShellPreferences
from interfaces.pyqt.shell.session_coordinator import SessionCoordinator
from interfaces.pyqt.shell.visibility_policy import ContributionVisibilityPolicy, normalize_role
from interfaces.pyqt.logging_adapter import get_logger
from interfaces.pyqt.widgets.force_password_change_dialog import ForcePasswordChangeDialog
from interfaces.pyqt.widgets.register_dialog import RegisterDialog
from interfaces.clients.auth_messages import user_facing_auth_message

_CONTRIBUTION_ROLE = Qt.ItemDataRole.UserRole + 1


class _LoginDialog(QDialog):
    def __init__(
        self,
        usermanagement_service,
        parent: QWidget | None = None,
        *,
        allow_local_register: bool = True,
    ) -> None:
        super().__init__(parent)
        self._um = usermanagement_service
        self.setWindowTitle("Anmelden")
        self._user = QLineEdit()
        self._pw = QLineEdit()
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        if allow_local_register:
            register_btn = buttons.addButton("Neu registrieren...", QDialogButtonBox.ButtonRole.ActionRole)
            register_btn.clicked.connect(self._open_register)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow("Benutzername", self._user)
        form.addRow("Passwort", self._pw)
        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addWidget(buttons)

    def credentials(self) -> tuple[str, str]:
        return self._user.text().strip(), self._pw.text()

    def _open_register(self) -> None:
        dlg = RegisterDialog(self._um, self)
        dlg.exec()


class MainWindow(QMainWindow):
    """
    Host shell with strict login-gate.

    - No module navigation before explicit login.
    - Contributions are filtered by role metadata.
    - Session is explicitly logged out on close.
    """

    def __init__(self, host: RuntimeHost) -> None:
        super().__init__()
        self._log = get_logger(__name__)
        self._host = host
        ordered = all_contributions()
        try:
            enabled_ids = frozenset(
                self._host.require_container().get_port("enabled_pyqt_contribution_ids")
            )
        except (KeyError, RuntimeError, TypeError):
            enabled_ids = frozenset(c.contribution_id for c in ordered)
        ordered = [c for c in ordered if c.contribution_id in enabled_ids]
        self._all_contributions: dict[str, QtModuleContribution] = {c.contribution_id: c for c in ordered}
        self._visible_ids: list[str] = []
        self._lazy_widgets: dict[str, QWidget] = {}
        self._session_fingerprint: tuple[str, str] | None = None
        self._stopping = False
        self._backup_reminder_shown_for_session = False
        self._preferences = ShellPreferences()
        self._debug_toggle_enabled = self._preferences.load_admin_debug_toggle()
        self._visibility_policy = ContributionVisibilityPolicy()
        backend_session = None
        try:
            backend_session = self._host.require_container().get_port("backend_session_api")
        except Exception:  # noqa: BLE001
            backend_session = None
        self._session = SessionCoordinator(self._um(), backend_session=backend_session)

        self.setWindowTitle("QM-Tool")
        self.resize(1240, 760)

        self._nav = QListWidget()
        self._nav.setMinimumWidth(232)
        self._nav.setSpacing(2)
        self._nav.currentItemChanged.connect(self._on_nav_changed)

        self._stack = QStackedWidget()
        self._stack.setMinimumSize(0, 0)
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._locked = QLabel("Anmeldung erforderlich. Menü Sitzung -> Anmelden öffnen...")
        self._locked.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._locked)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._nav)
        splitter.addWidget(self._stack)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self._apply_stylesheet()
        self._build_menus()

        self._session_label = QLabel("")
        self.statusBar().addPermanentWidget(self._session_label)

        # Enforce explicit login every start.
        self._force_logged_out()
        self._refresh_shell_for_session()
        # ``main`` shows the shell only after construction. Opening a modal
        # child dialog here would block ``window.show()`` and can leave both
        # parent and login dialog invisible on Windows. Defer it to the first
        # event-loop tick, after the shell has been shown.
        QTimer.singleShot(0, lambda: self._prompt_login(required=True))

    def _apply_stylesheet(self) -> None:
        path = Path(__file__).with_name("styles.qss")
        if path.is_file():
            self.setStyleSheet(path.read_text(encoding="utf-8"))

    def _build_menus(self) -> None:
        session_menu = self.menuBar().addMenu("&Sitzung")
        self._act_sign_in = QAction("Anmelden...", self)
        self._act_sign_in.triggered.connect(lambda: self._prompt_login(required=False))
        session_menu.addAction(self._act_sign_in)
        self._act_sign_out = QAction("Abmelden", self)
        self._act_sign_out.triggered.connect(self._on_sign_out)
        session_menu.addAction(self._act_sign_out)
        view_menu = self.menuBar().addMenu("&Ansicht")
        self._act_admin_debug = QAction("Admin/Debug anzeigen", self)
        self._act_admin_debug.setCheckable(True)
        self._act_admin_debug.setChecked(self._debug_toggle_enabled)
        self._act_admin_debug.setEnabled(False)
        self._act_admin_debug.toggled.connect(self._on_toggle_admin_debug)
        view_menu.addAction(self._act_admin_debug)

    def _um(self):
        return self._host.require_container().get_port("usermanagement_service")

    def _force_logged_out(self) -> None:
        self._session.force_logged_out()

    def _current_user(self):
        return self._session.current_user()

    def _is_visible_for_user(self, contribution: QtModuleContribution, user) -> bool:
        return self._visibility_policy.is_visible_for_user(contribution, user)

    def _license_availability(self) -> dict[str, tuple[bool, str]]:
        """
        Returns contribution availability for license-gated modules.
        GUI decoration only; runtime enforcement is in lifecycle + LicensedPortProxy.
        """
        from qm_platform.runtime import bootstrap as runtime_bootstrap

        container = self._host.require_container()
        result: dict[str, tuple[bool, str]] = {}
        if not container.has_port("license_service"):
            return result
        license_service = container.get_port("license_service")
        licensed_by_module = {module_id: tag for module_id, tag in runtime_bootstrap.core_licensed_modules()}
        for contribution in self._all_contributions.values():
            tag = licensed_by_module.get(contribution.module_id)
            if not tag:
                continue
            reason = license_service.block_reason_for_module(tag)
            if reason:
                result[contribution.contribution_id] = (False, reason)
        return result

    def _refresh_shell_for_session(self) -> None:
        user = self._current_user()
        session_fingerprint = self._session_fingerprint_for_user(user)
        if session_fingerprint != self._session_fingerprint:
            self._reset_contribution_widgets()
            self._session_fingerprint = session_fingerprint
        self._nav.blockSignals(True)
        self._nav.clear()
        self._visible_ids = []

        if user is None:
            self._stack.setCurrentWidget(self._locked)
            self._session_label.setText("Nicht angemeldet")
            self._act_sign_in.setEnabled(True)
            self._act_sign_out.setEnabled(False)
            self._act_admin_debug.setEnabled(False)
            self._nav.setEnabled(False)
            self._nav.blockSignals(False)
            return

        normalized_role = normalize_role(getattr(user, "role", None))
        self._act_admin_debug.setEnabled(normalized_role == "ADMIN")
        availability = self._license_availability()
        ordered = sorted(self._all_contributions.values(), key=lambda c: (c.sort_order, c.title))
        for c in ordered:
            if not self._is_visible_for_user(c, user):
                continue
            if c.contribution_id == "platform.admin_debug" and not self._debug_toggle_enabled:
                continue
            item_title = c.title
            if c.contribution_id in availability:
                item_title = f"{c.title} (deaktiviert)"
            item = QListWidgetItem(item_title)
            item.setData(_CONTRIBUTION_ROLE, c.contribution_id)
            if c.contribution_id in availability:
                enabled, reason = availability[c.contribution_id]
                item.setToolTip(reason)
                if not enabled:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._nav.addItem(item)
            self._visible_ids.append(c.contribution_id)
        self._nav.blockSignals(False)

        self._session_label.setText(f"Angemeldet als {user.username} ({user.role})")
        self._act_sign_in.setEnabled(False)
        self._act_sign_out.setEnabled(True)
        self._nav.setEnabled(True)
        if self._nav.count():
            self._nav.setCurrentRow(0)
        else:
            self._stack.setCurrentWidget(self._locked)

    @staticmethod
    def _session_fingerprint_for_user(user) -> tuple[str, str] | None:
        if user is None:
            return None
        return (str(getattr(user, "user_id", "")), normalize_role(getattr(user, "role", None)))

    def _reset_contribution_widgets(self) -> None:
        for widget in list(self._lazy_widgets.values()):
            self._stack.removeWidget(widget)
            widget.deleteLater()
        self._lazy_widgets.clear()
        self._stack.setCurrentWidget(self._locked)

    def _on_toggle_admin_debug(self, enabled: bool) -> None:
        user = self._current_user()
        if user is None or normalize_role(getattr(user, "role", None)) != "ADMIN":
            self._act_admin_debug.setChecked(self._debug_toggle_enabled)
            return
        self._debug_toggle_enabled = enabled
        self._preferences.save_admin_debug_toggle(self._debug_toggle_enabled)
        self._refresh_shell_for_session()

    def _prompt_login(self, *, required: bool) -> None:
        while True:
            dlg = _LoginDialog(
                self._um(),
                self,
                allow_local_register=not self._session.uses_backend_session,
            )
            result = dlg.exec()
            if result != QDialog.DialogCode.Accepted:
                if required:
                    self.close()
                return
            username, password = dlg.credentials()
            if not username:
                QMessageBox.information(self, "Anmeldung", "Bitte Benutzernamen eingeben.")
                continue
            try:
                user = self._session.login(username, password)
                if user is None:
                    raise RuntimeError("Ungültige Zugangsdaten.")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Anmeldung fehlgeschlagen", user_facing_auth_message(exc))
                continue
            if bool(getattr(user, "must_change_password", False)):
                change_pw = (
                    self._session.change_password if self._session.uses_backend_session else None
                )
                dlg = ForcePasswordChangeDialog(
                    self._um(),
                    user,
                    self,
                    change_password=change_pw,
                    require_current_password=change_pw is None,
                )
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    try:
                        self._session.force_logged_out()
                    except Exception:  # noqa: BLE001
                        self._log.exception("Logout after cancelled password change failed")
                    self._refresh_shell_for_session()
                    continue
                user = self._current_user()
                if user is None:
                    continue
                if bool(getattr(user, "must_change_password", False)):
                    continue
            try:
                self._refresh_shell_for_session()
            except Exception as exc:  # noqa: BLE001
                self._log.exception("Shell refresh after login failed")
                QMessageBox.critical(
                    self,
                    "Anmeldung",
                    "Anmeldung erfolgreich, aber die Oberflaeche konnte nicht geladen werden.\n\n"
                    f"{exc}",
                )
                return
            # Defer modal dialogs until the login dialog has fully closed
            # (avoids native WM_DESTROY crashes on some Windows/Qt setups).
            QTimer.singleShot(250, self._maybe_show_backup_reminder_modal)
            return

    def _widget_for(self, contribution_id: str) -> QWidget:
        if contribution_id in self._lazy_widgets:
            return self._lazy_widgets[contribution_id]
        c = self._all_contributions[contribution_id]
        try:
            w = c.factory(self._host.require_container())
        except Exception as exc:  # noqa: BLE001
            self._log.exception("Contribution factory failed for %s", contribution_id)
            QMessageBox.critical(
                self,
                "Modul konnte nicht geladen werden",
                f"{c.title}:\n{exc}",
            )
            return self._locked
        # Prevent contribution widgets from forcing oversized minimum geometry
        # onto the shell window on small/limited monitor work areas.
        w.setMinimumSize(0, 0)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._lazy_widgets[contribution_id] = w
        self._stack.addWidget(w)
        return w

    def _on_nav_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        cid = current.data(_CONTRIBUTION_ROLE)
        if not isinstance(cid, str):
            return
        w = self._widget_for(cid)
        self._stack.setCurrentWidget(w)

    def navigate_to_contribution(self, contribution_id: str) -> None:
        for idx in range(self._nav.count()):
            item = self._nav.item(idx)
            if item is None:
                continue
            cid = item.data(_CONTRIBUTION_ROLE)
            if cid == contribution_id and bool(item.flags() & Qt.ItemFlag.ItemIsEnabled):
                self._nav.setCurrentRow(idx)
                return

    def _on_sign_out(self) -> None:
        try:
            self._session.force_logged_out()
        except Exception:  # noqa: BLE001
            self._log.exception("Sign-out logout failed")
        self._refresh_shell_for_session()
        self._prompt_login(required=True)

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._stopping:
            self._stopping = True
            try:
                self._session.force_logged_out()
            except Exception:  # noqa: BLE001
                self._log.exception("Logout on close failed")
            self._host.stop()
        super().closeEvent(event)

    def _maybe_show_backup_reminder_modal(self) -> None:
        try:
            if self._backup_reminder_shown_for_session:
                return
            user = self._current_user()
            if user is None or normalize_role(getattr(user, "role", None)) != "ADMIN":
                return
            container = self._host.require_container()
            if not container.has_port("backup_reminder_service"):
                return
            status = container.get_port("backup_reminder_service").status()
            if not status.is_overdue:
                return
            self._backup_reminder_shown_for_session = True
            days_text = (
                str(status.days_since_last_backup)
                if status.days_since_last_backup is not None
                else "noch kein"
            )
            # Parent-less box: avoids destroying a child dialog while the shell
            # is still settling after login (native crash on some Windows builds).
            answer = QMessageBox.warning(
                None,
                "Logs-Backup Erinnerung",
                f"Logs-Backup ueberfaellig (letztes Backup: {days_text} Tage).\n"
                "Bitte jetzt ein Backup erstellen.\n\n"
                "OK = Audit & Logs oeffnen, Abbrechen = spaeter.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Ok:
                QTimer.singleShot(0, lambda: self.navigate_to_contribution("platform.audit_logs"))
        except Exception:  # noqa: BLE001
            self._log.exception("Backup reminder modal failed")
