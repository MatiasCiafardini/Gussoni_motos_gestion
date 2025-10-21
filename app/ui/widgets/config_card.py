from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QSizePolicy, QWidget

class ConfigCard(QFrame):
    """
    Tarjeta de configuración clickable basada en el estilo 'Card' de la aplicación.
    Emite una señal 'clicked' cuando se presiona.
    """
    clicked = Signal()

    def __init__(self, title: str, icon_text: str = "⚙", parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFrameShape(QFrame.StyledPanel)
        
        # Hacemos que la tarjeta se expanda para ser responsiva
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(QCursor(Qt.PointingHandCursor)) # Muestra un cursor de mano

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        # 1. Ícono (Grande y centrado)
        self.lbl_icon = QLabel(icon_text)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        
        # Usamos un estilo grande para el ícono
        icon_font = QFont(); 
        icon_font.setPointSize(40); # Tamaño grande
        icon_font.setWeight(QFont.Weight.Light)
        self.lbl_icon.setFont(icon_font)
        
        # 2. Título (centrado)
        self.lbl_title = QLabel(title)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("font-size:16px; font-weight:500; color:#212529;") # Estilo similar a KpiValue [2]

        lay.addWidget(self.lbl_icon)
        lay.addStretch(1) # Espacio entre ícono y título
        lay.addWidget(self.lbl_title)
        
        # 3. Estilo Visual (basado en DashboardPage)
        # Replicamos el estilo Card [2] pero agregamos un efecto al pasar el mouse
        self.setStyleSheet("""
            QFrame#Card { 
                background:#ffffff; 
                border:1px solid #e9ecef; 
                border-radius:12px; 
            }
            QFrame#Card:hover {
                border: 1px solid #60a5fa; /* Color azul al pasar el mouse */
                background: #f8f9fa;
            }
        """)

    def mousePressEvent(self, event):
        """Sobrescribe el evento de clic del ratón para emitir la señal."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)