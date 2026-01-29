from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy, QLabel
from PySide6.QtCore import Qt

class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(260)

        title = QLabel("Agencia Motos")
        title.setObjectName("SideTitle")
        title.setAlignment(Qt.AlignHCenter)

        self.btnInicio   = self._mk_btn("Inicio")
        self.btnClientes = self._mk_btn("Clientes")
        self.btnVehiculos= self._mk_btn("Vehículos")
        self.btnFact     = self._mk_btn("Facturación")
        self.btnProv     = self._mk_btn("Proveedores")
        self.btnDoc     = self._mk_btn("Documentacion")
        self.btnReportes = self._mk_btn("Reportes")
        self.btnConfig   = self._mk_btn("Configuración")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        lay.addWidget(title)
        for b in (self.btnInicio, self.btnClientes, self.btnVehiculos, self.btnFact,self.btnDoc, self.btnProv, self.btnReportes, self.btnConfig):
            lay.addWidget(b)
        lay.addStretch(1)

        self.btnInicio.setChecked(True)

    def _mk_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("SideButton")
        b.setCheckable(True)
        b.setAutoExclusive(True)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b.setMinimumHeight(44)
        b.setCursor(Qt.PointingHandCursor)
        return b
