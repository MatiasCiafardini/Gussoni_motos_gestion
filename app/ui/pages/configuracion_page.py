from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QMainWindow, 
    QSizePolicy, QSpacerItem, QPushButton, QHBoxLayout
)
import app.ui.app_message as popUp
# --- Card minimalista, centrada, clickeable ---
class OptionCard(QPushButton):
    """
    Card minimalista con icono grande centrado y título debajo.
    Usa objectName 'CfgOption' para QSS.
    """
    clicked_card = Signal()  # alias semántico si lo querés usar

    def __init__(self, title: str, icon: Optional[QIcon] = None, emoji: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("CfgOption")
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(False)
        self.setFlat(True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setMinimumSize(210, 130)
        self.setMaximumSize(230, 150)

        # contenido
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 16, 16, 16)
        box.setSpacing(10)
        box.setAlignment(Qt.AlignCenter)

        # Icono
        self.icon_label = QLabel(self)
        self.icon_label.setObjectName("CfgOptionIcon")
        self.icon_label.setAlignment(Qt.AlignCenter)

        if icon and not icon.isNull():
            pm = icon.pixmap(QSize(56, 56))
            if not pm.isNull():
                self.icon_label.setPixmap(pm)
        elif emoji:
            self.icon_label.setText(emoji)
        else:
            self.icon_label.setText("⚙️")

        # Título
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("CfgOptionTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)

        box.addStretch(1)
        box.addWidget(self.icon_label)
        box.addWidget(self.title_label)
        box.addStretch(1)

        # reenviar clicked
        self.clicked.connect(self.clicked_card.emit)


class ConfiguracionPage(QWidget):
    open_page_requested = Signal(QWidget)

    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None):
        super().__init__(parent)
        self.setObjectName("ConfiguracionPage")
        self.main_window = main_window

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(14)

        title = QLabel("Configuración y Administración"); title.setObjectName("CfgH1")
        subtitle = QLabel("Gestioná usuarios y las opciones generales del sistema (incluyendo ARCA / AFIP).")
        subtitle.setObjectName("CfgMuted")

        root.addWidget(title)
        root.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        # Card: Usuarios
        card_users = OptionCard(
            "Gestión de Usuarios",
            icon=QIcon.fromTheme("user-group"),
            emoji="👤"
        )
        card_users.clicked_card.connect(self._open_usuarios)
        grid.addWidget(card_users, 0, 0)

        # Card: Configuración general (placeholder para futuro)
        card_general = OptionCard(
            "Configuración General",
            icon=QIcon.fromTheme("settings"),
            emoji="⚙️"
        )
        card_general.clicked_card.connect(self._open_config_general)
        grid.addWidget(card_general, 0, 1)

        # NUEVA Card: Configuración ARCA / AFIP
        card_arca = OptionCard(
            "Configuración ARCA / AFIP",
            icon=QIcon.fromTheme("network-server"),
            emoji="🧾"
        )
        card_arca.clicked_card.connect(self._open_config_arca)
        grid.addWidget(card_arca, 1, 0)

                # NUEVA Card: Importación de Datos
        card_importacion = OptionCard(
            "Importación de Datos",
            icon=QIcon.fromTheme("document-import"),
            emoji="📥"
        )
        card_importacion.clicked_card.connect(self._open_importacion_datos)
        grid.addWidget(card_importacion, 1, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # Contenedor horizontal para alinear el grid a la izquierda
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addLayout(grid)
        hbox.addStretch(1)  # empuja las cards hacia la izquierda
        
        root.addLayout(hbox)
        
        root.addItem(QSpacerItem(0, 6, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # QSS corto para títulos de la página
        self.setStyleSheet("""
        QLabel#CfgH1 { font-size: 22px; font-weight: 800; color: #0F172A; margin-bottom: 2px; }
        QLabel#CfgMuted { color: #6B7280; margin-bottom: 8px; }
        """)

    # --------- Navegación ----------
    def _open_usuarios(self):
        try:
            from app.ui.pages.usuarios_page import UsuariosPage
            page = UsuariosPage(parent=self, main_window=self.main_window)
        except Exception as e:
            popUp.critical(self, "Error", f"No pude abrir Usuarios.\n\n{e}")
            return
        if self._try_navigate_in_main(page, object_name="UsuariosPage"):
            return
        self.open_page_requested.emit(page)

    def _open_config_general(self):
        popUp.info(self, "En construcción", "Esta sección estará disponible pronto.")

    def _open_config_arca(self):
        """
        Abre la pantalla de Configuración ARCA / AFIP, donde podés
        probar el próximo número a autorizar por tipo y punto de venta.
        """
        try:
            from app.ui.pages.configuracion_arca_page import ConfiguracionArcaPage
            page = ConfiguracionArcaPage(parent=self, main_window=self.main_window)
        except Exception as e:
            popUp.critical(self, f"No pude abrir la Configuración de ARCA.\n\n{e}")
            return

        if self._try_navigate_in_main(page, object_name="ConfiguracionArcaPage"):
            return
        self.open_page_requested.emit(page)
        
    def _open_importacion_datos(self):
        try:
            from app.ui.pages.importacion_datos_page import ImportacionDatosPage
            page = ImportacionDatosPage(parent=self, main_window=self.main_window)
        except Exception as e:
            popUp.critical(self, f"No pude abrir Importación de Datos.\n\n{e}")
            return

        if self._try_navigate_in_main(page, object_name="ImportacionDatosPage"):
            return
        self.open_page_requested.emit(page)

    def _try_navigate_in_main(self, page: QWidget, object_name: str) -> bool:
        if not self.main_window:
            return False
        page.setObjectName(object_name)
        for m in ("navigate_to", "push_page", "show_page", "open_page_widget"):
            if hasattr(self.main_window, m) and callable(getattr(self.main_window, m)):
                try:
                    getattr(self.main_window, m)(page)
                    return True
                except Exception:
                    pass
        return False
