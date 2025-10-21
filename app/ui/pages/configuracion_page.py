from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QMainWindow, QMessageBox
)
from app.ui.widgets.config_card import ConfigCard 
#from app.ui.pages.usuarios_page import UsuariosPage

# Usamos loguru para el logging, como se usa en el resto de la aplicación [29]
from loguru import logger 

class ConfiguracionPage(QWidget):
    """
    Página de configuración que actúa como dashboard de módulos administrativos
    usando tarjetas (cards) clicables.
    """
    
    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None):
        super().__init__(parent)
        self.setObjectName("ConfiguracionPage")
        self.main_window = main_window # Referencia a la ventana principal para la navegación

        # 🔧 Estilo general para que los QLabel no tengan el fondo gris (como en DashboardPage [4])
        self.setStyleSheet("QLabel { background: transparent; }")
        
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # 1. Header (Título)
        title = QLabel("Configuración y Administración")
        title.setStyleSheet("font-size:24px; font-weight:700;") # Estilo ligeramente más grande que el de Dashboard [4]
        
        hdr = QHBoxLayout()
        hdr.addWidget(title)
        hdr.addStretch(1) # Empuja el título a la izquierda
        root.addLayout(hdr)

        # 2. Layout de Cards (Responsive)
        self.card_grid = QGridLayout()
        self.card_grid.setHorizontalSpacing(20)
        self.card_grid.setVerticalSpacing(20)
        
        # Añadir layout de cards al root
        root.addLayout(self.card_grid)
        root.addStretch(1) # Asegura que el contenido se pegue arriba

        # 3. Creación y adición de la Card "Usuarios"
        self.card_usuarios = ConfigCard(
            title="Gestión de Usuarios", 
            icon_text="👤" # Usamos un emoji o un carácter Unicode simple como ícono
        )
        
        # Colocamos la tarjeta en la posición (0, 0)
        self.card_grid.addWidget(self.card_usuarios, 0, 0)

        # Configuramos las columnas para que se estiren de manera uniforme, 
        # haciendo el layout responsive
        self.card_grid.setColumnStretch(0, 1) 
        self.card_grid.setColumnStretch(1, 1)
        self.card_grid.setColumnStretch(2, 1)
        
        # 4. Conexión del Evento
        # Al hacer clic en la tarjeta, llamamos al método de navegación
        self.card_usuarios.clicked.connect(self.navigate_to_usuarios)

        # Añadir un placeholder para otro módulo (ej. Configuración general)
        card_general = ConfigCard(
            title="Configuración General", 
            icon_text="⚙️"
        )
        self.card_grid.addWidget(card_general, 0, 1)


    def navigate_to_usuarios(self):
        """
        Maneja la navegación a UsuariosPage usando el método open_page de la MainWindow.
        """
        logger.error("Hola")
        mw = getattr(self, "main_window", None) or self.window()
        if not isinstance(mw, QMainWindow):
            return
        logger.error(mw)
        try:
            if hasattr(mw, "open_page"):
                mw.open_page("usuarios")
        except Exception as e:
            logger.error(f"Fallo al instanciar UsuariosPage: {e}")
            pass