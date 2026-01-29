from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap
from app.core.updater import check_for_update

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

    def __init__(self, title: str, icon: Optional[QIcon] = None, emoji: Optional[str] = None,icon_size: QSize | None = None, parent=None):
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
        size = icon_size or QSize(72, 72)
        if icon and not icon.isNull():
            pm = icon.pixmap(size)
            pm = pm.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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
        icon_sizes = QSize(72, 72)
        # Card: Usuarios
        card_users = OptionCard(
            "Gestión de Usuarios",
            icon=QIcon.fromTheme("user-group"),
            emoji="👤",
            icon_size= icon_sizes
        )
        card_users.clicked_card.connect(self._open_usuarios)
        

        # Card: Configuración general (placeholder para futuro)
        card_general = OptionCard(
            "Configuración General",
            icon=QIcon.fromTheme("settings"),
            emoji="⚙️",
            icon_size= icon_sizes
        )
        card_general.clicked_card.connect(self._open_config_general)
        

        # NUEVA Card: Configuración ARCA / AFIP
        card_arca = OptionCard(
            "Configuración ARCA / AFIP",
            icon=QIcon.fromTheme("network-server"),
            emoji="🧾",
            icon_size= icon_sizes
        )
        card_arca.clicked_card.connect(self._open_config_arca)
        

                # NUEVA Card: Importación de Datos
        card_importacion = OptionCard(
            "Importación de Datos",
            icon=QIcon.fromTheme("document-import"),
            emoji="📥",
            icon_size= icon_sizes

        )
        card_importacion.clicked_card.connect(self._open_importacion_datos)
        

        # NUEVA Card: Buscar actualizaciones
        card_updates = OptionCard(
            "Buscar actualizaciones",
            icon=QIcon.fromTheme("software-update-available"),
            emoji="🚀",
            icon_size= icon_sizes
        )
        card_updates.clicked_card.connect(self._check_updates)

        grid.addWidget(card_users, 0, 0)
        grid.addWidget(card_general, 0, 1)
        grid.addWidget(card_updates, 0, 2)
        grid.addWidget(card_arca, 1, 0)
        grid.addWidget(card_importacion, 1, 1)
        
        for col in range(4):
            grid.setColumnStretch(col, 1)


        # Contenedor horizontal para alinear el grid a la izquierda
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addLayout(grid)
        hbox.addStretch(1)  # empuja las cards hacia la izquierda
        
        root.addLayout(hbox)
        
        root.addItem(QSpacerItem(0, 6, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # QSS corto para títulos de la página
        self.setStyleSheet("""
        QLabel#CfgH1 { font-size: 1.9em; font-weight: 800; color: #0F172A; margin-bottom: 2px; }
        QLabel#CfgMuted { color: #6B7280; margin-bottom: 8px; }
        """)

    # --------- Navegación ----------
    def _open_usuarios(self):
        try:
            from app.ui.pages.usuarios_page import UsuariosPage
            page = UsuariosPage(parent=self, main_window=self.main_window)
        except Exception as e:
            popUp.toast(self, "Error", f"No pude abrir Usuarios.\n\n{e}")
            return
        if self._try_navigate_in_main(page, object_name="UsuariosPage"):
            return
        self.open_page_requested.emit(page)

    def _open_config_general(self):
        try:
            from app.ui.pages.configuracion_general_page import ConfiguracionGeneralPage
            page = ConfiguracionGeneralPage(parent=self, main_window=self.main_window)
        except Exception as e:
            popUp.toast(self, "Error", f"No pude abrir Configuración General.\n\n{e}")
            return

        if self._try_navigate_in_main(page, object_name="ConfiguracionGeneralPage"):
            return
        self.open_page_requested.emit(page)


    def _open_config_arca(self):
        """
        Abre la pantalla de Configuración ARCA / AFIP, donde podés
        probar el próximo número a autorizar por tipo y punto de venta.
        """
        try:
            from app.ui.pages.configuracion_arca_page import ConfiguracionArcaPage
            page = ConfiguracionArcaPage(parent=self, main_window=self.main_window)
        except Exception as e:
            popUp.toast(self, f"No pude abrir la Configuración de ARCA.\n\n{e}")
            return

        if self._try_navigate_in_main(page, object_name="ConfiguracionArcaPage"):
            return
        self.open_page_requested.emit(page)
        
    def _open_importacion_datos(self):
        try:
            from app.ui.pages.importacion_datos_page import ImportacionDatosPage
            page = ImportacionDatosPage(parent=self, main_window=self.main_window)
        except Exception as e:
            popUp.toast(self, f"No pude abrir Importación de Datos.\n\n{e}")
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
    
    def _check_updates(self):
        """
        Dispara la búsqueda de actualizaciones desde la ventana principal.
        """
        if not self.main_window:
            popUp.warning(
                self,
                "Actualizaciones",
                "No se pudo acceder a la ventana principal."
            )
            return

        if hasattr(self.main_window, "check_updates_ui"):
            self.main_window.check_updates_ui(interactive=True)
        else:
            popUp.warning(
                self,
                "Actualizaciones",
                "La función de actualización no está disponible."
            )

