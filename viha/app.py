from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from viha.gui.shell import MainWindow
from viha.gui.theme import apply_theme, app_icon


def _windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VIHA.VindictiveHarvest.1")
    except Exception:
        pass


def run_app() -> int:
    _windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("Vindictive Harvest")
    app.setOrganizationName("VIHA")
    apply_theme(app)
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    win = MainWindow()
    if not icon.isNull():
        win.setWindowIcon(icon)
    win.show()
    return app.exec()
