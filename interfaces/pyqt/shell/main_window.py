from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
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
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.registry.catalog import all_contributions
from interfaces.pyqt.registry.contribution import QtModuleContribution
from interfaces.pyqt.runtime.host import RuntimeHost
from interfaces.pyqt.shell.preferences import ShellPreferences
from interfaces.pyqt.shell.session_coordinator import SessionCoordinator
from interfaces.pyqt.shell.visibility_policy import ContributionVisibilityPolicy, normalize_role

_CONTRIBUTION_ROLE = Qt.ItemDataRole.UserRole + 1


class _LoginDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Anmelden")
        self._user = QLineEdit()
        self._pw = QLineEdit()
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
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


class MainWindow(QMainWindow):
    """
    Host shell with strict login-gate.

    - No module navigation before explicit login.
    - Contributions are filtered by role metadata.
    - Session is explicitly logged out on close.
    """

    def __init__(self, host: RuntimeHost) -> None:
        super().__init__()
        self._host = host
        ordered = all_contributions()
        self._all_contributions: dict[str, QtModuleContribution] = {c.contribution_id: c for c in ordered}
        self._visible_ids: list[str] = []
        self._lazy_widgets: dict[str, QWidget] = {}
        self._session_fingerprint: tuple[str, str] | None = None
        self._stopping = False
        self._preferences = ShellPreferences()
        self._debug_toggle_enabled = self._preferences.load_admin_debug_toggle()
        self._visibility_policy = ContributionVisibilityPolicy()
        self._session = SessionCoordinator(self._um())

        self.setWindowTitle("QmTool")
        self.resize(1240, 760)

        self._nav = QListWidget()
        self._nav.setMinimumWidth(232)
        self._nav.setSpacing(2)
        self._nav.currentItemChanged.connect(self._on_nav_changed)

        self._stack = QStackedWidget()
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
        self._prompt_login(required=True)

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
        Returns contribution availability based on license and dependency hints.
        This is GUI-only decoration and does not alter runtime behavior.
        """
        container = self._host.require_container()
        result: dict[str, tuple[bool, str]] = {}
        if not container.has_port("license_service"):
            return result
        license_service = container.get_port("license_service")
        try:
            signature_ok = bool(license_service.is_module_allowed("signature"))
        except Exception as exc:  # noqa: BLE001
            signature_ok = False
            result["signature.workspace"] = (False, f"Lizenzprüfung fehlgeschlagen: {exc}")
        else:
            if not signature_ok:
                result["signature.workspace"] = (False, "Signatur-Lizenz fehlt")
        try:
            documents_ok = bool(license_service.is_module_allowed("documents"))
        except Exception as exc:  # noqa: BLE001
            documents_ok = False
            result["documents.workflow"] = (False, f"Dokumenten-Lizenzprüfung fehlgeschlagen: {exc}")
            result["documents.pool"] = (False, f"Dokumenten-Lizenzprüfung fehlgeschlagen: {exc}")
        else:
            if not documents_ok:
                result["documents.workflow"] = (False, "Dokumenten-Lizenz fehlt")
                result["documents.pool"] = (False, "Dokumenten-Lizenz fehlt")
        if not signature_ok:
            # Documents module depends on signature_api; expose dependency state in GUI.
            if "documents.workflow" not in result:
                result["documents.workflow"] = (False, "Abhängig blockiert: Signatur-Lizenz fehlt")
            if "documents.pool" not in result:
                result["documents.pool"] = (False, "Abhängig blockiert: Signatur-Lizenz fehlt")
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
            dlg = _LoginDialog(self)
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
                    raise RuntimeError("Ungültige Zugangsdaten")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Anmeldung fehlgeschlagen", str(exc))
                continue
            self._refresh_shell_for_session()
            return

    def _widget_for(self, contribution_id: str) -> QWidget:
        if contribution_id in self._lazy_widgets:
            return self._lazy_widgets[contribution_id]
        c = self._all_contributions[contribution_id]
        w = c.factory(self._host.require_container())
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
            self._um().logout()
        except Exception:
            pass
        self._refresh_shell_for_session()
        self._prompt_login(required=True)

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._stopping:
            self._stopping = True
            try:
                self._um().logout()
            except Exception:
                pass
            self._host.stop()
        super().closeEvent(event)
