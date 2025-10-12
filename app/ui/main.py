from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from app.core.logging_setup import setup_logging
from app.core.config import settings
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme   # <-- importa tu theme

def main():
    setup_logging(settings.APP_NAME)
    app = QApplication(sys.argv)

    apply_theme(app, base_font_pt=11)  # <-- aplica tu estilo

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
