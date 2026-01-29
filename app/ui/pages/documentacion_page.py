from __future__ import annotations
from typing import Optional, Dict
from datetime import date
import os
import tempfile

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt
from reportlab.platypus import KeepInFrame

from app.services.clientes_service import ClientesService
from app.services.vehiculos_service import VehiculosService
from app.ui.widgets.cliente_selector_combo import ClienteSelectorCombo
from app.ui.widgets.vehiculo_selector_combo import VehiculoSelectorCombo
import app.ui.app_message as popUp
from reportlab.lib.enums import TA_JUSTIFY
# PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.units import mm
from reportlab.lib import colors
import app.ui.utils.paths as paths
from app.ui.documentacion.nota_no_rodamiento import generar_nota_no_rodamiento_pdf

class DocumentacionPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._svc_clientes = ClientesService()
        self._svc_vehiculos = VehiculosService()

        self._selected_cliente: Optional[Dict] = None
        self._selected_vehiculo: Optional[Dict] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        title = QLabel("Documentación")
        title.setStyleSheet("font-size: 1.4em; font-weight: 600;")
        root.addWidget(title)

        subtitle = QLabel("Nota de no rodamiento")
        subtitle.setStyleSheet("font-weight: 600;")
        root.addWidget(subtitle)

        root.addSpacing(8)

        lbl_cliente = QLabel("Cliente")
        self.cb_cliente = ClienteSelectorCombo(self._svc_clientes, self)
        self.cb_cliente.setMaximumWidth(420)

        root.addWidget(lbl_cliente)
        root.addWidget(self.cb_cliente)

        root.addSpacing(8)

        lbl_vehiculo = QLabel("Vehículo")
        self.cb_vehiculo = VehiculoSelectorCombo(self._svc_vehiculos, self)
        self.cb_vehiculo.setMaximumWidth(420)

        root.addWidget(lbl_vehiculo)
        root.addWidget(self.cb_vehiculo)

        root.addSpacing(16)

        self.btn_generar = QPushButton("Generar nota de no rodamiento")
        self.btn_generar.setObjectName("BtnPrimary")
        self.btn_generar.setEnabled(False)
        self.btn_generar.setMinimumWidth(260)

        root.addWidget(self.btn_generar, alignment=Qt.AlignLeft)
        root.addStretch(1)

        # señales
        self.cb_cliente.cliente_selected.connect(self._on_cliente_selected)
        self.cb_cliente.cliente_cleared.connect(self._on_cliente_cleared)
        self.cb_vehiculo.vehiculo_selected.connect(self._on_vehiculo_selected)
        self.cb_vehiculo.vehiculo_cleared.connect(self._on_vehiculo_cleared)
        self.btn_generar.clicked.connect(self._generar_pdf)

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def _update_button_state(self) -> None:
        self.btn_generar.setEnabled(
            self._selected_cliente is not None
            and self._selected_vehiculo is not None
        )

    def _on_cliente_selected(self, data: Dict) -> None:
        self._selected_cliente = data
        self._update_button_state()

    def _on_cliente_cleared(self) -> None:
        self._selected_cliente = None
        self._update_button_state()

    def _on_vehiculo_selected(self, data: Dict) -> None:
        self._selected_vehiculo = data
        self._update_button_state()

    def _on_vehiculo_cleared(self) -> None:
        self._selected_vehiculo = None
        self._update_button_state()

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------
    def _generar_pdf(self) -> None:
        try:
            path = generar_nota_no_rodamiento_pdf(
                self._selected_cliente,
                self._selected_vehiculo
            )
        except Exception as ex:
            popUp.toast(self, f"Error al generar PDF: {ex}", kind="error")
            return

        popUp.toast(self, "Nota de no rodamiento generada.", kind="success")
        try:
            os.startfile(path)
        except Exception:
            pass