from __future__ import annotations
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView,
    QSizePolicy, QFrame, QMainWindow
)

import app.ui.app_message as popUp
from app.services.remitos_service import RemitosService
from app.services.clientes_service import ClientesService
from app.services.vehiculos_service import VehiculosService
from app.ui.widgets.cliente_selector_combo import ClienteSelectorCombo
from app.ui.widgets.vehiculo_selector_combo import VehiculoSelectorCombo


class RemitosAgregarPage(QWidget):
    go_back = Signal()
    go_to_detalle = Signal(int)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        main_window: Optional[QMainWindow] = None,
    ):
        super().__init__(parent)
        self.setObjectName("RemitosAgregarPage")

        self._svc_remitos = RemitosService()
        self._svc_clientes = ClientesService()
        self._svc_vehiculos = VehiculosService()

        self._selected_cliente: Optional[Dict[str, Any]] = None
        self._dirty = False

        self._build_ui()
        self._add_detalle_row()
        self._actualizar_numero()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("Nuevo remito")
        title.setStyleSheet("font-size: 1.4em; font-weight: 600;")
        root.addWidget(title)

        # -------- CABECERA --------
        panel = QFrame(self)
        panel.setObjectName("Panel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        grid = QGridLayout(panel)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        self.in_pto_vta = QLineEdit("3")
        self.in_numero = QLineEdit()
        self.in_numero.setReadOnly(True)
        self.in_pto_vta.editingFinished.connect(self._actualizar_numero)
        self.in_fecha = QLineEdit(QDate.currentDate().toString("yyyy-MM-dd"))

        self.cb_cliente = ClienteSelectorCombo(self._svc_clientes, self)
        self.cb_cliente.cliente_selected.connect(self._on_cliente)

        self.in_observaciones = QTextEdit()
        self.in_observaciones.setMaximumHeight(80)

        row = 0
        grid.addWidget(QLabel("Pto Vta"), row, 0)
        grid.addWidget(self.in_pto_vta, row, 1)
        grid.addWidget(QLabel("Número"), row, 2)
        grid.addWidget(self.in_numero, row, 3)

        row += 1
        grid.addWidget(QLabel("Fecha"), row, 0)
        grid.addWidget(self.in_fecha, row, 1)
        grid.addWidget(QLabel("Cliente"), row, 2)
        grid.addWidget(self.cb_cliente, row, 3)

        row += 1
        grid.addWidget(QLabel("Observaciones"), row, 0)
        grid.addWidget(self.in_observaciones, row, 1, 1, 3)

        root.addWidget(panel)

            # -------- DETALLE --------
        self.tbl_detalle = QTableWidget(0, 3, self)
        self.tbl_detalle.setHorizontalHeaderLabels(
            ["Vehículo", "Descripción", "Observaciones"]
        )
        self.tbl_detalle.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_detalle.verticalHeader().setVisible(False)

        header = self.tbl_detalle.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        root.addWidget(self.tbl_detalle)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Agregar")
        self.btn_del = QPushButton("Quitar")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_del)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.btn_add.clicked.connect(self._add_detalle_row)
        self.btn_del.clicked.connect(self._remove_row)

        btns = QHBoxLayout()
        self.btn_volver = QPushButton("Volver")
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setObjectName("BtnPrimary")

        btns.addStretch()
        btns.addWidget(self.btn_volver)
        btns.addWidget(self.btn_guardar)
        btns.addStretch()

        root.addLayout(btns)

        self.btn_volver.clicked.connect(self.go_back.emit)
        self.btn_guardar.clicked.connect(self._guardar)
    def _actualizar_numero(self):
        try:
            pto_vta = int(self.in_pto_vta.text())
            numero = self._svc_remitos.sugerir_proximo_numero(pto_vta)
            self.in_numero.setText(str(numero))
        except Exception:
            self.in_numero.setText("")
    def _add_detalle_row(self):
        row = self.tbl_detalle.rowCount()
        self.tbl_detalle.insertRow(row)

        selector = VehiculoSelectorCombo(self._svc_vehiculos, self)
        selector.vehiculo_selected.connect(
            lambda data, r=row: self._on_vehiculo(r, data)
        )

        self.tbl_detalle.setCellWidget(row, 0, selector)
        self.tbl_detalle.setItem(row, 1, QTableWidgetItem(""))
        self.tbl_detalle.setItem(row, 2, QTableWidgetItem(""))
    def _on_vehiculo(self, row: int, vehiculo: Dict[str, Any]):
        desc = f"{vehiculo.get('marca')} {vehiculo.get('modelo')} | Motor: {vehiculo.get('numero_motor')}"
        self.tbl_detalle.item(row, 1).setText(desc)
    def _guardar(self):
        if not self._selected_cliente:
            popUp.toast(self, "Seleccioná un cliente.", kind="warning")
            return

        items = []

        for r in range(self.tbl_detalle.rowCount()):
            selector = self.tbl_detalle.cellWidget(r, 0)
            if not selector or not selector.selected_vehiculo:
                continue

            veh = selector.selected_vehiculo

            items.append({
                "vehiculo_id": veh.get("id"),
                "descripcion": self.tbl_detalle.item(r, 1).text(),
                "observaciones": self.tbl_detalle.item(r, 2).text(),
            })

        if not items:
            popUp.toast(self, "Agregá al menos un vehículo.", kind="warning")
            return

        cabecera = {
            "numero": int(self.in_numero.text()),  # 👈 AGREGAR ESTO
            "punto_venta": int(self.in_pto_vta.text()),
            "fecha_emision": self.in_fecha.text(),
            "cliente_id": self._selected_cliente.get("id"),
            "observaciones": self.in_observaciones.toPlainText(),
        }

        try:
            new_id = self._svc_remitos.create_remito_completo(cabecera, items)
            popUp.toast(self, "Remito creado correctamente.", kind="success")
            self.go_to_detalle.emit(new_id)
        except Exception as e:
            popUp.toast(self, f"Error: {e}", kind="error")
    def _on_cliente(self, data: Dict[str, Any]):
        self._selected_cliente = data
    def _remove_row(self):
        row = self.tbl_detalle.currentRow()
        if row >= 0:
            self.tbl_detalle.removeRow(row)