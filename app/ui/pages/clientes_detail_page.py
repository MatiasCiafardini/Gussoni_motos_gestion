from __future__ import annotations

from typing import Any, Dict, Optional
import re

from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator, QIcon
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel, QListView, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView
)

import app.ui.app_message as popUp
from app.ui.widgets.registrar_pago_dialog import RegistrarPagoDialog
from app.domain.clientes_validaciones import validar_cliente
from app.ui.utils.table_utils import setup_compact_table
from PySide6.QtWidgets import QAbstractItemView
from app.ui.utils.text_utils import normalize_title

from app.services.clientes_service import ClientesService
from app.services.ventas_service import VentasService
from pathlib import Path

import sys

def get_assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Ejecutando como .exe (PyInstaller)
        base_path = Path(sys._MEIPASS)
    else:
        # Ejecutando en desarrollo
        base_path = Path(__file__).resolve().parents[2]

    return base_path / "assets"

ASSETS_DIR = get_assets_dir()


class ClientesDetailPage(QWidget):
    navigate_back = Signal()
    navigate_to_factura = Signal(int)  # factura_id
    navigate_to_factura_nueva = Signal(int)  # cliente_id

    def __init__(self, cliente_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ClientesDetailPage")
        
        self.service = ClientesService()
        self.ventas_service = VentasService()
        self.btn_add_factura = QPushButton("Agregar factura")
        self.btn_add_factura.setObjectName("BtnPrimary")

        self.cliente_id = cliente_id
        self.data: Dict[str, Any] = {}
        self.edit_mode = False

        # =========================
        # CAMPOS CLIENTE
        # =========================
        self.in_nombre = QLineEdit()
        self.in_apellido = QLineEdit()

        self.in_tipo_doc = QComboBox()
        self._setup_combo(self.in_tipo_doc)

        self.in_nro_doc = QLineEdit()

        self._validator_dni = QRegularExpressionValidator(QRegularExpression(r"^\d{1,8}$"), self)
        self._validator_cuit = QRegularExpressionValidator(QRegularExpression(r"^\d{1,11}$"), self)
        self._validator_otro = QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9]{1,20}$"), self)

        self.in_nro_doc.setValidator(self._validator_dni)

        self.in_email = QLineEdit()
        self.in_telefono = QLineEdit()
        self.in_direccion = QLineEdit()

        self.in_estado = QComboBox()
        self._setup_combo(self.in_estado)

        self.in_observ = QTextEdit()
        self.in_observ.setMinimumHeight(80)
        # Normalizar texto al salir del campo
        self.in_nombre.editingFinished.connect(
            lambda: self.in_nombre.setText(
                normalize_title(self.in_nombre.text())
            )
        )

        self.in_apellido.editingFinished.connect(
            lambda: self.in_apellido.setText(
                normalize_title(self.in_apellido.text())
            )
        )

        self.in_direccion.editingFinished.connect(
            lambda: self.in_direccion.setText(
                normalize_title(self.in_direccion.text())
            )
        )

        # =========================
        # BOTONES
        # =========================
        self.btn_edit = QPushButton("Editar")
        self.btn_edit.setObjectName("BtnPrimary")

        self.btn_save = QPushButton("Guardar")
        self.btn_save.setObjectName("BtnPrimary")

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("BtnFlat")

        self.btn_back = QPushButton("Volver")
        self.btn_back.setObjectName("BtnGhost")

        # =========================
        # LAYOUT FORM
        # =========================
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        row = 0
        grid.addWidget(QLabel("Nombre"), row, 0)
        grid.addWidget(self.in_nombre, row, 1)
        grid.addWidget(QLabel("Apellido"), row, 2)
        grid.addWidget(self.in_apellido, row, 3)

        row += 1
        grid.addWidget(QLabel("Tipo doc"), row, 0)
        grid.addWidget(self.in_tipo_doc, row, 1)
        grid.addWidget(QLabel("N° doc"), row, 2)
        grid.addWidget(self.in_nro_doc, row, 3)

        row += 1
        grid.addWidget(QLabel("Email"), row, 0)
        grid.addWidget(self.in_email, row, 1)
        grid.addWidget(QLabel("Teléfono"), row, 2)
        grid.addWidget(self.in_telefono, row, 3)

        row += 1
        grid.addWidget(QLabel("Dirección"), row, 0)
        grid.addWidget(self.in_direccion, row, 1)
        grid.addWidget(QLabel("Estado"), row, 2)
        grid.addWidget(self.in_estado, row, 3)

        row += 1
        grid.addWidget(QLabel("Observaciones"), row, 0, Qt.AlignTop)
        grid.addWidget(self.in_observ, row, 1, 1, 3)

        # =========================
        # SECCIÓN VENTAS (CARD)
        # =========================
        self.section_ventas = QWidget()
        self.section_ventas.setObjectName("Card")

        ventas_layout = QVBoxLayout(self.section_ventas)
        ventas_layout.setContentsMargins(16, 16, 16, 16)
        ventas_layout.setSpacing(12)

        lbl_ventas = QLabel("Ventas del cliente")
        lbl_ventas.setObjectName("SectionTitle")
        ventas_layout.addWidget(lbl_ventas)

        self.tbl_ventas = QTableWidget(0, 6)
        self.tbl_ventas.setObjectName("DataTable")

        self.tbl_ventas.setHorizontalHeaderLabels([
            "Fecha", "Descripción", "Precio", "Forma de pago", "Estado", "Acciones"
        ])

        self.tbl_ventas.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_ventas.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_ventas.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_ventas.setAlternatingRowColors(True)
        self.tbl_ventas.verticalHeader().setVisible(False)
        self.tbl_ventas.setSortingEnabled(False)

        # 🔑 clave para que crezca bien
        self.tbl_ventas.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        # 👇 mismo helper que el resto del sistema
        setup_compact_table(self.tbl_ventas)

        header = self.tbl_ventas.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)


        ventas_layout.addWidget(self.tbl_ventas)

        # =========================
        # ROOT
        # =========================
        root = QVBoxLayout(self)
        root.addLayout(grid)
        root.addSpacing(16)
        root.addWidget(self.section_ventas)
        root.addStretch(1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.btn_cancel)
        footer.addSpacing(8)
        footer.addWidget(self.btn_save)
        footer.addSpacing(16)
        footer.addWidget(self.btn_edit)
        footer.addSpacing(16)
        footer.addWidget(self.btn_add_factura)
        footer.addSpacing(16)
        footer.addWidget(self.btn_back)
        footer.addStretch(1)
        root.addLayout(footer)

        # =========================
        # ESTADO INICIAL
        # =========================
        self._set_editable(False)
        self._update_buttons()

        # =========================
        # SEÑALES
        # =========================
        self.btn_edit.clicked.connect(self._toggle_edit)
        self.btn_cancel.clicked.connect(self._cancel_edit)
        self.btn_save.clicked.connect(self._save)
        self.btn_back.clicked.connect(self._on_back_clicked)
        self.btn_add_factura.clicked.connect(self._on_add_factura)

        self.in_tipo_doc.currentIndexChanged.connect(self._on_tipo_doc_changed)

        # =========================
        # CARGA
        # =========================
        self._load_lookups()
        self._load_data()
        self._load_ventas()

    # -----------------------------------------------------
    # HELPERS UI
    # -----------------------------------------------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        cb.setMinimumHeight(36)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lv = QListView()
        lv.setObjectName("ComboPopup")
        lv.setUniformItemSizes(True)
        lv.setSpacing(2)
        cb.setView(lv)
    def _on_add_factura(self):
        self.navigate_to_factura_nueva.emit(self.cliente_id)

    def _set_editable(self, enabled: bool):
        for w in (
            self.in_nombre, self.in_apellido, self.in_tipo_doc, self.in_nro_doc,
            self.in_email, self.in_telefono, self.in_direccion, self.in_estado, self.in_observ
        ):
            w.setEnabled(enabled)

        # regla pedida: ocultar ventas al editar
        self.section_ventas.setVisible(not enabled)

    def _update_buttons(self):
        self.btn_edit.setVisible(not self.edit_mode)
        self.btn_save.setVisible(self.edit_mode)
        self.btn_cancel.setVisible(self.edit_mode)

    # -----------------------------------------------------
    # DOCUMENTO
    # -----------------------------------------------------
    def _on_tipo_doc_changed(self, _):
        tipo_id = self.in_tipo_doc.currentData()
        if not tipo_id:
            self.in_nro_doc.setValidator(self._validator_otro)
            return

        catalogos = self.service._catalogos

        if catalogos.es_cuit(tipo_id) or catalogos.es_cuil(tipo_id):
            self.in_nro_doc.setValidator(self._validator_cuit)
        elif catalogos.es_dni(tipo_id):
            self.in_nro_doc.setValidator(self._validator_dni)
        else:
            self.in_nro_doc.setValidator(self._validator_otro)



    # -----------------------------------------------------
    # VENTAS
    # -----------------------------------------------------
    def _load_ventas(self):
        self.tbl_ventas.setRowCount(0)
        ventas = self.ventas_service.get_by_cliente(self.cliente_id)

        for v in ventas:
            row = self.tbl_ventas.rowCount()
            self.tbl_ventas.insertRow(row)

            self.tbl_ventas.setItem(row, 0, QTableWidgetItem(str(v["fecha"])))
            self.tbl_ventas.setItem(row, 1, QTableWidgetItem(v["descripcion"]))
            self.tbl_ventas.setItem(row, 2, QTableWidgetItem(f"$ {v['precio_operacion']:.2f}"))
            self.tbl_ventas.setItem(row, 3, QTableWidgetItem(v["forma_pago"]))
            self.tbl_ventas.setItem(row, 4, QTableWidgetItem(v["estado_financiero"]))

            btns = QWidget()
            lay = QHBoxLayout(btns)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            lay.setAlignment(Qt.AlignCenter)

            b_factura = QPushButton()
            b_factura.setIcon(QIcon(str(ASSETS_DIR / "lupa.svg")))
            b_factura.setToolTip("Consultar factura")
            b_factura.setObjectName("IconButton")
            b_factura.clicked.connect(
                lambda _, fid=v["factura_id"]: self._ver_factura(fid)
            )

            estado = (v.get("estado_financiero") or "").lower()

            lay.addWidget(b_factura)

            # 👉 solo permitir pagar si está pendiente
            if estado in ("pendiente pago", "pendiente"):
                b_pago = QPushButton()
                b_pago.setIcon(QIcon(str(ASSETS_DIR / "pago.svg")))
                b_pago.setToolTip("Registrar pago")
                b_pago.setObjectName("IconButton")
                b_pago.clicked.connect(
                    lambda _, vid=v["id"]: self._registrar_pago(vid)
                )
                lay.addWidget(b_pago)


            self.tbl_ventas.setCellWidget(row, 5, btns)

    def _ver_factura(self, factura_id: Optional[int]):
        if not factura_id:
            popUp.warning(self, "Factura", "La venta no tiene factura asociada.")
            return
        self.navigate_to_factura.emit(factura_id)

    def _registrar_pago(self, venta_id: int):
        dialog = RegistrarPagoDialog(
            venta_id=venta_id,
            cliente_id=self.cliente_id,
            parent=self
        )
    
        if dialog.exec():
            self._load_ventas()
    


    # -----------------------------------------------------
    # DATA CLIENTE
    # -----------------------------------------------------
    def _load_lookups(self):
    # Tipos documento desde catálogo
        self.in_tipo_doc.clear()
        tipos = self.service.get_tipos_documento() or []
        for t in tipos:
            label = t.get("descripcion") or t.get("codigo") or ""
            self.in_tipo_doc.addItem(label, t.get("id"))

        # Estados desde catálogo
        self.in_estado.clear()
        estados = self.service.get_estados_clientes() or []
        for e in estados:
            self.in_estado.addItem(e.get("nombre"), e.get("id"))


    def _load_data(self):
        data = self.service.get(self.cliente_id)
        if not data:
            popUp.warning(self, "Clientes", "Cliente no encontrado.")
            self.navigate_back.emit()
            return
        self.data = data
        self._fill_fields(data)

    def _fill_fields(self, d: Dict[str, Any]):
        self.in_nombre.setText(d.get("nombre", ""))
        self.in_apellido.setText(d.get("apellido", ""))
        self.in_nro_doc.setText(d.get("nro_doc", ""))
        self.in_email.setText(d.get("email", ""))
        self.in_telefono.setText(d.get("telefono", ""))
        self.in_direccion.setText(d.get("direccion", ""))
        self.in_observ.setPlainText(d.get("observaciones", ""))
        tipo_id = d.get("tipo_doc_id")
        if tipo_id is not None:
            idx = self.in_tipo_doc.findData(tipo_id)
            if idx != -1:
                self.in_tipo_doc.setCurrentIndex(idx)
        estado_id = d.get("estado_id")
        if estado_id is not None:
            idx_estado = self.in_estado.findData(estado_id)
            if idx_estado != -1:
                self.in_estado.setCurrentIndex(idx_estado)
    # -----------------------------------------------------
    # EDICIÓN
    # -----------------------------------------------------
    def _toggle_edit(self):
        self.edit_mode = True
        self._set_editable(True)
        self._update_buttons()

    def _cancel_edit(self):
        self.edit_mode = False
        self._set_editable(False)
        self._fill_fields(self.data)
        self._update_buttons()

    def _on_back_clicked(self):
        if self.edit_mode:
            if not popUp.ask_discard(self):
                return
            self._cancel_edit()
        self.navigate_back.emit()

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------
    def _save(self):
        payload = {
            "tipo_doc_id": self.in_tipo_doc.currentData(),
            "nro_doc": self.in_nro_doc.text().strip(),
            "nombre": self.in_nombre.text().strip(),
            "apellido": self.in_apellido.text().strip(),
            "email": self.in_email.text().strip() or None,
            "telefono": self.in_telefono.text().strip() or None,
            "direccion": self.in_direccion.text().strip() or None,
            "estado_id": self.in_estado.currentData(),
            "observaciones": self.in_observ.toPlainText().strip() or None,
        }

        ok, errs = validar_cliente(payload)
        if not ok:
            popUp.toast(self, "\n".join(f"• {v}" for v in errs.values()), kind="warning")
            return
        try:
            self.service.update(self.cliente_id, payload)
        except Exception as ex:
            popUp.toast(self, str(ex), kind="error")
            return

        self.edit_mode = False
        self._set_editable(False)
        self._load_data()
        self._load_ventas()
        self._update_buttons()
