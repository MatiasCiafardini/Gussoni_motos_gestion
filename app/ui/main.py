from __future__ import annotations

import sys
import ctypes
from typing import Optional, Dict, Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QDialog
from app.ui.utils.resources import resource_path
from PySide6.QtGui import QIcon
from app.core.logging_setup import setup_logging
from app.core.config import settings
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme   # <-- importa tu theme
from app.ui.login_dialog import LoginDialog
from app.shared.paths import ensure_user_dirs


class ApplicationController(QObject):
    """Coordinates the login flow and the main window lifecycle."""

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._main_window: Optional[MainWindow] = None
        self._current_user: Optional[Dict[str, Any]] = None

    def start(self) -> None:
        self._show_login()

    def _show_login(self) -> None:
        dialog = LoginDialog()
        result = dialog.exec()
        if result != QDialog.Accepted or not dialog.user:
            self._app.quit()
            return

        self._current_user = dialog.user
        self._show_main_window()

    def _show_main_window(self) -> None:
        if self._main_window:
            self._main_window.deleteLater()
        self._main_window = MainWindow(current_user=self._current_user, on_logout=self._handle_logout)
        self._main_window.show()

    def _handle_logout(self) -> None:
        if self._main_window:
            self._main_window.deleteLater()
            self._main_window = None
        self._current_user = None
        self._show_login()


def main():
    ensure_user_dirs()
    setup_logging(settings.APP_NAME)
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "gussoni.app"
    )
    app = QApplication(sys.argv)

    apply_theme(app, base_font_pt=11)  # <-- aplica tu estilo
    icon_path = resource_path("app/assets/logo.ico")
    app.setWindowIcon(QIcon(str(icon_path)))
    controller = ApplicationController(app)
    controller.start()
    sys.exit(app.exec())
