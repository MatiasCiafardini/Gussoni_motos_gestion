from __future__ import annotations
from typing import Any, Dict, Optional
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel, QListView, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from app.services.vehiculos_service import VehiculosService
from app.ui.widgets.confirm_dialog import ConfirmDialog
from app.ui.widgets.money_spinbox import MoneySpinBox
import app.ui.app_message as popUp
from app.domain.vehiculos_validaciones import validate_vehiculo

class VehiculoDetailPage(QWidget):
    """
    Detalle de un vehículo:
    - Campos como los filtros (LineEdit + ComboBox con estilo FilterCombo)
    - Al entrar: todo deshabilitado
    - Botón Editar/Guardar/Cancelar/Volver en el pie, centrados
    - Volver valida si hay edición pendiente y pide confirmación
    """
    navigate_back = Signal()

    def __init__(self, vehiculo_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("VehiculoDetailPage")

        self.service = VehiculosService()
        self.vehiculo_id = vehiculo_id
        self.data: Dict[str, Any] = {}
        self.edit_mode = False

        # ---------- Controles ----------
        # Línea 0
        self.in_marca = QLineEdit();            self.in_marca.setPlaceholderText("Marca")
        self.in_modelo = QLineEdit();           self.in_modelo.setPlaceholderText("Modelo")
        self.in_anio = QLineEdit();             self.in_anio.setPlaceholderText("Año")
        self.in_anio.setValidator(QIntValidator(1900, 2100, self))

        # Línea 1
        self.in_nro_cert = QLineEdit();         self.in_nro_cert.setPlaceholderText("N° Certificado")
        self.in_nro_dnrpa = QLineEdit();        self.in_nro_dnrpa.setPlaceholderText("N° DNRPA")

        self.in_precio = MoneySpinBox()
        self.in_precio.setMinimumHeight(36)
        self.in_precio.valueChanged.connect(self._mark_edited)


        # Línea 2
        self.in_cuadro = QLineEdit();           self.in_cuadro.setPlaceholderText("N° de cuadro")
        self.in_motor = QLineEdit();            self.in_motor.setPlaceholderText("N° de motor")

        # PROVEEDOR: combo dinámico (muestra nombres, guarda ID)
        self.in_proveedor = QComboBox();        self._setup_combo(self.in_proveedor)
        self.in_proveedor.addItem("Seleccionar", 0)

        # Línea 3 – combos dinámicos
        self.in_color = QComboBox();            self._setup_combo(self.in_color)
        self.in_estado_stock = QComboBox();     self._setup_combo(self.in_estado_stock)
        self.in_condicion = QComboBox();        self._setup_combo(self.in_condicion)  # Nueva/Usada

        # Observaciones (multilínea)
        self.in_observ = QTextEdit()
        self.in_observ.setPlaceholderText("Observaciones")
        self.in_observ.setMinimumHeight(80)

        # ---------- Botonera del pie (centrada) ----------
        self.btn_edit = QPushButton("Editar");      self.btn_edit.setObjectName("BtnPrimary")
        self.btn_save = QPushButton("Guardar");     self.btn_save.setObjectName("BtnPrimary")
        self.btn_cancel = QPushButton("Cancelar");  self.btn_cancel.setObjectName("BtnFlat")
        self.btn_back = QPushButton("Volver");      self.btn_back.setObjectName("BtnGhost")
        for b in (self.btn_edit, self.btn_save, self.btn_cancel, self.btn_back):
            b.setMinimumWidth(140)

        # ---------- Layout filtros (grid 1-3) ----------
        for w in (
            self.in_marca, self.in_modelo, self.in_anio, self.in_nro_cert, self.in_nro_dnrpa,
            self.in_precio, self.in_cuadro, self.in_motor, self.in_proveedor
        ):
            w.setMinimumHeight(36)

        grid = QGridLayout()
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1); grid.setColumnStretch(3, 3)
        grid.setColumnStretch(4, 1); grid.setColumnStretch(5, 3)
        grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)

        row = 0
        grid.addWidget(QLabel("Marca"), row, 0);        grid.addWidget(self.in_marca, row, 1)
        grid.addWidget(QLabel("Modelo"), row, 2);       grid.addWidget(self.in_modelo, row, 3)
        grid.addWidget(QLabel("Año"), row, 4);          grid.addWidget(self.in_anio, row, 5)

        row += 1
        grid.addWidget(QLabel("N° Certificado"), row, 0); grid.addWidget(self.in_nro_cert, row, 1)
        grid.addWidget(QLabel("N° DNRPA"), row, 2);       grid.addWidget(self.in_nro_dnrpa, row, 3)
        grid.addWidget(QLabel("Precio lista (ARS)"), row, 4); grid.addWidget(self.in_precio, row, 5)

        row += 1
        grid.addWidget(QLabel("N° Cuadro"), row, 0);     grid.addWidget(self.in_cuadro, row, 1)
        grid.addWidget(QLabel("N° Motor"), row, 2);      grid.addWidget(self.in_motor, row, 3)
        grid.addWidget(QLabel("Proveedor"), row, 4);     grid.addWidget(self.in_proveedor, row, 5)

        row += 1
        grid.addWidget(QLabel("Color"), row, 0);         grid.addWidget(self.in_color, row, 1)
        grid.addWidget(QLabel("Estado stock"), row, 2);  grid.addWidget(self.in_estado_stock, row, 3)
        grid.addWidget(QLabel("Condición"), row, 4);     grid.addWidget(self.in_condicion, row, 5)

        row += 1
        grid.addWidget(QLabel("Observaciones"), row, 0, Qt.AlignTop)
        grid.addWidget(self.in_observ, row, 1, 1, 5)

        # ---------- Root ----------
        root = QVBoxLayout(self)
        title = QLabel(f"Vehículo #{self.vehiculo_id}")
        title.setObjectName("KpiValue")
        root.addWidget(title)
        root.addLayout(grid)

        # llena el alto restante y empuja la botonera al final
        root.addStretch(1)

        # botonera centrada
        self._footer = QHBoxLayout()
        self._footer.addStretch(1)
        # el orden/visibilidad se maneja en _update_buttons()
        self._footer.addWidget(self.btn_cancel)
        self._footer.addSpacing(8)
        self._footer.addWidget(self.btn_save)
        self._footer.addSpacing(16)
        self._footer.addWidget(self.btn_edit)
        self._footer.addSpacing(16)
        self._footer.addWidget(self.btn_back)
        self._footer.addStretch(1)
        root.addLayout(self._footer)

        # Estados iniciales
        self._set_editable(False)
        self._update_buttons()

        # Señales
        self.btn_edit.clicked.connect(self._toggle_edit)
        self.btn_cancel.clicked.connect(self._cancel_edit)
        self.btn_save.clicked.connect(self._save)
        self.btn_back.clicked.connect(self._on_back_clicked)

        # Carga inicial
        self._load_lookups()
        self._load_data()

    # ---------------------- Helpers UI ----------------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        cb.setMinimumHeight(36)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lv = QListView()
        lv.setObjectName("ComboPopup")
        lv.setUniformItemSizes(True)
        lv.setSpacing(2)
        cb.setView(lv)

    def _set_editable(self, enabled: bool):
        for w in (
            self.in_marca, self.in_modelo, self.in_anio, self.in_nro_cert, self.in_nro_dnrpa,
            self.in_precio, self.in_cuadro, self.in_motor, self.in_proveedor,
            self.in_color, self.in_estado_stock, self.in_condicion, self.in_observ
        ):
            w.setEnabled(enabled)

    def _update_buttons(self):
        """Maneja visibilidad según modo."""
        if self.edit_mode:
            self.btn_edit.hide()
            self.btn_cancel.show()
            self.btn_save.show()
            self.btn_back.show()   # sigue visible; confirma descarte en _on_back_clicked
        else:
            self.btn_edit.show()
            self.btn_cancel.hide()
            self.btn_save.hide()
            self.btn_back.show()

    def _toggle_edit(self):
        self.edit_mode = True
        self._set_editable(True)
        self._update_buttons()

    def _cancel_edit(self):
        self.edit_mode = False
        self._set_editable(False)
        self._fill_fields(self.data)  # volver a valores originales
        self._update_buttons()

    # ---------------------- Data ----------------------
    def _load_lookups(self):
        # Proveedores
        try:
            proveedores = self.service.get_proveedores()
        except Exception:
            proveedores = []
        for p in proveedores:
            # asume columnas: id, nombre (ajustar si tu esquema difiere)
            self.in_proveedor.addItem(p.get("nombre", f"ID {p.get('id')}"), p.get("id"))

        # Colores
        try:
            colores = self.service.get_colores()
        except Exception:
            colores = []
        for c in colores:
            self.in_color.addItem(c.get("nombre", f"ID {c.get('id')}"), c.get("id"))

        # Estados stock
        try:
            est = self.service.get_estados_stock()
        except Exception:
            est = []
        for e in est:
            self.in_estado_stock.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

        # Condición (nueva/usada)
        try:
            cond = self.service.get_estados_condicion()
        except Exception:
            cond = []
        for e in cond:
            self.in_condicion.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

    def _load_data(self):
        data = self.service.get(self.vehiculo_id)
        if not data:
            self.navigate_back.emit()
            return
        self.data = data
        self._fill_fields(data)

    def _fill_fields(self, d: Dict[str, Any]):
        self.in_marca.setText(str(d.get("marca", "") or ""))
        self.in_modelo.setText(str(d.get("modelo", "") or ""))
        self.in_anio.setText(str(d.get("anio") or ""))

        self.in_nro_cert.setText(str(d.get("nro_certificado", "") or ""))
        self.in_nro_dnrpa.setText(str(d.get("nro_dnrpa", "") or ""))

        self.in_precio.setValue(float(d.get("precio_lista") or 0))


        self.in_cuadro.setText(str(d.get("numero_cuadro", "") or ""))
        self.in_motor.setText(str(d.get("numero_motor", "") or ""))

        # seleccionar proveedor por id
        self._set_combo_by_value(self.in_proveedor, d.get("proveedor_id"))

        self._set_combo_by_value(self.in_color, d.get("color_id"))
        self._set_combo_by_value(self.in_estado_stock, d.get("estado_stock_id"))
        self._set_combo_by_value(self.in_condicion, d.get("estado_moto_id"))

        self.in_observ.setPlainText(str(d.get("observaciones", "") or ""))

    def _set_combo_by_value(self, cb: QComboBox, value: Optional[int]):
        if value is None:
            cb.setCurrentIndex(0)
            return
        for i in range(cb.count()):
            if cb.itemData(i) == value:
                cb.setCurrentIndex(i)
                return
        cb.setCurrentIndex(0)

    # ---------------------- Back con confirmación ----------------------
    def _on_back_clicked(self):
        if self.edit_mode:
            if not ConfirmDialog.ask_discard(self):
                return
            self._cancel_edit()
        self.navigate_back.emit()


    def _collect_payload(self) -> Dict[str, Any]:
        anio = self.in_anio.text().strip()
        precio = self.in_precio.value()
        

        payload: Dict[str, Any] = {
            "marca": self.in_marca.text().strip() or None,
            "modelo": self.in_modelo.text().strip() or None,
            "anio": int(anio) if anio.isdigit() else None,
            "nro_certificado": self.in_nro_cert.text().strip() or None,
            "nro_dnrpa": self.in_nro_dnrpa.text().strip() or None,
            "numero_cuadro": self.in_cuadro.text().strip() or None,
            "numero_motor": self.in_motor.text().strip() or None,
            "precio_lista": precio if precio > 0 else None,
            "proveedor_id": self.in_proveedor.currentData(),
            "color_id": self.in_color.currentData(),
            "estado_stock_id": self.in_estado_stock.currentData(),
            "estado_moto_id": self.in_condicion.currentData(),
            "observaciones": self.in_observ.toPlainText().strip() or None,
        }
        return payload

    def _mark_edited(self, *_):
        self.edit_mode = True

    def _save(self):
        payload = self._collect_payload()

        # Mezclamos datos originales + cambios del usuario
        final_data = {**self.data, **payload}

        ok, errs = validate_vehiculo(final_data)
        if not ok:
            msg = "\n".join(f"• {v}" for v in errs.values())
            popUp.warning(self, "Vehículo", msg)
            return

        try:
            self.service.update(self.vehiculo_id, payload)
        except Exception as ex:
            popUp.error(
                self,
                "Vehículo",
                f"Error al guardar el vehículo:\n{ex}",
            )
            return

        self.edit_mode = False
        self._set_editable(False)
        self._load_data()
        self._update_buttons()

