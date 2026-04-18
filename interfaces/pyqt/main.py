from __future__ import annotations

import os
import sys

from interfaces.pyqt.runtime.host import RuntimeHost
from interfaces.pyqt.shell.main_window import MainWindow


def main() -> int:
    os.environ.setdefault("QMTOOL_LICENSE_MODE", "production")
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog
    except ImportError as exc:  # pragma: no cover - runtime guard
        print(
            "PyQt6 is not installed. Install with:\n"
            "  pip install -r requirements.txt -r requirements-pyqt.txt",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    app = QApplication(sys.argv)
    app.setApplicationName("QM-Tool")
    app.setOrganizationName("QM-Tool")

    host = RuntimeHost()
    progress = QProgressDialog("Initialisiere Runtime...", None, 0, 0)
    progress.setWindowTitle("QM-Tool startet")
    progress.setMinimumDuration(0)
    progress.setCancelButton(None)
    progress.show()
    app.processEvents()
    try:
        host.start()
    except Exception as exc:  # noqa: BLE001
        progress.close()
        QMessageBox.critical(
            None,
            "Start fehlgeschlagen",
            "Die Anwendung konnte nicht gestartet werden.\n\n"
            "Mögliche Ursache: fehlende oder ungültige Modul-Lizenz.\n\n"
            f"Technische Details:\n{exc}",
        )
        return 1
    progress.close()

    window = MainWindow(host)
    window.show()

    code = app.exec()
    host.stop()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
