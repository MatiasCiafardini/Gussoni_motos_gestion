# app/ui/pages/configuracion_page.py
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QMainWindow, QMessageBox, QSizePolicy, QSpacerItem
)

from app.ui.widgets.config_card import ConfigCard


class ConfiguracionPage(QWidget):
    """
    Dashboard de configuración con tarjetas clicables.
    """
    open_page_requested = Signal(QWidget)  # para que MainWindow pueda empujar páginas hijas

    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None):
        super().__init__(parent)
        self.setObjectName("ConfiguracionPage")
        self.main_window = main_window

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)

        title = QLabel("Configuración"); title.setObjectName("CfgH1")
        subtitle = QLabel("Gestioná usuarios y opciones generales del sistema.")
        subtitle.setObjectName("CfgMuted")

        root.addWidget(title)
        root.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        # ---- Card: Gestión de usuarios ----
        card_users = ConfigCard(
            "Usuarios",
            "Altas, bajas, roles y estados.",
            icon=QIcon.fromTheme("user-group")  # si no hay theme, igual se ve bien sin icono
        )
        card_users.setObjectName("CardUsuarios")
        card_users.clicked.connect(self._open_usuarios)
        grid.addWidget(card_users, 0, 0)

        # ---- Card: Configuración general ----
        card_general = ConfigCard(
            "Configuración general",
            "Preferencias de la app, numeración, etc.",
            icon=QIcon.fromTheme("settings")
        )
        card_general.setObjectName("CardGeneral")
        card_general.clicked.connect(self._open_config_general)
        grid.addWidget(card_general, 0, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        root.addLayout(grid)
        # un pequeño spacer al final para respirar
        root.addItem(QSpacerItem(0, 6, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # QSS específico de esta página (no afecta al resto)
        self.setStyleSheet("""
        QLabel#CfgH1 { font-size: 20px; font-weight: 800; color: #0F172A; }
        QLabel#CfgMuted { color: #6B7280; margin-bottom: 6px; }
        """)

    # ---------------- Navegación ----------------

    def _open_usuarios(self):
        try:
            from app.ui.pages.usuarios_page import UsuariosPage
            page = UsuariosPage(parent=self, main_window=self.main_window)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No pude abrir Usuarios.\n\n{e}")
            return

        if self._try_navigate_in_main(page, object_name="UsuariosPage"):
            return
        self.open_page_requested.emit(page)

    def _open_config_general(self):
        QMessageBox.information(self, "En construcción", "Esta sección estará disponible pronto.")

    def _try_navigate_in_main(self, page: QWidget, object_name: str) -> bool:
        if not self.main_window:
            return False
        page.setObjectName(object_name)
        if hasattr(self.main_window, "navigate_to") and callable(self.main_window.navigate_to):
            try:
                self.main_window.navigate_to(page); return True
            except Exception:
                pass
        if hasattr(self.main_window, "push_page") and callable(self.main_window.push_page):
            try:
                self.main_window.push_page(page); return True
            except Exception:
                pass
        if hasattr(self.main_window, "show_page") and callable(self.main_window.show_page):
            try:
                self.main_window.show_page(page); return True
            except Exception:
                pass
        return False
