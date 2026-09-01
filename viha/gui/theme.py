from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from viha.data import DATA_DIR

ICON_PATH = DATA_DIR / "viha.ico"

BG = "#0B0D10"
BG_RAISE = "#12151B"
BG_SUNKEN = "#08090C"
AMBER = "#E8A317"
RUST = "#C23B22"
GREEN = "#3DDC97"
BONE = "#E7E2D6"
MUTED = "#8A8476"
LINE = "#2A2E36"

QSS = f"""
QWidget {{
    background: {BG};
    color: {BONE};
    font-family: "Segoe UI", "IBM Plex Sans", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {BG};
}}
QFrame#Rail, QFrame#Detail, QFrame#Header {{
    background: {BG_RAISE};
    border: 1px solid {LINE};
}}
QLabel#Brand {{
    color: {AMBER};
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 3px;
}}
QLabel#SubBrand {{
    color: {MUTED};
    font-size: 11px;
    letter-spacing: 1px;
}}
QLabel#Section {{
    color: {AMBER};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#PersonaName {{
    font-size: 22px;
    font-weight: 600;
    color: {BONE};
}}
QLabel#Muted {{
    color: {MUTED};
}}
QLabel#PersonaBrief {{
    color: {BONE};
    font-size: 14px;
    background: transparent;
    min-height: 36px;
    padding: 4px 0 0 0;
}}
QLabel#PersonaKey {{
    color: {MUTED};
    font-size: 10px;
    letter-spacing: 1px;
    font-weight: 700;
    background: transparent;
}}
QLabel#PersonaIndex {{
    color: {BONE};
    font-size: 12px;
    background: transparent;
}}
QLabel#PersonaIndex a {{
    color: {AMBER};
}}
QFrame#PersonaSheet {{
    background: {BG_SUNKEN};
    border: 1px solid {LINE};
    border-radius: 4px;
}}
QFrame#PersonaSheet QLabel {{
    background: transparent;
}}
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {BG_SUNKEN};
    border: 1px solid {LINE};
    border-radius: 4px;
    padding: 6px 8px;
    color: {BONE};
    selection-background-color: {AMBER};
    selection-color: {BG};
}}
QLineEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {AMBER};
}}
QCheckBox {{
    spacing: 8px;
    color: {BONE};
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {LINE};
    background: {BG_SUNKEN};
}}
QCheckBox::indicator:checked {{
    background: {AMBER};
    border: 1px solid {AMBER};
}}
QPushButton {{
    background: transparent;
    border: 1px solid {LINE};
    border-radius: 4px;
    padding: 8px 14px;
    color: {BONE};
}}
QPushButton:hover {{
    border-color: {AMBER};
    color: {AMBER};
}}
QPushButton#Reap {{
    background: {AMBER};
    color: {BG};
    font-weight: 700;
    letter-spacing: 2px;
    border: none;
    padding: 10px 16px;
}}
QPushButton#Reap:hover {{
    background: #ffbb33;
    color: {BG};
}}
QPushButton#Reap:disabled {{
    background: #5a4a24;
    color: #2a2414;
}}
QTabWidget::pane {{
    border: 1px solid {LINE};
    background: {BG};
}}
QTabBar::tab {{
    background: {BG_RAISE};
    color: {MUTED};
    padding: 8px 16px;
    border: 1px solid {LINE};
    border-bottom: none;
    margin-right: 4px;
}}
QTabBar::tab:selected {{
    color: {AMBER};
    background: {BG};
}}
QTableWidget {{
    background: {BG};
    alternate-background-color: {BG_RAISE};
    gridline-color: {LINE};
    border: none;
}}
QHeaderView::section {{
    background: {BG_RAISE};
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {LINE};
    padding: 6px;
    font-size: 11px;
    letter-spacing: 1px;
}}
QScrollBar:vertical {{
    background: {BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {LINE};
    min-height: 24px;
    border-radius: 4px;
}}
QStatusBar {{
    background: {BG_RAISE};
    color: {MUTED};
    border-top: 1px solid {LINE};
}}
QGraphicsView {{
    background: {BG_SUNKEN};
    border: 1px solid {LINE};
}}
"""


def app_icon() -> QIcon:
    if ICON_PATH.exists():
        return QIcon(str(ICON_PATH))
    return QIcon()


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(BONE))
    pal.setColor(QPalette.ColorRole.Base, QColor(BG_SUNKEN))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_RAISE))
    pal.setColor(QPalette.ColorRole.Text, QColor(BONE))
    pal.setColor(QPalette.ColorRole.Button, QColor(BG_RAISE))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(BONE))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(AMBER))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(BG))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    app.setPalette(pal)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setStyleSheet(QSS)
