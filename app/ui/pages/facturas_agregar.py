from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QDate, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QTextEdit, QPushButton, QSizePolicy, QListView, QFrame,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QMainWindow
)
import app.ui.app_message as popUp
from app.services.facturas_service import FacturasService
from app.services.clientes_service import ClientesService
from app.services.vehiculos_service import VehiculosService
from app.ui.widgets.confirm_dialog import ConfirmDialog
from app.ui.notify import NotifyPopup
from PySide6.QtCore import Qt, QDate
from app.data.database import SessionLocal
from sqlalchemy import text


# -------- Helpers --------

def _setup_combo(cb: QComboBox) -> None:
    cb.setObjectName("FilterCombo")
    lv = QListView()
    lv.setObjectName("ComboPopup")
    lv.setUniformItemSizes(True)
    lv.setSpacing(2)
    cb.setView(lv)
    cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


def _parse_decimal(text: str) -> float:
    if text is None:
        return 0.0
    t = str(text).strip()
    if not t:
        return 0.0
    for ch in ("$", " ", "\u00a0"):
        t = t.replace(ch, "")
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except Exception:
        return 0.0


def _format_money(value: float) -> str:
    try:
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"{value:.2f}"


def _cliente_label(c: Dict[str, Any]) -> str:
    nombre = f"{c.get('nombre', '')} {c.get('apellido', '')}".strip()
    doc = f"{c.get('tipo_doc', '')} {c.get('nro_doc', '')}".strip()
    label = nombre
    if doc:
        label += f" ({doc})"
    return label or "(sin nombre)"


def _vehiculo_label(v: Dict[str, Any]) -> str:
    desc = f"{v.get('marca', '')} {v.get('modelo', '')}".strip()
    anio = v.get("anio")
    if anio:
        desc += f" {anio}"
    nro_motor = v.get("numero_motor") or v.get("nro_motor")
    if nro_motor:
        desc += f" | Motor: {nro_motor}"
    nro_cuadro = v.get("numero_cuadro") or v.get("nro_cuadro")
    if nro_cuadro:
        desc += f" | Cuadro: {nro_cuadro}"
    return desc or "(sin descripción)"


def _style_section_label(lbl: QLabel) -> None:
    """Títulos de sección: solo negrita, sin fondo de color."""
    lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    lbl.setStyleSheet(
        """
        font-weight: 600;
        padding: 2px 0;
        """
    )


# -------- Combo dinámico de vehículos --------

class VehiculoSelectorCombo(QComboBox):
    """
    QComboBox editable que busca vehículos dinámicamente.
    """

    vehiculo_selected = Signal(dict)

    def __init__(self, vehiculos_service: VehiculosService, parent: Optional[Widget] = None) -> None:
        super().__init__(parent)
        _setup_combo(self)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

        le = self.lineEdit()
        le.setPlaceholderText("Buscar vehículo...")
        le.setClearButtonEnabled(True)

        self._svc = vehiculos_service
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._do_search)

        self._results: List[Dict[str, Any]] = []
        self._selected: Optional[Dict[str, Any]] = None

        le.textEdited.connect(self._on_text_edited)
        self.currentIndexChanged.connect(self._on_index_changed)
        

    @property
    def selected_vehiculo(self) -> Optional[Dict[str, Any]]:
        return self._selected

    # ---- búsqueda ----
    def _on_text_edited(self, _text: str) -> None:
        self._selected = None
        self._timer.start()

    def _do_search(self) -> None:
        text = (self.lineEdit().text() or "").strip()
        if len(text) < 4:
            self._results = []
            self.blockSignals(True)
            self.clear()
            self.blockSignals(False)
            return

        filtros = {
            "q": text,
            "page": 1,
            "page_size": 20,
        }
        try:
            rows, _ = self._svc.search(filtros, page=1, page_size=20)
        except Exception as ex:
            NotifyPopup(f"Error al buscar vehículos: {ex}", "error", self).show_centered()
            rows = []

        self._results = rows or []

        current_text = self.lineEdit().text()
        self.blockSignals(True)
        self.clear()
        for v in self._results:
            self.addItem(_vehiculo_label(v), v)
        self.setCurrentIndex(-1)
        self.blockSignals(False)
        self.lineEdit().setText(current_text)
        if self.count() > 0:
            self.showPopup()

    def _on_index_changed(self, index: int) -> None:
        if index < 0:
            self._selected = None
            return
        data = self.itemData(index)
        if not isinstance(data, dict):
            self._selected = None
            return
        self._selected = data
        self.vehiculo_selected.emit(data)


# -------- Página FacturasAgregar --------

class FacturasAgregarPage(QWidget):
    go_back = Signal()
    go_to_detalle = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None, main_window: Optional[QMainWindow] = None) -> None:
        super().__init__(parent)
        self.setObjectName("FacturasAgregarPage")

        self._svc_facturas = FacturasService()
        self._svc_clientes = ClientesService()
        self._svc_vehiculos = VehiculosService()

        self._main_window = main_window
        self._dirty = False
        self._selected_cliente: Optional[Dict[str, Any]] = None

        self._cliente_search_timer = QTimer(self)
        self._cliente_search_timer.setSingleShot(True)
        self._cliente_search_timer.setInterval(150)
        self._cliente_search_timer.timeout.connect(self._do_cliente_search)

        self._cliente_results: List[Dict[str, Any]] = []

        # Lista cacheada de condiciones IVA (para poder buscar por código)
        self._cond_iva_receptor_list: List[Dict[str, Any]] = []

        # Lista de facturas del cliente para NC
        self._facturas_cliente_nc: List[Dict[str, Any]] = []

        self._build_ui()
        self._load_tipos_comprobante()
        self._load_formas_pago()
        self.cb_forma_pago.currentIndexChanged.connect(self._on_forma_pago_changed)

        self._load_formas_pago()
        self.cb_forma_pago.currentIndexChanged.connect(self._on_forma_pago_changed)

        self._load_puntos_venta()
        self._load_condicion_iva_receptor()
        self._add_detalle_row()
        # Ajuste inicial de anchos (por las dudas)
        self._ajustar_ancho_detalle()
        # Aseguramos que arranca en modo "factura normal"
        self._actualizar_modo_nc()
        self._on_forma_pago_changed()

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(6)

        title = QLabel("Nueva factura")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        main.addWidget(title)

        # --- Sección 1: Datos factura ---
        sec1 = QFrame(self)
        sec1.setObjectName("Panel")
        sec1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        sec1_l = QVBoxLayout(sec1)
        sec1_l.setContentsMargins(10, 10, 10, 10)
        sec1_l.setSpacing(8)

        lbl1 = QLabel("Datos de la factura")
        _style_section_label(lbl1)
        sec1_l.addWidget(lbl1)

        grid1 = QGridLayout()
        grid1.setContentsMargins(0, 0, 0, 0)
        grid1.setHorizontalSpacing(8)
        grid1.setVerticalSpacing(6)
        sec1_l.addLayout(grid1)

        # columnas 1 3 1 3 1 3
        for col, stretch in enumerate((1, 3, 1, 3, 1, 3)):
            grid1.setColumnStretch(col, stretch)

        self.in_tipo = QComboBox()
        _setup_combo(self.in_tipo)

        # Punto de venta como combo desplegable
        self.in_pto_vta = QComboBox()
        _setup_combo(self.in_pto_vta)

        self.in_numero = QLineEdit()
        self.in_numero.setPlaceholderText("Se definirá al guardar")
        # Lo dejamos de solo lectura: la numeración la maneja el sistema
        self.in_numero.setReadOnly(True)

        # Fecha de emisión
        self.in_fecha_emision = QLineEdit()
        self.in_fecha_emision.setText(QDate.currentDate().toString("yyyy-MM-dd"))

        self.in_moneda = QLineEdit("ARS")
        self.in_moneda.setReadOnly(True)

        # NUEVO: combo Condición IVA receptor (almacena ID INT)
        self.in_condicion_iva_receptor = QComboBox()
        _setup_combo(self.in_condicion_iva_receptor)

        # Observaciones
        self.in_observaciones = QTextEdit()
        self.in_observaciones.setPlaceholderText(
            "Observaciones internas, comentarios, condiciones especiales, etc."
        )
        # Para que se vea como campo “con recuadro” como los demás
        self.in_observaciones.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
        self.in_observaciones.setFixedHeight(70)

        row = 0
        # Fila 1: Tipo / Punto de venta / Número
        grid1.addWidget(QLabel("Tipo"), row, 0)
        grid1.addWidget(self.in_tipo, row, 1)
        grid1.addWidget(QLabel("Pto Vta"), row, 2)
        grid1.addWidget(self.in_pto_vta, row, 3)
        grid1.addWidget(QLabel("Número"), row, 4)
        grid1.addWidget(self.in_numero, row, 5)

        # Fila 2: Condición IVA / Fecha emisión
        row += 1
        grid1.addWidget(QLabel("Condición IVA receptor"), row, 0)
        grid1.addWidget(self.in_condicion_iva_receptor, row, 1)
        grid1.addWidget(QLabel("Fecha emisión"), row, 2)
        grid1.addWidget(self.in_fecha_emision, row, 3)
        grid1.addWidget(QLabel("Moneda"), row, 4)
        grid1.addWidget(self.in_moneda, row, 5)

        # Fila 3: Observaciones
        row += 1
        grid1.addWidget(QLabel("Observaciones"), row, 0)
        grid1.addWidget(self.in_observaciones, row, 1, 1, 5)

        main.addWidget(sec1)

        self.in_tipo.currentIndexChanged.connect(self._on_tipo_or_pto_changed)
        self.in_pto_vta.currentIndexChanged.connect(self._on_tipo_or_pto_changed)
        self.in_observaciones.textChanged.connect(self._on_observaciones_changed)

        # --- Sección 2: Cliente ---
        sec2 = QFrame(self)
        sec2.setObjectName("Panel")
        sec2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        sec2_l = QVBoxLayout(sec2)
        sec2_l.setContentsMargins(10, 10, 10, 10)
        sec2_l.setSpacing(8)

        lbl2 = QLabel("Datos del cliente")
        _style_section_label(lbl2)
        sec2_l.addWidget(lbl2)

        grid2 = QGridLayout()
        grid2.setContentsMargins(0, 0, 0, 0)
        grid2.setHorizontalSpacing(8)
        grid2.setVerticalSpacing(4)
        sec2_l.addLayout(grid2)

        for col, stretch in enumerate((1, 3, 1, 3, 1, 3)):
            grid2.setColumnStretch(col, stretch)

        # fila 1: buscar cliente + limpiar
        self.cb_cliente = QComboBox()
        _setup_combo(self.cb_cliente)
        self.cb_cliente.setEditable(True)
        self.cb_cliente.setInsertPolicy(QComboBox.NoInsert)
        le_cli = self.cb_cliente.lineEdit()
        le_cli.setPlaceholderText("Escribí nombre, apellido o documento...")
        le_cli.setClearButtonEnabled(True)

        self.btn_cliente_limpiar = QPushButton("Limpiar")
        self.btn_cliente_limpiar.setObjectName("BtnPrimary")

        row = 0
        grid2.addWidget(QLabel("Buscar cliente"), row, 0)
        grid2.addWidget(self.cb_cliente, row, 1, 1, 1)
        grid2.addWidget(self.btn_cliente_limpiar, row, 2)

        # fila 2: tipo doc + nro doc
        self.in_cliente_tipo_doc = QLineEdit()
        self.in_cliente_tipo_doc.setReadOnly(True)
        self.in_cliente_nro_doc = QLineEdit()
        self.in_cliente_nro_doc.setReadOnly(True)

        row += 1
        grid2.addWidget(QLabel("Tipo doc."), row, 0)
        grid2.addWidget(self.in_cliente_tipo_doc, row, 1)
        grid2.addWidget(QLabel("Nro doc."), row, 2)
        grid2.addWidget(self.in_cliente_nro_doc, row, 3, 1, 3)

        # fila 3: email + teléfono + dirección
        self.in_cliente_email = QLineEdit()
        self.in_cliente_email.setReadOnly(True)
        self.in_cliente_telefono = QLineEdit()
        self.in_cliente_telefono.setReadOnly(True)
        self.in_cliente_direccion = QLineEdit()
        self.in_cliente_direccion.setReadOnly(True)

        row += 1
        grid2.addWidget(QLabel("Email"), row, 0)
        grid2.addWidget(self.in_cliente_email, row, 1)
        grid2.addWidget(QLabel("Teléfono"), row, 2)
        grid2.addWidget(self.in_cliente_telefono, row, 3)
        grid2.addWidget(QLabel("Dirección"), row, 4)
        grid2.addWidget(self.in_cliente_direccion, row, 5)

        main.addWidget(sec2)

        le_cli.textEdited.connect(self._on_cliente_text_edited)
        self.cb_cliente.currentIndexChanged.connect(self._on_cliente_selected)
        self.btn_cliente_limpiar.clicked.connect(self._on_cliente_limpiar)

        # --- Sección: Datos de la venta / Forma de pago ---

        sec_venta = QFrame(self)
        sec_venta.setObjectName("Panel")
        sec_venta.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        sec_venta_l = QVBoxLayout(sec_venta)
        sec_venta_l.setContentsMargins(10, 10, 10, 10)
        sec_venta_l.setSpacing(8)

        lblv = QLabel("Datos de la venta")
        _style_section_label(lblv)
        sec_venta_l.addWidget(lblv)

        gridv = QGridLayout()
        gridv.setHorizontalSpacing(8)
        gridv.setVerticalSpacing(6)
        sec_venta_l.addLayout(gridv)

        # columnas 1 3 1 3 1 3
        for col, stretch in enumerate((1, 3, 1, 3, 1, 3)):
            gridv.setColumnStretch(col, stretch)

        self.in_precio_real = QLineEdit()
        self.in_precio_real.setPlaceholderText("Precio total de la operación")

        self.cb_forma_pago = QComboBox()
        _setup_combo(self.cb_forma_pago)

        self.in_anticipo = QLineEdit()
        self.in_anticipo.setPlaceholderText("Anticipo")
        self.lbl_anticipo = QLabel("Anticipo")
        self.in_cantidad_cuotas = QLineEdit()
        self.in_cantidad_cuotas.setPlaceholderText("Cantidad de cuotas")
        self.lbl_cantidad_cuotas = QLabel("Cantidad de cuotas")
        self.in_interes_pct = QLineEdit()
        self.in_interes_pct.setPlaceholderText("Interés %")
        self.lbl_interes = QLabel("Interés")

        row = 0
        gridv.addWidget(QLabel("Precio real"), row, 0)
        gridv.addWidget(self.in_precio_real, row, 1)
        gridv.addWidget(QLabel("Forma de pago"), row, 2)
        gridv.addWidget(self.cb_forma_pago, row, 3)
        gridv.addWidget(self.lbl_anticipo, row, 4)
        gridv.addWidget(self.in_anticipo, row, 5)

        row += 1
        gridv.addWidget(self.lbl_cantidad_cuotas, row, 0)
        gridv.addWidget(self.in_cantidad_cuotas, row, 1)
        gridv.addWidget(self.lbl_interes, row, 2)
        gridv.addWidget(self.in_interes_pct, row, 3)
        


        main.addWidget(sec_venta)

        
        # --- Sección 3: Detalle (responsive) ---
        sec3 = QFrame(self)
        sec3.setObjectName("Panel")
        sec3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sec_detalle = sec3  # para poder ocultar/mostrar

        sec3_l = QVBoxLayout(sec3)
        sec3_l.setContentsMargins(10, 10, 10, 10)
        sec3_l.setSpacing(8)

        lbl3 = QLabel("Detalle de la factura")
        _style_section_label(lbl3)
        sec3_l.addWidget(lbl3)

        self.tbl_detalle = QTableWidget(0, 7, self)
        self.tbl_detalle.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_detalle.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_detalle.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_detalle.setAlternatingRowColors(True)
        self.tbl_detalle.verticalHeader().setVisible(False)
        self.tbl_detalle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tbl_detalle.setMinimumHeight(250)

        self.tbl_detalle.setHorizontalHeaderLabels(
            ["Vehículo", "Cant.", "P. Unitario", "IVA %", "Neto", "IVA", "Total"]
        )
        header = self.tbl_detalle.horizontalHeader()

        # Todas las columnas en modo interactivo; el tamaño lo manejamos nosotros.
        for col in range(7):
            header.setSectionResizeMode(col, QHeaderView.Interactive)

        # ancho inicial aproximado
        self.tbl_detalle.setColumnWidth(0, 320)  # Vehículo
        self.tbl_detalle.setColumnWidth(1, 100)
        self.tbl_detalle.setColumnWidth(2, 140)
        self.tbl_detalle.setColumnWidth(3, 90)
        self.tbl_detalle.setColumnWidth(4, 130)
        self.tbl_detalle.setColumnWidth(5, 130)
        self.tbl_detalle.setColumnWidth(6, 130)

        sec3_l.addWidget(self.tbl_detalle)

        row_btns = QHBoxLayout()
        row_btns.setContentsMargins(0, 0, 0, 0)
        row_btns.setSpacing(6)
        self.btn_add_row = QPushButton("+ Agregar fila")
        self.btn_add_row.setObjectName("BtnPrimary")
        self.btn_del_row = QPushButton("Quitar fila")
        row_btns.addWidget(self.btn_add_row)
        row_btns.addWidget(self.btn_del_row)
        row_btns.addStretch(1)
        sec3_l.addLayout(row_btns)

        # Totales
        tot_layout = QGridLayout()
        tot_layout.setContentsMargins(0, 0, 0, 0)
        tot_layout.setHorizontalSpacing(8)
        tot_layout.setVerticalSpacing(4)
        tot_layout.setColumnStretch(0, 1)
        tot_layout.setColumnStretch(1, 3)

        self.in_subtotal = QLineEdit("0,00")
        self.in_subtotal.setReadOnly(True)
        self.in_subtotal.setAlignment(Qt.AlignRight)
        self.in_iva_total = QLineEdit("0,00")
        self.in_iva_total.setReadOnly(True)
        self.in_iva_total.setAlignment(Qt.AlignRight)
        self.in_total = QLineEdit("0,00")
        self.in_total.setReadOnly(True)
        self.in_total.setAlignment(Qt.AlignRight)

        r = 0
        tot_layout.addWidget(QLabel("Subtotal"), r, 0)
        tot_layout.addWidget(self.in_subtotal, r, 1)
        r += 1
        tot_layout.addWidget(QLabel("IVA"), r, 0)
        tot_layout.addWidget(self.in_iva_total, r, 1)
        r += 1
        tot_layout.addWidget(QLabel("Total"), r, 0)
        tot_layout.addWidget(self.in_total, r, 1)

        tot_wrap = QHBoxLayout()
        tot_wrap.addStretch(1)
        tot_wrap.addLayout(tot_layout)
        sec3_l.addLayout(tot_wrap)

        main.addWidget(sec3, 1)

        self.btn_add_row.clicked.connect(self._add_detalle_row)
        self.btn_del_row.clicked.connect(self._remove_selected_row)

        # --- Sección 4: Comprobantes (para Nota de Crédito) ---
        sec_nc = QFrame(self)
        sec_nc.setObjectName("Panel")
        sec_nc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sec_comprobantes = sec_nc

        sec_nc_l = QVBoxLayout(sec_nc)
        sec_nc_l.setContentsMargins(10, 10, 10, 10)
        sec_nc_l.setSpacing(8)

        lbl_nc = QLabel("Comprobantes")
        _style_section_label(lbl_nc)
        sec_nc_l.addWidget(lbl_nc)

        grid_nc = QGridLayout()
        grid_nc.setContentsMargins(0, 0, 0, 0)
        grid_nc.setHorizontalSpacing(8)
        grid_nc.setVerticalSpacing(4)
        sec_nc_l.addLayout(grid_nc)

        for col, stretch in enumerate((1, 3, 1, 3, 1, 3)):
            grid_nc.setColumnStretch(col, stretch)

        self.cb_comprobante = QComboBox()
        _setup_combo(self.cb_comprobante)
        self.cb_comprobante.setEditable(False)

        row_nc = 0
        grid_nc.addWidget(QLabel("Comprobante asociado"), row_nc, 0)
        grid_nc.addWidget(self.cb_comprobante, row_nc, 1, 1, 5)

        main.addWidget(sec_nc, 1)
        self.sec_comprobantes.setVisible(False)

        # --- Botones pie ---
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 8, 0, 0)
        btns.setSpacing(8)

        self.btn_volver = QPushButton("Volver")
        self.btn_guardar = QPushButton("Enviar")
        self.btn_guardar_ver = QPushButton("Enviar y consultar")

        self.btn_guardar.setObjectName("BtnPrimary")
        self.btn_guardar_ver.setObjectName("BtnPrimary")

        btns.addStretch(1)
        btns.addWidget(self.btn_volver)
        btns.addSpacing(8)
        btns.addWidget(self.btn_guardar)
        btns.addWidget(self.btn_guardar_ver)
        btns.addStretch(1)
        main.addLayout(btns)

        self.btn_volver.clicked.connect(self._on_volver)
        self.btn_guardar.clicked.connect(lambda: self._on_guardar(False))
        self.btn_guardar_ver.clicked.connect(lambda: self._on_guardar(True))

    # --- layout: lógica de ancho responsive con mínimo para Vehículo ---

    def _ajustar_ancho_detalle(self) -> None:
        """
        Reparte el ancho de la tabla:
        - Columnas 1..6 respetan un mínimo y se ajustan a contenido.
        - Columna 0 (Vehículo) tiene un mínimo y usa el espacio restante.
        """
        if not hasattr(self, "tbl_detalle") or self.tbl_detalle is None:
            return

        vp_width = self.tbl_detalle.viewport().width()
        if vp_width <= 0:
            return

        # mínimos por columna
        min_widths = {
            0: 260,  # Vehículo (mínimo visible)
            1: 90,   # Cant.
            2: 130,  # P. Unitario
            3: 90,   # IVA %
            4: 120,  # Neto
            5: 120,  # IVA
            6: 120,  # Total
        }

        # Ajustar 1..6 al contenido pero no menos del mínimo
        for col in range(1, 7):
            self.tbl_detalle.resizeColumnToContents(col)
            current = self.tbl_detalle.columnWidth(col)
            if current < min_widths[col]:
                self.tbl_detalle.setColumnWidth(col, min_widths[col])

        other_width = sum(self.tbl_detalle.columnWidth(c) for c in range(1, 7))

        # Vehículo = lo que sobra, pero nunca menos que su mínimo
        veh_min = min_widths[0]
        space_for_veh = vp_width - other_width

        if space_for_veh >= veh_min:
            veh_width = space_for_veh
        else:
            veh_width = veh_min  # esto puede pasarse del viewport => scroll horizontal

        self.tbl_detalle.setColumnWidth(0, veh_width)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._ajustar_ancho_detalle()

    def showEvent(self, event) -> None:
        """
        Asegura que al entrar por primera vez la tabla ya use
        todo el ancho disponible (después de que el layout se calcule).
        """
        super().showEvent(event)
        QTimer.singleShot(0, self._ajustar_ancho_detalle)

    # ---------------- Helpers modo NC ----------------

    def _es_nota_credito(self) -> bool:
        tipo = self.in_tipo.currentData()
        if not tipo:
            return False
        return str(tipo).upper().startswith("NC")

    def _actualizar_modo_nc(self) -> None:
        """
        Si el tipo es Nota de Crédito y hay cliente seleccionado:
        - ocultar sección de Detalle
        - mostrar sección de Comprobantes y cargar facturas del cliente
        En cualquier otro caso:
        - mostrar Detalle
        - ocultar Comprobantes
        """
        es_nc = self._es_nota_credito()
        tiene_cliente = self._selected_cliente is not None

        if es_nc and tiene_cliente:
            # Cargar facturas del cliente
            self._load_comprobantes_cliente()
            self.sec_detalle.setVisible(False)
            self.sec_comprobantes.setVisible(True)
        else:
            self.sec_detalle.setVisible(True)
            self.sec_comprobantes.setVisible(False)

    def _load_comprobantes_cliente(self) -> None:
        """
        Usa FacturasService.search para traer facturas del cliente
        (FA/FB/FC) ordenadas por número descendente y las carga en el combo.
        """
        self.cb_comprobante.blockSignals(True)
        self.cb_comprobante.clear()
        self._facturas_cliente_nc = []

        if not self._selected_cliente:
            self.cb_comprobante.blockSignals(False)
            return

        nro_doc = (self._selected_cliente.get("nro_doc") or "").strip()
        if not nro_doc:
            self.cb_comprobante.blockSignals(False)
            return

        # Filtramos por CUIT / documento del cliente
        filtros = {"cuit": nro_doc}
        try:
            rows, _total = self._svc_facturas.search(filtros, page=1, page_size=500)
        except Exception as ex:
            NotifyPopup(f"Error al cargar comprobantes del cliente: {ex}", "error", self).show_centered()
            self.cb_comprobante.blockSignals(False)
            return

        # Nos quedamos solo con FA/FB/FC (facturas, no NC/ND)
        rows_ok = [r for r in rows if str(r.get("tipo") or "").upper() in ("FA", "FB", "FC")]

        # Ordenar por número de mayor a menor
        def _key_num(r: Dict[str, Any]) -> int:
            try:
                return int(r.get("numero") or 0)
            except Exception:
                return 0

        rows_ok.sort(key=_key_num, reverse=True)

        self._facturas_cliente_nc = rows_ok

        for f in rows_ok:
            tipo = f.get("tipo") or ""
            pto = f.get("pto_vta") or f.get("punto_venta")
            nro = f.get("numero")
            fecha = f.get("fecha") or f.get("fecha_emision") or ""
            total = f.get("total") or 0.0
            try:
                ptostr = str(int(pto)).zfill(4) if pto is not None else "0000"
            except Exception:
                ptostr = str(pto)
            label = f"{tipo} {ptostr}-{nro}  ({fecha})  $ {_format_money(float(total))}"
            self.cb_comprobante.addItem(label, f.get("id"))

        if self.cb_comprobante.count() > 0:
            self.cb_comprobante.setCurrentIndex(0)
        else:
            self.cb_comprobante.setCurrentIndex(-1)

        self.cb_comprobante.blockSignals(False)

    # ---------------- Datos iniciales / cabecera ----------------

    def _load_tipos_comprobante(self) -> None:
        try:
            tipos = self._svc_facturas.get_tipos_comprobante()
        except Exception:
            tipos = []
        if not tipos:
            tipos = [
                {"codigo": "FA", "nombre": "Factura A"},
                {"codigo": "FB", "nombre": "Factura B"},
                {"codigo": "FC", "nombre": "Factura C"},
            ]
        self.in_tipo.blockSignals(True)
        self.in_tipo.clear()
        for t in tipos:
            self.in_tipo.addItem(t.get("nombre") or t.get("codigo"), t.get("codigo"))
        self.in_tipo.blockSignals(False)
        idx_fb = self.in_tipo.findData("FB")
        self.in_tipo.setCurrentIndex(idx_fb if idx_fb != -1 else 0)
        self._on_tipo_or_pto_changed()

    def _load_puntos_venta(self) -> None:
        """
        Carga los puntos de venta desde el servicio de facturas.
        Espera que get_puntos_venta() devuelva una lista de dicts con
        al menos la clave 'punto_venta'.
        """
        try:
            pvs = self._svc_facturas.get_puntos_venta()
        except Exception:
            pvs = []

        self.in_pto_vta.blockSignals(True)
        self.in_pto_vta.clear()

        for pv in pvs or []:
            nro = pv.get("punto_venta")
            if nro is None:
                continue
            try:
                nro_int = int(nro)
            except (TypeError, ValueError):
                continue
            # Se muestra con cero a la izquierda tipo "0002"
            label = str(nro_int).zfill(4)
            self.in_pto_vta.addItem(label, nro_int)

        self.in_pto_vta.blockSignals(False)

        if self.in_pto_vta.count() > 0:
            self.in_pto_vta.setCurrentIndex(0)

        self._on_tipo_or_pto_changed()
    def _load_formas_pago(self) -> None:
        """
        Carga las formas de pago desde BD.
        Requiere tabla forma_pago.
        """
        db = SessionLocal()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT id, nombre
                    FROM forma_pago
                    ORDER BY nombre
                    """
                )
            ).mappings().all()
        except Exception:
            rows = []
        finally:
            db.close()

        self.cb_forma_pago.blockSignals(True)
        self.cb_forma_pago.clear()
        for r in rows:
            self.cb_forma_pago.addItem(r["nombre"], r["id"])
        self.cb_forma_pago.blockSignals(False)

    def _on_forma_pago_changed(self) -> None:
        """
        Si la forma de pago es financiación (id = 3),
        mostramos anticipo y cuotas.
        """
        forma_pago_id = self.cb_forma_pago.currentData()

        if forma_pago_id == 3:  # Financiación
            self.in_anticipo.show() 
            self.lbl_interes.show() 
            self.lbl_anticipo.show() 
            self.lbl_cantidad_cuotas.show() 
            self.in_cantidad_cuotas.show()
            self.in_interes_pct.show()
        else:
            self.in_anticipo.hide()
            self.in_cantidad_cuotas.hide()
            self.in_anticipo.setText("")
            self.in_cantidad_cuotas.setText("")
            self.in_interes_pct.hide()
            self.in_interes_pct.setText("")
            self.lbl_interes.hide() 
            self.lbl_anticipo.hide() 
            self.lbl_cantidad_cuotas.hide() 

    def _load_condicion_iva_receptor(self) -> None:
        """
        Carga la lista de condiciones frente al IVA del receptor.
        Usa FacturasService.get_condiciones_iva_receptor().
        Cada item del combo guarda el ID (INT) en userData.
        """
        self.in_condicion_iva_receptor.blockSignals(True)
        self.in_condicion_iva_receptor.clear()

        conds: List[Dict[str, Any]] = []
        getter = getattr(self._svc_facturas, "get_condiciones_iva_receptor", None)
        if callable(getter):
            try:
                conds = getter() or []
            except Exception:
                conds = []

        # Cacheamos la lista para luego poder buscar por código (CF, RI, etc.)
        self._cond_iva_receptor_list = conds or []

        if not conds:
            # fallback simple (aunque con IDs fijos)
            conds = [
                {"id": 5, "codigo": "CF", "descripcion": "Consumidor Final"},
                {"id": 1, "codigo": "RI", "descripcion": "Responsable Inscripto"},
                {"id": 6, "codigo": "MT", "descripcion": "Monotributista"},
                {"id": 4, "codigo": "EX", "descripcion": "Exento"},
            ]
            self._cond_iva_receptor_list = conds

        idx_cf = -1
        for i, c in enumerate(conds):
            desc = (
                c.get("descripcion")
                or c.get("nombre")
                or c.get("codigo")
                or str(c.get("id", ""))
            )
            cid = c.get("id")
            try:
                cid_int = int(cid)
            except Exception:
                continue
            self.in_condicion_iva_receptor.addItem(desc, cid_int)
            if str(c.get("codigo") or "").strip().upper() == "CF":
                idx_cf = self.in_condicion_iva_receptor.count() - 1

        self.in_condicion_iva_receptor.blockSignals(False)
        # Por defecto: Consumidor Final si lo encontramos, si no el primero
        if idx_cf >= 0:
            self.in_condicion_iva_receptor.setCurrentIndex(idx_cf)
        elif self.in_condicion_iva_receptor.count() > 0:
            self.in_condicion_iva_receptor.setCurrentIndex(0)

    def _select_condicion_iva_por_codigo(self, codigo: str) -> None:
        """
        Selecciona en el combo la condición IVA cuyo 'codigo' matchee (CF, RI, etc.).
        No hace nada si no la encuentra.
        """
        if not codigo:
            return
        codigo_up = str(codigo).strip().upper()
        if not codigo_up:
            return

        target_id = None
        for c in self._cond_iva_receptor_list or []:
            cod = (c.get("codigo") or "").strip().upper()
            if cod == codigo_up:
                target_id = c.get("id")
                break

        if target_id is None:
            return

        try:
            target_id_int = int(target_id)
        except Exception:
            return

        idx = self.in_condicion_iva_receptor.findData(target_id_int)
        if idx >= 0:
            self.in_condicion_iva_receptor.setCurrentIndex(idx)

    def _on_tipo_or_pto_changed(self, *_args) -> None:
        """
        Actualiza el número sugerido usando FacturasService.sugerir_proximo_numero.
        Si por algún motivo falla, deja el placeholder.
        Además, actualiza el modo NC / Factura normal.
        """
        self._dirty = True
        tipo = self.in_tipo.currentData()
        pto = self.in_pto_vta.currentData()
        if not tipo or not pto:
            self.in_numero.clear()
            self.in_numero.setPlaceholderText("Se definirá al guardar")
            self._actualizar_modo_nc()
            return

        sugerir = getattr(self._svc_facturas, "sugerir_proximo_numero", None)
        if callable(sugerir):
            try:
                nro = sugerir(tipo, int(pto))
                # el número que ve el usuario coincide con lo que se mandará al service
                self.in_numero.setText(str(nro))
            except Exception:
                self.in_numero.clear()
                self.in_numero.setPlaceholderText("Se definirá al guardar")
        else:
            self.in_numero.clear()
            self.in_numero.setPlaceholderText("Se definirá al guardar")

        # Cambiar visibilidad de Detalle / Comprobantes según tipo
        self._actualizar_modo_nc()

    # ---------------- Cliente dinámico ----------------

    def _on_cliente_text_edited(self, _text: str) -> None:
        self._dirty = True
        self._selected_cliente = None
        self._clear_cliente_info()
        self._cliente_search_timer.start()
        self._actualizar_modo_nc()

    def _do_cliente_search(self) -> None:
        text = (self.cb_cliente.lineEdit().text() or "").strip()
        if len(text) < 4:
            self._cliente_results = []
            self.cb_cliente.blockSignals(True)
            self.cb_cliente.clear()
            self.cb_cliente.blockSignals(False)
            return

        filtros = {
            "nombre": text,
            "page": 1,
            "page_size": 20,
        }

        try:
            rows, _ = self._svc_clientes.search(filtros, page=1, page_size=20)
        except Exception as ex:
            NotifyPopup(f"Error al buscar clientes: {ex}", "error", self).show_centered()
            rows = []

        self._cliente_results = rows or []
        current_text = self.cb_cliente.lineEdit().text()

        self.cb_cliente.blockSignals(True)
        self.cb_cliente.clear()
        for c in self._cliente_results:
            self.cb_cliente.addItem(_cliente_label(c), c)
        self.cb_cliente.setCurrentIndex(-1)
        self.cb_cliente.blockSignals(False)

        self.cb_cliente.lineEdit().setText(current_text)

        if self.cb_cliente.count() > 0:
            self.cb_cliente.showPopup()

    def _on_cliente_selected(self, index: int) -> None:
        if index < 0:
            self._selected_cliente = None
            self._clear_cliente_info()
            self._actualizar_modo_nc()
            return
        data = self.cb_cliente.itemData(index)
        if not isinstance(data, dict):
            self._selected_cliente = None
            self._clear_cliente_info()
            self._actualizar_modo_nc()
            return
        self._set_selected_cliente(data)

    def _set_selected_cliente(self, data: Dict[str, Any]) -> None:
        self._dirty = True
        self._selected_cliente = data
        tipo_doc = data.get("tipo_doc") or ""
        nro_doc = data.get("nro_doc") or ""
        self.in_cliente_tipo_doc.setText(tipo_doc)
        self.in_cliente_nro_doc.setText(nro_doc)
        self.in_cliente_email.setText(data.get("email") or "")
        self.in_cliente_telefono.setText(data.get("telefono") or "")
        self.in_cliente_direccion.setText(data.get("direccion") or "")

        # YA NO tocamos la condición IVA automáticamente,
        # dejamos la que está seleccionada.
        # Solo actualizamos modo NC (para mostrar comprobantes)
        self._actualizar_modo_nc()

    def _clear_cliente_info(self) -> None:
        self.in_cliente_tipo_doc.clear()
        self.in_cliente_nro_doc.clear()
        self.in_cliente_email.clear()
        self.in_cliente_telefono.clear()
        self.in_cliente_direccion.clear()

    def _on_cliente_limpiar(self) -> None:
        self._dirty = True
        self._selected_cliente = None
        self._cliente_results = []
        self.cb_cliente.blockSignals(True)
        self.cb_cliente.clear()
        self.cb_cliente.blockSignals(False)
        self.cb_cliente.lineEdit().clear()
        self._clear_cliente_info()
        self._actualizar_modo_nc()

    # ---------------- Detalle ----------------

    def _add_detalle_row(self) -> None:
        row = self.tbl_detalle.rowCount()
        self.tbl_detalle.insertRow(row)

        selector = VehiculoSelectorCombo(self._svc_vehiculos, self)
        selector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        selector.vehiculo_selected.connect(
            lambda data, r=row: self._on_vehiculo_en_fila_seleccionado(r, data)
        )
        self.tbl_detalle.setCellWidget(row, 0, selector)

        selector.lineEdit().textChanged.connect(
            lambda text, r=row: self._on_vehiculo_text_changed_en_fila(r, text)
        )

        h = max(selector.sizeHint().height(), 32)
        self.tbl_detalle.setRowHeight(row, h + 4)

        in_cant = QLineEdit("1")
        in_cant.setAlignment(Qt.AlignRight)
        in_cant.editingFinished.connect(lambda r=row: self._on_detalle_valor_editado(r))
        self.tbl_detalle.setCellWidget(row, 1, in_cant)

        in_pu = QLineEdit("0,00")
        in_pu.setAlignment(Qt.AlignRight)
        in_pu.editingFinished.connect(lambda r=row: self._on_detalle_valor_editado(r))
        self.tbl_detalle.setCellWidget(row, 2, in_pu)

        in_iva = QLineEdit("21")
        in_iva.setAlignment(Qt.AlignRight)
        in_iva.editingFinished.connect(lambda r=row: self._on_detalle_valor_editado(r))
        self.tbl_detalle.setCellWidget(row, 3, in_iva)

        for col in (4, 5, 6):
            it = QTableWidgetItem("0,00")
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.tbl_detalle.setItem(row, col, it)

        self._dirty = True
        self._recalcular_fila(row)
        self._ajustar_ancho_detalle()

    def _remove_selected_row(self) -> None:
        row = self.tbl_detalle.currentRow()
        if row < 0:
            return
        self.tbl_detalle.removeRow(row)
        if self.tbl_detalle.rowCount() == 0:
            self._add_detalle_row()
        self._dirty = True
        self._recalcular_totales()
        self._ajustar_ancho_detalle()

    def _on_vehiculo_en_fila_seleccionado(self, row: int, vehiculo: Dict[str, Any]) -> None:
        if row < 0 or row >= self.tbl_detalle.rowCount():
            return
        pu_widget = self.tbl_detalle.cellWidget(row, 2)
        if isinstance(pu_widget, QLineEdit):
            actual = _parse_decimal(pu_widget.text())
            if actual == 0.0:
                precio = vehiculo.get("precio_lista") or vehiculo.get("precio") or 0
                pu_widget.setText(_format_money(float(precio)))
        self._dirty = True
        self._recalcular_fila(row)

    def _on_vehiculo_text_changed_en_fila(self, row: int, text: str) -> None:
        if row < 0 or row >= self.tbl_detalle.rowCount():
            return
        if text.strip():
            return
        self._dirty = True
        self._clear_detalle_row(row)

    def _on_detalle_valor_editado(self, row: int) -> None:
        if row < 0 or row >= self.tbl_detalle.rowCount():
            return

        # Normalizar formato de precio unitario con decimales siempre
        pu_w = self.tbl_detalle.cellWidget(row, 2)
        if isinstance(pu_w, QLineEdit):
            val = _parse_decimal(pu_w.text())
            pu_w.setText(_format_money(val))

        self._dirty = True
        self._recalcular_fila(row)

    def _recalcular_fila(self, row: int) -> None:
        cant_w = self.tbl_detalle.cellWidget(row, 1)
        pu_w = self.tbl_detalle.cellWidget(row, 2)
        iva_w = self.tbl_detalle.cellWidget(row, 3)

        cantidad = _parse_decimal(cant_w.text()) if isinstance(cant_w, QLineEdit) else 0.0
        precio_unit = _parse_decimal(pu_w.text()) if isinstance(pu_w, QLineEdit) else 0.0
        alic_iva = _parse_decimal(iva_w.text()) if isinstance(iva_w, QLineEdit) else 0.0

        neto = cantidad * precio_unit
        iva = neto * alic_iva / 100.0
        total = neto + iva

        for col, val in zip((4, 5, 6), (neto, iva, total)):
            item = self.tbl_detalle.item(row, col)
            if not item:
                item = QTableWidgetItem()
                self.tbl_detalle.setItem(row, col, item)
            item.setText(_format_money(val))

        self._recalcular_totales()

    def _recalcular_totales(self) -> None:
        subtotal = iva_total = total_total = 0.0
        for r in range(self.tbl_detalle.rowCount()):
            neto_item = self.tbl_detalle.item(r, 4)
            iva_item = self.tbl_detalle.item(r, 5)
            tot_item = self.tbl_detalle.item(r, 6)
            subtotal += _parse_decimal(neto_item.text() if neto_item else "0")
            iva_total += _parse_decimal(iva_item.text() if iva_item else "0")
            total_total += _parse_decimal(tot_item.text() if tot_item else "0")
        self.in_subtotal.setText(_format_money(subtotal))
        self.in_iva_total.setText(_format_money(iva_total))
        self.in_total.setText(_format_money(total_total))

    def _clear_detalle_row(self, row: int) -> None:
        if row < 0 or row >= self.tbl_detalle.rowCount():
            return
        defaults = {1: "1", 2: "0,00", 3: "21"}
        for col, val in defaults.items():
            w = self.tbl_detalle.cellWidget(row, col)
            if isinstance(w, QLineEdit):
                w.setText(val)
        for col in (4, 5, 6):
            item = self.tbl_detalle.item(row, col)
            if not item:
                item = QTableWidgetItem()
                self.tbl_detalle.setItem(row, col, item)
            item.setText("0,00")
        self._recalcular_totales()

    # ---------------- Observaciones ----------------

    def _on_observaciones_changed(self) -> None:
        self._dirty = True

    # ---------------- Guardar ----------------

    def _collect_data(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        tipo = self.in_tipo.currentData()
        pto_vta = self.in_pto_vta.currentData()
        numero = self.in_numero.text().strip() or None
        fecha_emision = self.in_fecha_emision.text().strip()
        moneda = self.in_moneda.text().strip() or "ARS"
        cotizacion = 1.0  # fijo (ya no se muestra campo)
        total = _parse_decimal(self.in_total.text())
        cliente_id = self._selected_cliente.get("id") if self._selected_cliente else None

        condicion_id_raw = self.in_condicion_iva_receptor.currentData()
        try:
            condicion_iva_receptor_id = int(condicion_id_raw) if condicion_id_raw is not None else None
        except Exception:
            condicion_iva_receptor_id = None

        observaciones_text = (self.in_observaciones.toPlainText() or "").strip()

        cabecera = {
            "tipo": tipo,
            "pto_vta": int(pto_vta) if pto_vta is not None else None,
            # si por alguna razón no hay número (falló sugerencia),
            # lo dejamos en None para que el service calcule el próximo
            "numero": int(numero) if numero else None,
            "fecha_emision": fecha_emision,
            "moneda": moneda,
            "cotizacion": cotizacion,
            "cliente_id": cliente_id,
            "total": total,
            # condición frente al IVA del receptor (ID numérico)
            "condicion_iva_receptor_id": condicion_iva_receptor_id,
            # observaciones
            "observaciones": observaciones_text or None,
            "precio_real": _parse_decimal(self.in_precio_real.text()),
            "forma_pago_id": self.cb_forma_pago.currentData(),
            "anticipo": _parse_decimal(self.in_anticipo.text()),
            "cantidad_cuotas": int(self.in_cantidad_cuotas.text() or 0),
            "interes_pct": float(self.in_interes_pct.text() or 0.0),

        }

        items: List[Dict[str, Any]] = []
        for r in range(self.tbl_detalle.rowCount()):
            selector = self.tbl_detalle.cellWidget(r, 0)
            if not isinstance(selector, VehiculoSelectorCombo):
                continue
            veh = selector.selected_vehiculo
            if not veh:
                continue

            cant_w = self.tbl_detalle.cellWidget(r, 1)
            pu_w = self.tbl_detalle.cellWidget(r, 2)
            iva_w = self.tbl_detalle.cellWidget(r, 3)
            neto_it = self.tbl_detalle.item(r, 4)
            iva_it = self.tbl_detalle.item(r, 5)
            tot_it = self.tbl_detalle.item(r, 6)

            cantidad = _parse_decimal(cant_w.text()) if isinstance(cant_w, QLineEdit) else 0.0
            precio_unit = _parse_decimal(pu_w.text()) if isinstance(pu_w, QLineEdit) else 0.0
            alic_iva = _parse_decimal(iva_w.text()) if isinstance(iva_w, QLineEdit) else 0.0
            importe_neto = _parse_decimal(neto_it.text() if neto_it else "0")
            importe_iva = _parse_decimal(iva_it.text() if iva_it else "0")
            importe_total = _parse_decimal(tot_it.text() if tot_it else "0")

            desc = _vehiculo_label(veh)

            items.append(
                {
                    "item_tipo": "VEHICULO",
                    "vehiculo_id": veh.get("id"),
                    "descripcion": desc,
                    "cantidad": cantidad,
                    "precio_unitario": precio_unit,
                    "alicuota_iva": alic_iva,
                    "importe_neto": importe_neto,
                    "importe_iva": importe_iva,
                    "importe_total": importe_total,
                }
            )

        return cabecera, items

    def _validate(self, cabecera: Dict[str, Any], items: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        errs: List[str] = []
        if not cabecera.get("tipo"):
            errs.append("Seleccioná el tipo de comprobante.")
        if not cabecera.get("pto_vta"):
            errs.append("Seleccioná el punto de venta.")
        if not cabecera.get("fecha_emision"):
            errs.append("Ingresá la fecha de emisión.")
        if not cabecera.get("cliente_id"):
            errs.append("Seleccioná un cliente.")
        if not cabecera.get("condicion_iva_receptor_id"):
            errs.append("Seleccioná la condición frente al IVA del receptor.")
        if not self._es_nota_credito():
            # Para facturas normales, se exige detalle
            if not items:
                errs.append("Agregá al menos un vehículo en el detalle.")
            for it in items:
                if not it.get("vehiculo_id"):
                    errs.append("Hay filas de detalle sin vehículo seleccionado.")
                    break
        else:
            # Para NC, se valida aparte: comprobante seleccionado
            comp_id = self.cb_comprobante.currentData()
            if comp_id in (None, "", 0, "0"):
                errs.append("Seleccioná el comprobante a asociar a la Nota de Crédito.")
        return (len(errs) == 0), errs

    def _on_guardar(self, abrir_detalle: bool) -> None:
        """
        Guarda:
        - Si es factura (FA/FB/FC, etc.) → alta normal + ARCA.
        - Si es Nota de Crédito (NCA/NCB/NCC) → genera NC a partir del comprobante seleccionado.
        """
        if self._es_nota_credito():
            self._on_guardar_nota_credito(abrir_detalle)
            return

        # ----- Flujo normal de factura -----
        cabecera, items = self._collect_data()
        ok, errs = self._validate(cabecera, items)
        if not ok:
            msg = "\n".join(f"• {e}" for e in errs)
            NotifyPopup(msg, "warning", self).show_centered()
            return

        create_full = getattr(self._svc_facturas, "create_factura_completa", None)
        if not callable(create_full):
            popUp.info(
                self,
                "Pendiente",
                (
                    "La pantalla de alta de factura ya está lista, pero todavía no está "
                    "implementado el método 'create_factura_completa' en FacturasService."
                ),
            )
            return

        # 1) Guardar factura en BD
        try:
            new_id = create_full(cabecera, items)
        except Exception as ex:
            NotifyPopup(f"Error al guardar la factura: {ex}", "error", self).show_centered()
            return

        self._dirty = False
        NotifyPopup("Factura guardada correctamente.", "success", self).show_centered()

        # 2) Autorizar en ARCA (si existe el método en el service)
        autorizar = getattr(self._svc_facturas, "autorizar_en_arca", None)
        if callable(autorizar) and isinstance(new_id, int):
            try:
                result = autorizar(new_id)
                from pprint import pformat

                # Popup técnico (te sirve mientras estás en homologación)
                NotifyPopup(
                    "Resultado de ARCA:\n" + pformat(result),
                    "info",
                    self,
                ).show_centered()

                msg = result.get("mensaje") if isinstance(result, dict) else ""
                estado_id = result.get("estado_id") if isinstance(result, dict) else None

                if isinstance(result, dict) and result.get("aprobada"):
                    # Autorizada ok
                    NotifyPopup(
                        "Factura autorizada correctamente en ARCA.\n" + msg,
                        "success",
                        self,
                    ).show_centered()
                elif isinstance(result, dict) and result.get("rechazada"):
                    # Rechazada por AFIP/ARCA
                    NotifyPopup(
                        "Factura rechazada por ARCA.\n" + msg,
                        "error",
                        self,
                    ).show_centered()
                else:
                    # Ni aprobada ni rechazada → error de comunicación o quedó en borrador
                    extra = ""
                    try:
                        if estado_id in (
                            self._svc_facturas.ESTADO_BORRADOR,
                            self._svc_facturas.ESTADO_ERROR_COMUNICACION,
                        ):
                            extra = (
                                "\n\nLa factura quedó guardada en el sistema. "
                                "Podés reintentar la autorización desde la pantalla "
                                "de facturas usando 'Sincronizar con ARCA'."
                            )
                    except Exception:
                        pass

                    NotifyPopup(
                        "No se pudo confirmar la autorización en ARCA.\n"
                        + (msg or "")
                        + extra,
                        "warning",
                        self,
                    ).show_centered()
            except Exception as ex:
                # Si algo explota acá, la factura igual ya se guardó como borrador.
                NotifyPopup(
                    "La factura se guardó localmente, pero se produjo un error al "
                    f"intentar autorizar en ARCA:\n{ex}\n\n"
                    "Podés reintentar luego desde la pantalla de facturas "
                    "con el botón 'Sincronizar con ARCA'.",
                    "error",
                    self,
                ).show_centered()
        else:
            # Si por alguna razón el método no está, solo informamos guardar local.
            NotifyPopup(
                "La factura se guardó localmente, pero la integración con ARCA no está disponible.",
                "warning",
                self,
            ).show_centered()

        # 3) Navegación según el botón
        if abrir_detalle and isinstance(new_id, int):
            self.go_to_detalle.emit(new_id)
        else:
            self.go_back.emit()

    def _on_guardar_nota_credito(self, abrir_detalle: bool) -> None:
        """
        Flujo especial cuando el tipo es Nota de Crédito:
        - Requiere cliente + comprobante asociado.
        - Llama a FacturasService.generar_nota_credito(id_factura_seleccionada).
        """
        # Validación básica
        if not self._selected_cliente:
            NotifyPopup("Seleccioná un cliente para la Nota de Crédito.", "warning", self).show_centered()
            return

        comp_id = self.cb_comprobante.currentData()
        if comp_id in (None, "", 0, "0"):
            NotifyPopup("Seleccioná el comprobante a asociar a la Nota de Crédito.", "warning", self).show_centered()
            return

        try:
            comp_id_int = int(comp_id)
        except Exception:
            NotifyPopup("El comprobante seleccionado no es válido.", "error", self).show_centered()
            return

        generar_nc = getattr(self._svc_facturas, "generar_nota_credito", None)
        if not callable(generar_nc):
            popUp.info(
                self,
                "Pendiente",
                (
                    "La generación de Notas de Crédito no está implementada "
                    "en FacturasService (método 'generar_nota_credito')."
                ),
            )
            return

        try:
            res = generar_nc(comp_id_int)
        except Exception as ex:
            NotifyPopup(f"Error al generar la Nota de Crédito: {ex}", "error", self).show_centered()
            return

        from pprint import pformat
        NotifyPopup("Resultado de generación de NC:\n" + pformat(res), "info", self).show_centered()

        msg = res.get("mensaje") if isinstance(res, dict) else ""
        if res.get("aprobada"):
            self._dirty = False
            NotifyPopup(
                "Nota de Crédito generada y autorizada correctamente en ARCA.\n" + (msg or ""),
                "success",
                self,
            ).show_centered()
        elif res.get("rechazada"):
            NotifyPopup(
                "Nota de Crédito rechazada por ARCA.\n" + (msg or ""),
                "error",
                self,
            ).show_centered()
        else:
            NotifyPopup(
                "No se pudo confirmar la autorización de la Nota de Crédito en ARCA.\n" + (msg or ""),
                "warning",
                self,
            ).show_centered()

        nc_id = res.get("nc_id") if isinstance(res, dict) else None

        if abrir_detalle and isinstance(nc_id, int):
            self.go_to_detalle.emit(nc_id)
        else:
            self.go_back.emit()

    # ---------------- Volver ----------------

    def _on_volver(self) -> None:
        """
        Maneja el botón Volver.
        - Si hay cambios, pregunta con ConfirmDialog.
        - Si el usuario acepta, resetea _dirty y navega hacia atrás.
        """
        if self._dirty and self._hay_info_cargada():
            if not ConfirmDialog.ask_discard(self):
                return

        # Si llegamos acá, no hay cambios o el usuario aceptó descartar.
        self._dirty = False

        # Señal para quien esté escuchando (MainWindow normalmente).
        self.go_back.emit()

        # Fallback: por si nadie está conectado al signal.
        mw = getattr(self, "_main_window", None) or self.window()
        if isinstance(mw, QMainWindow) and hasattr(mw, "navigate_back"):
            try:
                mw.navigate_back()
            except Exception:
                pass

    def _hay_info_cargada(self) -> bool:
        # Cabecera
        if self.in_pto_vta.currentIndex() >= 0:
            return True
        if self.in_fecha_emision.text().strip():
            return True
        if self.in_condicion_iva_receptor.currentIndex() >= 0:
            return True

        # Observaciones
        if self.in_observaciones.toPlainText().strip():
            return True

        # Cliente
        if self.cb_cliente.lineEdit().text().strip():
            return True
        if self._selected_cliente is not None:
            return True

        # Si estamos en modo NC y hay comprobante seleccionado
        if self._es_nota_credito() and self.cb_comprobante.currentIndex() >= 0:
            return True

        # Detalle
        for r in range(self.tbl_detalle.rowCount()):
            selector = self.tbl_detalle.cellWidget(r, 0)
            if isinstance(selector, VehiculoSelectorCombo) and selector.selected_vehiculo:
                return True

            cant_w = self.tbl_detalle.cellWidget(r, 1)
            pu_w = self.tbl_detalle.cellWidget(r, 2)
            iva_w = self.tbl_detalle.cellWidget(r, 3)

            cant = _parse_decimal(cant_w.text()) if isinstance(cant_w, QLineEdit) else 0.0
            pu = _parse_decimal(pu_w.text()) if isinstance(pu_w, QLineEdit) else 0.0
            iva = _parse_decimal(iva_w.text()) if isinstance(iva_w, QLineEdit) else 0.0

            if cant != 1.0 or pu != 0.0 or iva != 21.0:
                return True

        return False
