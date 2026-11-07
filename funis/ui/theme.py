"""Palette and style sheet of the application."""
import os

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

INK = "#243b53"
ACCENT = "#1f6feb"
ACCENT_DARK = "#1858bf"
BG = "#f4f6f9"
PANEL = "#ffffff"
BORDER = "#d9e0e8"
MUTED = "#6b7a8c"

STYLE = """
QMainWindow, QDialog { background: %(bg)s; }
QWidget { font-size: 13px; color: %(ink)s; }
QToolBar { background: %(panel)s; border-bottom: 1px solid %(border)s; padding: 4px 8px; spacing: 6px; }
QToolBar QToolButton { padding: 5px 10px; border-radius: 6px; }
QToolBar QToolButton:hover { background: #e8eef7; }
QToolBar QToolButton:pressed { background: #d7e2f3; }
QStatusBar { background: %(panel)s; border-top: 1px solid %(border)s; color: %(muted)s; }
QMenuBar { background: %(panel)s; border-bottom: 1px solid %(border)s; }
QMenuBar::item:selected { background: #e8eef7; border-radius: 4px; }
QMenu { background: %(panel)s; border: 1px solid %(border)s; padding: 4px; }
QMenu::item { padding: 5px 24px 5px 12px; border-radius: 4px; }
QMenu::item:selected { background: #e8eef7; }
QGroupBox { border: 1px solid %(border)s; border-radius: 8px; margin-top: 14px; padding: 10px 8px 6px;
            background: %(panel)s; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: %(ink)s; }
QTabWidget::pane { border: 1px solid %(border)s; border-radius: 6px; background: %(panel)s; top: -1px; }
QTabBar::tab { padding: 7px 14px; border: 1px solid transparent; border-bottom: none;
               border-top-left-radius: 6px; border-top-right-radius: 6px; color: %(muted)s; }
QTabBar::tab:selected { background: %(panel)s; border-color: %(border)s; color: %(ink)s; font-weight: 600; }
QTabBar::tab:hover:!selected { color: %(ink)s; }
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
    border: 1px solid %(border)s; border-radius: 5px; padding: 3px 6px; background: %(panel)s;
    selection-background-color: %(accent)s; }
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus { border-color: %(accent)s; }
QComboBox { padding-right: 24px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 22px;
    border: none; border-left: 1px solid %(border)s; border-top-right-radius: 5px;
    border-bottom-right-radius: 5px; background: #f3f6fa; }
QComboBox::drop-down:hover { background: #e8eef7; }
QComboBox::down-arrow { image: url("%(arrow)s"); width: 12px; height: 12px; }
QComboBox::down-arrow:disabled { image: url("%(arrow_disabled)s"); }
QComboBox QAbstractItemView { border: 1px solid %(border)s; background: %(panel)s;
    selection-background-color: #e8eef7; selection-color: %(ink)s; }
QToolBar QToolButton[popupMode="2"] { padding-right: 24px; }
QToolButton::menu-indicator { image: url("%(arrow)s"); width: 12px; height: 12px;
    subcontrol-origin: padding; subcontrol-position: center right; right: 6px; }
QPushButton { background: %(panel)s; border: 1px solid %(border)s; border-radius: 6px; padding: 6px 14px; }
QPushButton:hover { background: #eef2f7; }
QPushButton:pressed { background: #dde5ef; }
QPushButton#primary { background: %(accent)s; color: white; border: none; font-weight: 600; }
QPushButton#primary:hover { background: %(accent_dark)s; }
QPushButton#primary:disabled { background: #9db9e8; }
QTableView, QTableWidget { border: 1px solid %(border)s; border-radius: 6px; gridline-color: #eceff3;
    background: %(panel)s; alternate-background-color: #f8fafc; selection-background-color: #dce8fb;
    selection-color: %(ink)s; }
QHeaderView::section { background: #eef2f7; color: %(ink)s; padding: 4px 6px; border: none;
    border-right: 1px solid %(border)s; border-bottom: 1px solid %(border)s; font-weight: 600; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 10px; background: transparent; }
QScrollBar::handle:vertical { background: #c5ced9; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 10px; background: transparent; }
QScrollBar::handle:horizontal { background: #c5ced9; border-radius: 5px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSplitter::handle { background: %(border)s; }
QSplitter::handle:horizontal { width: 2px; }
QToolBox::tab { background: #eef2f7; border: 1px solid %(border)s; border-radius: 6px; padding: 6px;
    font-weight: 600; color: %(ink)s; }
QToolBox::tab:selected { background: #dce8fb; }
QLabel#heading { font-size: 15px; font-weight: 700; color: %(ink)s; }
QLabel#muted { color: %(muted)s; }
QLabel#badge { background: #e8eef7; border-radius: 9px; padding: 2px 8px; color: %(ink)s; }
QLabel#warning { background: #fff4e5; border-left: 3px solid #b57726; padding: 6px 8px; border-radius: 4px; }
QLabel#error { background: #fdecec; border-left: 3px solid #a04460; padding: 6px 8px; border-radius: 4px; }
QCheckBox::indicator, QRadioButton::indicator { width: 15px; height: 15px; }
QFrame#card { background: %(panel)s; border: 1px solid %(border)s; border-radius: 8px; }
QFrame#summary { background: %(panel)s; border: 1px solid %(border)s; border-radius: 8px; }
QToolTip { background: %(ink)s; color: white; border: none; padding: 4px 6px; }
""" % dict(bg=BG, panel=PANEL, border=BORDER, ink=INK, muted=MUTED, accent=ACCENT,
           accent_dark=ACCENT_DARK,
           arrow=os.path.join(ASSETS, "arrow_down.svg").replace("\\", "/"),
           arrow_disabled=os.path.join(ASSETS, "arrow_down_disabled.svg").replace("\\", "/"))


def apply(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.WindowText, QColor(INK))
    pal.setColor(QPalette.Base, QColor(PANEL))
    pal.setColor(QPalette.AlternateBase, QColor("#f8fafc"))
    pal.setColor(QPalette.Text, QColor(INK))
    pal.setColor(QPalette.Button, QColor(PANEL))
    pal.setColor(QPalette.ButtonText, QColor(INK))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor(INK))
    pal.setColor(QPalette.ToolTipText, QColor("#ffffff"))
    pal.setColor(QPalette.PlaceholderText, QColor(MUTED))
    app.setPalette(pal)
    app.setStyleSheet(STYLE)
