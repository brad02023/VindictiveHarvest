from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from viha.gui.shell import MainWindow
from viha.gui.theme import apply_theme


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Vindictive Harvest")
    app.setOrganizationName("VIHA")
    apply_theme(app)
    win = MainWindow()
    win.show()
    return app.exec()
