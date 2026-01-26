from __future__ import annotations

import sys
import ctypes
from typing import Optional, Dict, Any

from PySide6.QtCore import QSettings, QObject
from PySide6.QtWidgets import QDialog
from PySide6.QtGui import QIcon

from app.core.logging_setup import setup_logging
from app.core.config import settings
from app.ui.theme import apply_theme
from app.shared.paths import ensure_user_dirs
from app.core.db_state import db_config_completa
import app.ui.utils.paths as paths


from typing import Optional, Dict, Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog

from app.core.db_state import db_config_completa


class ApplicationController(QObject):
    """Coordinates the login flow and the main window lifecycle."""

    def __init__(self, app):
        super().__init__()
        self._app = app
        self._main_window = None
        self._current_user: Optional[Dict[str, Any]] = None

    def start(self) -> None:
        if not db_config_completa():
            self._show_config()
        else:
            self._show_login()

    def _show_login(self) -> None:
        from app.ui.login_dialog import LoginDialog  # lazy import

        dialog = LoginDialog()
        result = dialog.exec()

        if result != QDialog.Accepted or not dialog.user:
            self._app.quit()
            return

        self._current_user = dialog.user
        self._show_main_window()

    def _show_config(self) -> None:
        from app.ui.config_dialog import ConfigDialog  # lazy import

        dialog = ConfigDialog()
        result = dialog.exec()

        if result != QDialog.Accepted:
            self._app.quit()
            return

        self._show_login()

    def _show_main_window(self) -> None:
        from app.ui.main_window import MainWindow  # lazy import

        if self._main_window:
            self._main_window.deleteLater()

        self._main_window = MainWindow(
            current_user=self._current_user,
            on_logout=self._handle_logout
        )
        self._main_window.show()

    def _handle_logout(self) -> None:
        if self._main_window:
            self._main_window.deleteLater()
            self._main_window = None

        self._current_user = None
        self._show_login()



def start_app(app):
    """
    Arranca la aplicación principal.
    QApplication DEBE venir creado desde run.py
    """

    ensure_user_dirs()

    setup_logging(settings.APP_NAME)

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "gussoni.app"
    )

    # UI settings
    ui_settings = QSettings("Gussoni", "GussoniApp")
    scale = ui_settings.value("ui/font_scale", 1.0, float)

    apply_theme(app, base_font_pt=11, scale=scale)

    app.setWindowIcon(QIcon(str(paths.APP_ICON)))

    controller = ApplicationController(app)
    controller.start()
