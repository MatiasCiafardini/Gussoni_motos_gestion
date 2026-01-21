from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QDate, Signal, QTimer, QPoint, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QFrame, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QMainWindow, QTextEdit,
    QDialog, QScrollArea, QToolButton, QApplication, QStyle,
    QComboBox, QListView
)
from PySide6.QtGui import QIcon, QDesktopServices
import app.ui.app_message as popUp
from sqlalchemy import text

from app.data.database import SessionLocal
from app.services.facturas_service import FacturasService
from app.services.clientes_service import ClientesService
from app.services.vehiculos_service import VehiculosService
from app.services.comprobantes_service import ComprobantesService
from app.ui.notify import NotifyPopup
from app.ui.widgets.confirm_dialog import ConfirmDialog
from PySide6.QtGui import QColor

# -------------------- Ventana popup movible --------------------
from datetime import date

CUOTA_COLORS = {
    "PENDIENTE": "#f5f6f7",   # gris muy suave
    "PARCIAL":   "#fff7e6",   # amarillo pastel
    "PAGADA":    "#eaf7ee",   # verde pastel
    "VENCIDA":   "#fdecec",   # rojo pastel
}

class MovableDialog(QDialog):
    """
    QDialog sin marco y arrastrable desde cualquier parte.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._drag_offset: Optional[QPoint] = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.LeftButton) and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


# -------------------- Helpers comunes --------------------


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
    lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    lbl.setStyleSheet(
        """
        font-weight: 600;
        padding: 2px 0;
        """
    )


# -------- Combo dinámico de vehículos (idéntico al de agregar) --------


class VehiculoSelectorCombo(QComboBox):
    """
    QComboBox editable que busca vehículos dinámicamente.
    """
    vehiculo_selected = Signal(dict)

    def __init__(self, vehiculos_service: VehiculosService, parent: Optional[QWidget] = None) -> None:
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

    def _on_text_edited(self, _text: str) -> None:
        self._selected = None
        self._timer.start()

    def _do_search(self) -> None:
        textq = (self.lineEdit().text() or "").strip()
        if len(textq) < 4:
            self._results = []
            self.blockSignals(True)
            self.clear()
            self.blockSignals(False)
            return

        filtros = {"q": textq, "page": 1, "page_size": 20}
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


# -------------------- Pantalla principal --------------------


class FacturasConsultarPage(QWidget):
    """
    Pantalla de consulta de factura:
    - Modo solo lectura por defecto.
    - Botón "Modificar" para entrar a modo edición (si está permitido).
    - En modo edición se pueden editar cabecera + cliente + detalle + observaciones.
    - Botón "Generar nota de crédito" (solo facturas autorizadas no-NC).
    - Popup lindo para copiar datos rápido.

    REGLAS UI (implementadas):
    - Al entrar (modo consulta): NO se muestran botones de edición (guardar/cancelar/limpiar/agregar/quitar).
    - Esos botones aparecen SOLO al entrar a modo edición.
    - "Modificar" NO se muestra si la factura está AUTORIZADA (y tampoco si está ANULADA/BAJA/ANULADA POR NC).
    """

    go_back = Signal()

    COL_VEHICULO = 0
    COL_CANT = 1
    COL_PUNIT = 2
    COL_IVA_PCT = 3
    COL_NETO = 4
    COL_IVA = 5
    COL_TOTAL = 6

    def __init__(
        self,
        factura_id: int,
        parent: Optional[QWidget] = None,
        main_window: Optional[QMainWindow] = None,
        return_to: Optional[str] = None,
        cliente_id: Optional[int] = None,
    ) -> None:

        super().__init__(parent)
        self.setObjectName("FacturasConsultarPage")

        self._factura_id = int(factura_id)
        self._svc_facturas = FacturasService()
        self._svc_clientes = ClientesService()
        self._svc_vehiculos = VehiculosService()
        self._svc_comprobantes = ComprobantesService()
        self._main_window = main_window
        self._return_to = return_to
        self._cliente_id = cliente_id

        self._tipo: Optional[str] = None
        self._estado_id: Optional[int] = None
        self._factura: Optional[Dict[str, Any]] = None  # cache cabecera

        print("hola")
        # baja/anulada (para bloquear acciones)
        self._baja: bool = False
        self._can_edit_current: bool = False

        self._cond_iva_by_id: Dict[int, Dict[str, Any]] = {}
        self._cond_iva_by_codigo: Dict[str, Dict[str, Any]] = {}

        # cliente dinámico
        self._selected_cliente: Optional[Dict[str, Any]] = None
        self._cliente_results: List[Dict[str, Any]] = []
        self._cliente_search_timer = QTimer(self)
        self._cliente_search_timer.setSingleShot(True)
        self._cliente_search_timer.setInterval(150)
        self._cliente_search_timer.timeout.connect(self._do_cliente_search)

        # estado de edición
        self._edit_mode: bool = False
        self._snapshot_cabecera: Optional[Dict[str, Any]] = None

        self._build_ui()
        self._load_tipos_comprobante()
        self._load_puntos_venta()
        self._load_condiciones_iva()  # carga combo de cond IVA y cache
        self._load_data()

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
                # ===== Scroll principal =====
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        root_layout.addWidget(scroll)

        # Contenedor real del contenido
        container = QWidget()
        scroll.setWidget(container)

        main = QVBoxLayout(container)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(6)

        title = QLabel("Consulta de factura")
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

        for col, stretch in enumerate((1, 3, 1, 3, 1, 3)):
            grid1.setColumnStretch(col, stretch)

        # Combos como en agregar
        self.in_tipo = QComboBox()
        _setup_combo(self.in_tipo)

        self.in_pto_vta = QComboBox()
        _setup_combo(self.in_pto_vta)

        self.in_numero = QLineEdit()
        self.in_fecha_emision = QLineEdit()
        self.in_moneda = QLineEdit()

        self.in_condicion_iva_receptor = QComboBox()
        _setup_combo(self.in_condicion_iva_receptor)

        self.in_estado = QLineEdit()
        self._make_readonly(self.in_estado)
        self.in_cae = QLineEdit()
        self._make_readonly(self.in_cae)
        self.in_cae_vto = QLineEdit()
        self._make_readonly(self.in_cae_vto)

        # Observaciones
        self.in_observaciones = QTextEdit()
        self.in_observaciones.setReadOnly(True)
        self.in_observaciones.setFixedHeight(70)
        self.in_observaciones.setObjectName("TextInput")

        row = 0
        grid1.addWidget(QLabel("Tipo"), row, 0)
        grid1.addWidget(self.in_tipo, row, 1)
        grid1.addWidget(QLabel("Pto Vta"), row, 2)
        grid1.addWidget(self.in_pto_vta, row, 3)
        grid1.addWidget(QLabel("Número"), row, 4)
        grid1.addWidget(self.in_numero, row, 5)

        row += 1
        grid1.addWidget(QLabel("Fecha emisión"), row, 0)
        grid1.addWidget(self.in_fecha_emision, row, 1)
        grid1.addWidget(QLabel("Moneda"), row, 2)
        grid1.addWidget(self.in_moneda, row, 3)

        row += 1
        grid1.addWidget(QLabel("Condición IVA receptor"), row, 0)
        grid1.addWidget(self.in_condicion_iva_receptor, row, 1, 1, 5)

        row += 1
        grid1.addWidget(QLabel("Estado"), row, 0)
        grid1.addWidget(self.in_estado, row, 1)
        grid1.addWidget(QLabel("CAE"), row, 2)
        grid1.addWidget(self.in_cae, row, 3)
        grid1.addWidget(QLabel("Vto CAE"), row, 4)
        grid1.addWidget(self.in_cae_vto, row, 5)

        row += 1
        grid1.addWidget(QLabel("Observaciones"), row, 0)
        grid1.addWidget(self.in_observaciones, row, 1, 1, 5)

        row += 1
        self.btn_ver_info = QPushButton("Ver info / copiar")
        grid1.addWidget(QWidget(), row, 0)
        grid1.addWidget(self.btn_ver_info, row, 1, 1, 5, alignment=Qt.AlignRight)
        self.btn_ver_info.clicked.connect(self._on_ver_info)

        main.addWidget(sec1)

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

        self.in_cliente_tipo_doc = QLineEdit()
        self._make_readonly(self.in_cliente_tipo_doc)
        self.in_cliente_nro_doc = QLineEdit()
        self._make_readonly(self.in_cliente_nro_doc)

        row += 1
        grid2.addWidget(QLabel("Tipo doc."), row, 0)
        grid2.addWidget(self.in_cliente_tipo_doc, row, 1)
        grid2.addWidget(QLabel("Nro doc."), row, 2)
        grid2.addWidget(self.in_cliente_nro_doc, row, 3, 1, 3)

        self.in_cliente_email = QLineEdit()
        self._make_readonly(self.in_cliente_email)
        self.in_cliente_telefono = QLineEdit()
        self._make_readonly(self.in_cliente_telefono)
        self.in_cliente_direccion = QLineEdit()
        self._make_readonly(self.in_cliente_direccion)

        row += 1
        grid2.addWidget(QLabel("Email"), row, 0)
        grid2.addWidget(self.in_cliente_email, row, 1)
        grid2.addWidget(QLabel("Teléfono"), row, 2)
        grid2.addWidget(self.in_cliente_telefono, row, 3)
        grid2.addWidget(QLabel("Dirección"), row, 4)
        grid2.addWidget(self.in_cliente_direccion, row, 5)

        main.addWidget(sec2)

                # --- Sección 2B: Datos de la venta ---
        secv = QFrame(self)
        secv.setObjectName("Panel")
        secv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        secv_l = QVBoxLayout(secv)
        secv_l.setContentsMargins(10, 10, 10, 10)
        secv_l.setSpacing(8)

        lblv = QLabel("Datos de la venta")
        _style_section_label(lblv)
        secv_l.addWidget(lblv)

        gridv = QGridLayout()
        gridv.setHorizontalSpacing(8)
        gridv.setVerticalSpacing(6)
        secv_l.addLayout(gridv)

        for col, stretch in enumerate((1, 3, 1, 3, 1, 3)):
            gridv.setColumnStretch(col, stretch)

        self.in_precio_real = QLineEdit()
        self.in_forma_pago = QLineEdit()
        self.in_anticipo = QLineEdit()
        self.in_interes = QLineEdit()
        self.in_cant_cuotas = QLineEdit()

        for w in (
            self.in_precio_real,
            self.in_forma_pago,
            self.in_anticipo,
            self.in_interes,
            self.in_cant_cuotas,
        ):
            self._make_readonly(w, align_right=True)

        r = 0
        gridv.addWidget(QLabel("Precio real"), r, 0)
        gridv.addWidget(self.in_precio_real, r, 1)
        gridv.addWidget(QLabel("Forma de pago"), r, 2)
        gridv.addWidget(self.in_forma_pago, r, 3)

        r += 1
        gridv.addWidget(QLabel("Anticipo"), r, 0)
        gridv.addWidget(self.in_anticipo, r, 1)
        gridv.addWidget(QLabel("Interés (%)"), r, 2)
        gridv.addWidget(self.in_interes, r, 3)
        gridv.addWidget(QLabel("Cuotas"), r, 4)
        gridv.addWidget(self.in_cant_cuotas, r, 5)

        main.addWidget(secv)
        self.sec_venta = secv


        le_cli.textEdited.connect(self._on_cliente_text_edited)
        self.cb_cliente.currentIndexChanged.connect(self._on_cliente_selected)
        self.btn_cliente_limpiar.clicked.connect(self._on_cliente_limpiar)

        # --- Sección 3: Detalle ---
        sec3 = QFrame(self)
        sec3.setObjectName("Panel")
        sec3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sec_detalle = sec3

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
        for col in range(7):
            header.setSectionResizeMode(col, QHeaderView.Interactive)

        self.tbl_detalle.setColumnWidth(self.COL_VEHICULO, 320)
        self.tbl_detalle.setColumnWidth(self.COL_CANT, 100)
        self.tbl_detalle.setColumnWidth(self.COL_PUNIT, 140)
        self.tbl_detalle.setColumnWidth(self.COL_IVA_PCT, 90)
        self.tbl_detalle.setColumnWidth(self.COL_NETO, 130)
        self.tbl_detalle.setColumnWidth(self.COL_IVA, 130)
        self.tbl_detalle.setColumnWidth(self.COL_TOTAL, 130)

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

        self._detalle_actions_wrap = QWidget()
        self._detalle_actions_wrap.setLayout(row_btns)
        sec3_l.addWidget(self._detalle_actions_wrap)

        self.btn_add_row.clicked.connect(self._add_detalle_row)
        self.btn_del_row.clicked.connect(self._remove_selected_row)

        tot_layout = QGridLayout()
        tot_layout.setContentsMargins(0, 0, 0, 0)
        tot_layout.setHorizontalSpacing(8)
        tot_layout.setVerticalSpacing(4)
        tot_layout.setColumnStretch(0, 1)
        tot_layout.setColumnStretch(1, 3)

        self.in_subtotal = QLineEdit("0,00")
        self._make_readonly(self.in_subtotal, align_right=True)
        self.in_iva_total = QLineEdit("0,00")
        self._make_readonly(self.in_iva_total, align_right=True)
        self.in_total = QLineEdit("0,00")
        self._make_readonly(self.in_total, align_right=True)

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

                # --- Sección 4: Cuotas (solo lectura) ---
        secc = QFrame(self)
        secc.setObjectName("Panel")
        secc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        secc_l = QVBoxLayout(secc)
        secc_l.setContentsMargins(10, 10, 10, 10)
        secc_l.setSpacing(8)

        lblc = QLabel("Cuotas de la financiación")
        _style_section_label(lblc)
        secc_l.addWidget(lblc)

        self.tbl_cuotas = QTableWidget(0, 5, self)
        self.tbl_cuotas.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_cuotas.setSelectionMode(QAbstractItemView.NoSelection)
        self.tbl_cuotas.verticalHeader().setVisible(False)
        self.tbl_cuotas.setAlternatingRowColors(True)
        self.tbl_cuotas.setHorizontalHeaderLabels(
            ["N°", "Vencimiento", "Monto", "Pagado", "Estado"]
        )
        self.tbl_cuotas.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tbl_cuotas.verticalScrollBar().setSingleStep(12)

        self._lock_scroll_inside_table(self.tbl_cuotas)
        header = self.tbl_cuotas.horizontalHeader()
        for c in range(5):
            header.setSectionResizeMode(c, QHeaderView.Stretch)

        secc_l.addWidget(self.tbl_cuotas)
        main.addWidget(secc)
        self.sec_cuotas = secc


        # --- Botones pie ---
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 8, 0, 0)
        btns.setSpacing(8)

        self.btn_volver = QPushButton("Volver")
        self.btn_modificar = QPushButton("Modificar")
        self.btn_guardar = QPushButton("Guardar cambios")
        self.btn_cancelar_edicion = QPushButton("Cancelar edición")
        self.btn_pdf = QPushButton("Comprobante PDF")
        self.btn_nc = QPushButton("Generar nota de crédito")

        self.btn_nc.setObjectName("BtnPrimary")
        self.btn_guardar.setObjectName("BtnPrimary")
        self.btn_pdf.setObjectName("BtnPrimary")

        btns.addStretch(1)
        btns.addWidget(self.btn_volver)
        btns.addWidget(self.btn_modificar)
        btns.addWidget(self.btn_guardar)
        btns.addWidget(self.btn_cancelar_edicion)
        btns.addWidget(self.btn_pdf)
        btns.addWidget(self.btn_nc)
        btns.addStretch(1)

        main.addLayout(btns)

        self.btn_volver.clicked.connect(self._on_volver)
        self.btn_pdf.clicked.connect(self._on_comprobante_pdf)
        self.btn_nc.clicked.connect(self._on_generar_nc)
        self.btn_modificar.clicked.connect(self._on_modificar)
        self.btn_guardar.clicked.connect(self._on_guardar_cambios)
        self.btn_cancelar_edicion.clicked.connect(self._on_cancelar_edicion)
        container.setMinimumWidth(self.width())

        self._set_edit_mode(False)

    def _resolve_estado_cuota(
        self,
        estado_db: str,
        vencimiento,
        monto: float,
        pagado: float,
    ) -> str:
        if estado_db == "PAGADA":
            return "PAGADA"

        if pagado > 0 and pagado < monto:
            return "PARCIAL"

        if vencimiento and vencimiento < date.today():
            return "VENCIDA"

        return "PENDIENTE"

    def _apply_cuota_row_style(self, row: int, estado: str):
        if not estado:
            return

        color = CUOTA_COLORS.get(estado.upper())
        if not color:
            return

        for col in range(self.tbl_cuotas.columnCount()):
            item = self.tbl_cuotas.item(row, col)
            if item:
                item.setBackground(QColor(color))
    def _lock_scroll_inside_table(self, table: QTableWidget) -> None:
        """
        Evita que el scroll de la tabla se propague al ScrollArea padre
        cuando se llega al límite.
        """
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.Wheel:
            # Si el evento viene de la tabla de cuotas
            if obj is self.tbl_cuotas.viewport():
                bar = self.tbl_cuotas.verticalScrollBar()
                delta = event.angleDelta().y()

                # Scroll hacia arriba
                if delta > 0 and bar.value() == bar.minimum():
                    return True  # 🚫 bloquea propagación

                # Scroll hacia abajo
                if delta < 0 and bar.value() == bar.maximum():
                    return True  # 🚫 bloquea propagación

                return False  # ✅ la tabla maneja el scroll

        return super().eventFilter(obj, event)

    def _on_comprobante_pdf(self) -> None:
        try:
            self.btn_pdf.setEnabled(False)
            old_cursor = self.cursor()
            self.setCursor(Qt.WaitCursor)
            QApplication.processEvents()

            path = self._svc_comprobantes.generar_pdf(self._factura_id)

            self.setCursor(old_cursor)
            self.btn_pdf.setEnabled(True)

            ok = QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            if not ok:
                NotifyPopup(
                    f"Se generó el PDF pero no se pudo abrir automáticamente:\n{path}",
                    "warning",
                    self,
                ).show_centered()
        except Exception as ex:
            try:
                self.setCursor(Qt.ArrowCursor)
            except Exception:
                pass
            try:
                self.btn_pdf.setEnabled(True)
            except Exception:
                pass
            NotifyPopup(
                f"Error al generar el comprobante PDF:\n{ex}",
                "error",
                self,
            ).show_centered()

    def _make_readonly(self, le: QLineEdit, *, align_right: bool = False) -> None:
        le.setReadOnly(True)
        if align_right:
            le.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def _ajustar_ancho_detalle(self) -> None:
        if not hasattr(self, "tbl_detalle") or self.tbl_detalle is None:
            return
        vp_width = self.tbl_detalle.viewport().width()
        if vp_width <= 0:
            return

        min_widths = {
            self.COL_VEHICULO: 260,
            self.COL_CANT: 90,
            self.COL_PUNIT: 130,
            self.COL_IVA_PCT: 90,
            self.COL_NETO: 120,
            self.COL_IVA: 120,
            self.COL_TOTAL: 120,
        }

        for col in range(1, 7):
            self.tbl_detalle.resizeColumnToContents(col)
            current = self.tbl_detalle.columnWidth(col)
            if current < min_widths[col]:
                self.tbl_detalle.setColumnWidth(col, min_widths[col])

        other_width = sum(self.tbl_detalle.columnWidth(c) for c in range(1, 7))
        veh_min = min_widths[self.COL_VEHICULO]
        space_for_veh = vp_width - other_width
        veh_width = space_for_veh if space_for_veh >= veh_min else veh_min
        self.tbl_detalle.setColumnWidth(self.COL_VEHICULO, veh_width)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._ajustar_ancho_detalle()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._ajustar_ancho_detalle)

    # ---------------- Condiciones IVA / combos cabecera ----------------

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

    def _load_puntos_venta(self) -> None:
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
            label = str(nro_int).zfill(4)
            self.in_pto_vta.addItem(label, nro_int)

        self.in_pto_vta.blockSignals(False)

    def _load_condiciones_iva(self) -> None:
        try:
            conds = self._svc_facturas.get_condiciones_iva_receptor() or []
        except Exception:
            conds = []

        self._cond_iva_by_id.clear()
        self._cond_iva_by_codigo.clear()
        self.in_condicion_iva_receptor.blockSignals(True)
        self.in_condicion_iva_receptor.clear()

        if not conds:
            conds = [
                {"id": 5, "codigo": "CF", "descripcion": "Consumidor Final"},
                {"id": 1, "codigo": "RI", "descripcion": "Responsable Inscripto"},
                {"id": 6, "codigo": "MT", "descripcion": "Monotributista"},
                {"id": 4, "codigo": "EX", "descripcion": "Exento"},
            ]

        idx_cf = -1
        for c in conds:
            cid = c.get("id")
            codigo = (c.get("codigo") or "").strip().upper()

            try:
                cid_int = int(cid) if cid is not None else None
            except Exception:
                cid_int = None

            if cid_int is not None:
                self._cond_iva_by_id[cid_int] = c
            if codigo:
                self._cond_iva_by_codigo[codigo] = c

            desc = c.get("descripcion") or c.get("nombre") or c.get("codigo") or str(c.get("id", ""))
            if cid_int is not None:
                self.in_condicion_iva_receptor.addItem(desc, cid_int)
                if codigo == "CF":
                    idx_cf = self.in_condicion_iva_receptor.count() - 1

        self.in_condicion_iva_receptor.blockSignals(False)
        if idx_cf >= 0:
            self.in_condicion_iva_receptor.setCurrentIndex(idx_cf)

    def _select_condicion_iva_from_raw(self, raw: Any) -> None:
        if raw is None or raw == "":
            return
        try:
            cid_int = int(raw)
        except Exception:
            cid_int = None

        if cid_int is not None:
            idx = self.in_condicion_iva_receptor.findData(cid_int)
            if idx >= 0:
                self.in_condicion_iva_receptor.setCurrentIndex(idx)
                return

        codigo = str(raw).strip().upper()
        for cid, c in self._cond_iva_by_id.items():
            cod = (c.get("codigo") or "").strip().upper()
            if cod == codigo:
                idx = self.in_condicion_iva_receptor.findData(cid)
                if idx >= 0:
                    self.in_condicion_iva_receptor.setCurrentIndex(idx)
                return

    # ---------------- Permisos de edición ----------------

    def _compute_can_edit_current(self) -> bool:
        estado_id = self._estado_id
        estado_nombre = (self.in_estado.text() or "").strip().lower()

        try:
            st_aut = getattr(self._svc_facturas, "ESTADO_AUTORIZADA", None)
            st_anulada = getattr(self._svc_facturas, "ESTADO_ANULADA", None)
            st_baja = getattr(self._svc_facturas, "ESTADO_DADA_DE_BAJA", None)
            st_anulada_nc = getattr(self._svc_facturas, "ESTADO_ANULADA_POR_NC", None)
        except Exception:
            st_aut = st_anulada = st_baja = st_anulada_nc = None

        if getattr(self, "_baja", False):
            return False

        if st_aut is not None and estado_id == st_aut:
            return False
        if st_anulada is not None and estado_id == st_anulada:
            return False
        if st_baja is not None and estado_id == st_baja:
            return False
        if st_anulada_nc is not None and estado_id == st_anulada_nc:
            return False

        if "autoriz" in estado_nombre:
            return False
        if "anulad" in estado_nombre:
            return False
        if "baja" in estado_nombre:
            return False

        return True

    def _apply_edit_visibility(self) -> None:
        edit_only_visible = self._edit_mode

        self.btn_cliente_limpiar.setVisible(edit_only_visible)
        self._detalle_actions_wrap.setVisible(edit_only_visible)
        self.btn_add_row.setVisible(edit_only_visible)
        self.btn_del_row.setVisible(edit_only_visible)

        self.btn_guardar.setVisible(edit_only_visible)
        self.btn_cancelar_edicion.setVisible(edit_only_visible)

        self.btn_modificar.setVisible((not self._edit_mode) and bool(self._can_edit_current))
        self.btn_modificar.setEnabled((not self._edit_mode) and bool(self._can_edit_current))

    # ---------------- Carga de datos ----------------

    def _load_data(self) -> None:
        db = SessionLocal()
        try:
            factura = self._svc_facturas.get(self._factura_id)
            if not factura:
                popUp.critical(self, "Error", f"No se encontró la factura ID {self._factura_id}.")
                return

            self._factura = factura
            self._tipo = factura.get("tipo") or ""

            try:
                self._estado_id = int(factura.get("estado_id")) if factura.get("estado_id") is not None else None
            except Exception:
                self._estado_id = None

            self._baja = bool(
                factura.get("baja")
                or factura.get("dada_de_baja")
                or factura.get("is_baja")
                or factura.get("anulada")
            )

            tipo = self._tipo
            pto = factura.get("punto_venta") or factura.get("pto_vta") or ""
            numero = factura.get("numero") or ""
            fecha = factura.get("fecha_emision") or factura.get("fecha") or ""
            moneda = factura.get("moneda") or "ARS"
            estado = factura.get("estado_nombre") or factura.get("estado") or ""
            cae = factura.get("cae") or ""
            vto_cae = factura.get("vto_cae") or ""
            cond_iva_raw = factura.get("condicion_iva_receptor_id") or factura.get("condicion_iva_receptor")
            obs = factura.get("observaciones") or ""

            if tipo:
                idx_tipo = self.in_tipo.findData(tipo)
                if idx_tipo < 0:
                    idx_tipo = self.in_tipo.findText(str(tipo))
                if idx_tipo >= 0:
                    self.in_tipo.setCurrentIndex(idx_tipo)
                else:
                    self.in_tipo.addItem(str(tipo), tipo)
                    self.in_tipo.setCurrentIndex(self.in_tipo.count() - 1)

            if pto != "":
                try:
                    pto_int = int(pto)
                except Exception:
                    pto_int = None

                if pto_int is not None:
                    idx_pv = self.in_pto_vta.findData(pto_int)
                    if idx_pv >= 0:
                        self.in_pto_vta.setCurrentIndex(idx_pv)
                    else:
                        label = str(pto_int).zfill(4)
                        self.in_pto_vta.addItem(label, pto_int)
                        self.in_pto_vta.setCurrentIndex(self.in_pto_vta.count() - 1)
                else:
                    self.in_pto_vta.addItem(str(pto), pto)
                    self.in_pto_vta.setCurrentIndex(self.in_pto_vta.count() - 1)

            self.in_numero.setText(str(numero))
            self.in_fecha_emision.setText(str(fecha))
            self.in_moneda.setText(str(moneda))
            self._select_condicion_iva_from_raw(cond_iva_raw)
            self.in_estado.setText(str(estado))
            self.in_cae.setText(str(cae))
            self.in_cae_vto.setText(str(vto_cae))
            self.in_observaciones.setPlainText(str(obs))

            cliente_id = factura.get("cliente_id")
            cliente_tipo_doc = factura.get("cliente_tipo_doc") or factura.get("tipo_doc") or ""
            cliente_nro_doc = factura.get("cliente_nro_doc") or factura.get("nro_doc") or ""
            cliente_email = factura.get("cliente_email") or factura.get("email") or ""
            cliente_telefono = factura.get("cliente_telefono") or factura.get("telefono") or ""
            cliente_direccion = factura.get("cliente_direccion") or factura.get("direccion") or ""

            if cliente_id is not None:
                cli_data = {
                    "id": cliente_id,
                    "nombre": factura.get("cliente_nombre"),
                    "apellido": factura.get("cliente_apellido"),
                    "tipo_doc": cliente_tipo_doc,
                    "nro_doc": cliente_nro_doc,
                    "email": cliente_email,
                    "telefono": cliente_telefono,
                    "direccion": cliente_direccion,
                }
                self._selected_cliente = cli_data
                self.cb_cliente.blockSignals(True)
                self.cb_cliente.clear()
                self.cb_cliente.addItem(_cliente_label(cli_data), cli_data)
                self.cb_cliente.setCurrentIndex(0)
                self.cb_cliente.blockSignals(False)
            else:
                self._selected_cliente = None

            self.in_cliente_tipo_doc.setText(str(cliente_tipo_doc))
            self.in_cliente_nro_doc.setText(str(cliente_nro_doc))
            self.in_cliente_email.setText(str(cliente_email))
            self.in_cliente_telefono.setText(str(cliente_telefono))
            self.in_cliente_direccion.setText(str(cliente_direccion))

            rows = db.execute(
                text(
                    """
                    SELECT
                        vehiculo_id,
                        descripcion,
                        cantidad,
                        precio_unitario,
                        alicuota_iva,
                        importe_neto,
                        importe_iva,
                        importe_total
                    FROM facturas_detalle
                    WHERE factura_id = :fid
                    ORDER BY id ASC
                    """
                ),
                {"fid": self._factura_id},
            ).mappings().all()

            self._load_detalle_grid(rows)

                        # -------- Datos de venta + cuotas --------
            venta_id = factura.get("venta_id")
            if venta_id:
                row_venta = db.execute(
                    text("""
                        SELECT
                            v.precio_total,
                            v.forma_pago_id,
                            v.anticipo,
                            pf.interes_pct,
                            fp.nombre AS forma_pago,
                            pf.id AS plan_id,
                            pf.cantidad_cuotas
                        FROM ventas v
                        LEFT JOIN forma_pago fp ON fp.id = v.forma_pago_id
                        LEFT JOIN plan_financiacion pf ON pf.venta_id = v.id
                        WHERE v.id = :id
                    """),
                    {"id": venta_id},
                ).mappings().first()

                if row_venta:
                    self.in_precio_real.setText(_format_money(row_venta["precio_total"] or 0))
                    self.in_forma_pago.setText(row_venta.get("forma_pago") or "")
                    self.in_anticipo.setText(_format_money(row_venta.get("anticipo") or 0))
                    self.in_interes.setText(str(row_venta.get("interes_pct") or 0))
                    self.in_cant_cuotas.setText(str(row_venta.get("cantidad_cuotas") or 0))

                    plan_id = row_venta.get("plan_id")
                    if plan_id:
                        cuotas = db.execute(
                            text("""
                                SELECT
                                    nro_cuota,
                                    fecha_vencimiento,
                                    monto,
                                    monto_pagado,
                                    estado
                                FROM cuotas
                                WHERE plan_id = :pid
                                ORDER BY nro_cuota
                            """),
                            {"pid": plan_id},
                        ).mappings().all()

                        self.tbl_cuotas.setRowCount(0)
                        for c in cuotas:
                            r = self.tbl_cuotas.rowCount()
                            self.tbl_cuotas.insertRow(r)

                            nro = c["nro_cuota"]
                            venc = c["fecha_vencimiento"]
                            monto = float(c["monto"] or 0.0)
                            pagado = float(c["monto_pagado"] or 0.0)
                            estado_db = c["estado"]

                            # 🔎 estado real (pendiente / parcial / vencida / pagada)
                            estado = self._resolve_estado_cuota(
                                estado_db,
                                venc,
                                monto,
                                pagado,
                            )

                            self.tbl_cuotas.setItem(r, 0, QTableWidgetItem(str(nro)))
                            self.tbl_cuotas.setItem(r, 1, QTableWidgetItem(str(venc)))
                            self.tbl_cuotas.setItem(r, 2, QTableWidgetItem(_format_money(monto)))
                            self.tbl_cuotas.setItem(r, 3, QTableWidgetItem(_format_money(pagado)))
                            self.tbl_cuotas.setItem(r, 4, QTableWidgetItem(estado))

                            # 🎨 color suave por estado
                            self._apply_cuota_row_style(r, estado)

                            # ℹ️ tooltip informativo
                            self.tbl_cuotas.item(r, 4).setToolTip(
                                f"Vencimiento: {venc}\n"
                                f"Monto: {_format_money(monto)}\n"
                                f"Pagado: {_format_money(pagado)}"
                            )

                        self.sec_cuotas.setVisible(True)
                    else:
                        self.sec_cuotas.setVisible(False)
            else:
                self.sec_venta.setVisible(False)
                self.sec_cuotas.setVisible(False)


            subtotal = factura.get("subtotal")
            iva = factura.get("iva")
            total = factura.get("total")

            if subtotal is None or iva is None or total is None:
                subtotal = iva = total = 0.0
                for r in rows:
                    subtotal += float(r.get("importe_neto") or 0.0)
                    iva += float(r.get("importe_iva") or 0.0)
                    total += float(r.get("importe_total") or 0.0)

            self.in_subtotal.setText(_format_money(float(subtotal or 0.0)))
            self.in_iva_total.setText(_format_money(float(iva or 0.0)))
            self.in_total.setText(_format_money(float(total or 0.0)))

            self._ajustar_ancho_detalle()

            self._can_edit_current = self._compute_can_edit_current()
            self._set_edit_mode(False)

            # NC button (visible/enabled/tooltip) según estado real
            self._update_nc_button_state()

        finally:
            db.close()

    # ---------------- Detalle (tabla) ----------------

    def _load_detalle_grid(self, rows) -> None:
        self.tbl_detalle.setRowCount(0)
        for r in rows or []:
            self._append_detalle_row(
                vehiculo_id=r.get("vehiculo_id"),
                descripcion=r.get("descripcion") or "",
                cantidad=float(r.get("cantidad") or 0.0),
                precio_unitario=float(r.get("precio_unitario") or 0.0),
                alicuota_iva=float(r.get("alicuota_iva") or 0.0),
                importe_neto=float(r.get("importe_neto") or 0.0),
                importe_iva=float(r.get("importe_iva") or 0.0),
                importe_total=float(r.get("importe_total") or 0.0),
            )

    def _set_item_editable(self, item: QTableWidgetItem, editable: bool) -> None:
        flags = item.flags()
        if editable:
            item.setFlags(flags | Qt.ItemIsEditable)
        else:
            item.setFlags(flags & ~Qt.ItemIsEditable)

    def _append_detalle_row(
        self,
        *,
        vehiculo_id: Optional[int],
        descripcion: str,
        cantidad: float,
        precio_unitario: float,
        alicuota_iva: float,
        importe_neto: float,
        importe_iva: float,
        importe_total: float,
    ) -> None:
        row = self.tbl_detalle.rowCount()
        self.tbl_detalle.insertRow(row)

        if self._edit_mode:
            cb = VehiculoSelectorCombo(self._svc_vehiculos)
            cb.setObjectName("VehiculoCombo")

            if vehiculo_id:
                try:
                    v = self._svc_vehiculos.get_by_id(int(vehiculo_id))
                except Exception:
                    v = None
                if v:
                    cb.blockSignals(True)
                    cb.clear()
                    cb.addItem(_vehiculo_label(v), v)
                    cb.setCurrentIndex(0)
                    cb.blockSignals(False)

            cb.vehiculo_selected.connect(lambda _v, rr=row: self._on_detalle_changed(rr))
            self.tbl_detalle.setCellWidget(row, self.COL_VEHICULO, cb)
        else:
            item = QTableWidgetItem(str(descripcion))
            self._set_item_editable(item, False)
            self.tbl_detalle.setItem(row, self.COL_VEHICULO, item)

        it_cant = QTableWidgetItem(_format_money(cantidad))
        it_cant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._set_item_editable(it_cant, self._edit_mode)
        self.tbl_detalle.setItem(row, self.COL_CANT, it_cant)

        it_pu = QTableWidgetItem(_format_money(precio_unitario))
        it_pu.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._set_item_editable(it_pu, self._edit_mode)
        self.tbl_detalle.setItem(row, self.COL_PUNIT, it_pu)

        it_iva_pct = QTableWidgetItem(_format_money(alicuota_iva))
        it_iva_pct.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._set_item_editable(it_iva_pct, self._edit_mode)
        self.tbl_detalle.setItem(row, self.COL_IVA_PCT, it_iva_pct)

        it_neto = QTableWidgetItem(_format_money(importe_neto))
        it_neto.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._set_item_editable(it_neto, False)
        self.tbl_detalle.setItem(row, self.COL_NETO, it_neto)

        it_iva = QTableWidgetItem(_format_money(importe_iva))
        it_iva.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._set_item_editable(it_iva, False)
        self.tbl_detalle.setItem(row, self.COL_IVA, it_iva)

        it_total = QTableWidgetItem(_format_money(importe_total))
        it_total.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._set_item_editable(it_total, False)
        self.tbl_detalle.setItem(row, self.COL_TOTAL, it_total)

    def _add_detalle_row(self) -> None:
        if not self._edit_mode:
            return
        self._append_detalle_row(
            vehiculo_id=None,
            descripcion="",
            cantidad=1.0,
            precio_unitario=0.0,
            alicuota_iva=21.0,
            importe_neto=0.0,
            importe_iva=0.0,
            importe_total=0.0,
        )
        self._ajustar_ancho_detalle()

    def _remove_selected_row(self) -> None:
        if not self._edit_mode:
            return
        row = self.tbl_detalle.currentRow()
        if row < 0:
            return
        self.tbl_detalle.removeRow(row)
        self._recalc_totales_from_grid()

    def _on_detalle_changed(self, row: int) -> None:
        if not self._edit_mode:
            return
        self._recalc_row(row)
        self._recalc_totales_from_grid()

    def _recalc_row(self, row: int) -> None:
        cant = _parse_decimal(self.tbl_detalle.item(row, self.COL_CANT).text())
        punit = _parse_decimal(self.tbl_detalle.item(row, self.COL_PUNIT).text())
        iva_pct = _parse_decimal(self.tbl_detalle.item(row, self.COL_IVA_PCT).text())

        neto = cant * punit
        iva = neto * iva_pct / 100.0
        total = neto + iva

        self.tbl_detalle.item(row, self.COL_NETO).setText(_format_money(neto))
        self.tbl_detalle.item(row, self.COL_IVA).setText(_format_money(iva))
        self.tbl_detalle.item(row, self.COL_TOTAL).setText(_format_money(total))

    def _recalc_totales_from_grid(self) -> None:
        subtotal = 0.0
        iva = 0.0
        total = 0.0
        for r in range(self.tbl_detalle.rowCount()):
            subtotal += _parse_decimal(self.tbl_detalle.item(r, self.COL_NETO).text())
            iva += _parse_decimal(self.tbl_detalle.item(r, self.COL_IVA).text())
            total += _parse_decimal(self.tbl_detalle.item(r, self.COL_TOTAL).text())
        self.in_subtotal.setText(_format_money(subtotal))
        self.in_iva_total.setText(_format_money(iva))
        self.in_total.setText(_format_money(total))

    # ---------------- Cliente dinámico ----------------

    def _on_cliente_text_edited(self, _text: str) -> None:
        if not self._edit_mode:
            return
        self._cliente_search_timer.start()

    def _do_cliente_search(self) -> None:
        textq = (self.cb_cliente.lineEdit().text() or "").strip()
        if len(textq) < 3:
            return
        try:
            rows, _ = self._svc_clientes.search({"q": textq}, page=1, page_size=20)
        except Exception:
            rows = []

        self._cliente_results = rows or []
        cur = self.cb_cliente.lineEdit().text()

        self.cb_cliente.blockSignals(True)
        self.cb_cliente.clear()
        for c in self._cliente_results:
            self.cb_cliente.addItem(_cliente_label(c), c)
        self.cb_cliente.setCurrentIndex(-1)
        self.cb_cliente.blockSignals(False)

        self.cb_cliente.lineEdit().setText(cur)
        if self.cb_cliente.count() > 0:
            self.cb_cliente.showPopup()

    def _on_cliente_selected(self, idx: int) -> None:
        if idx < 0:
            return
        data = self.cb_cliente.itemData(idx)
        if not isinstance(data, dict):
            return
        self._selected_cliente = data
        self.in_cliente_tipo_doc.setText(str(data.get("tipo_doc") or ""))
        self.in_cliente_nro_doc.setText(str(data.get("nro_doc") or ""))
        self.in_cliente_email.setText(str(data.get("email") or ""))
        self.in_cliente_telefono.setText(str(data.get("telefono") or ""))
        self.in_cliente_direccion.setText(str(data.get("direccion") or ""))

    def _on_cliente_limpiar(self) -> None:
        if not self._edit_mode:
            return
        self._selected_cliente = None
        self.cb_cliente.blockSignals(True)
        self.cb_cliente.clear()
        self.cb_cliente.blockSignals(False)
        self.in_cliente_tipo_doc.setText("")
        self.in_cliente_nro_doc.setText("")
        self.in_cliente_email.setText("")
        self.in_cliente_telefono.setText("")
        self.in_cliente_direccion.setText("")

    # ---------------- Modo edición ----------------

    def _set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)

        self.in_tipo.setEnabled(enabled)
        self.in_pto_vta.setEnabled(enabled)
        self.in_numero.setReadOnly(not enabled)
        self.in_fecha_emision.setReadOnly(not enabled)
        self.in_moneda.setReadOnly(not enabled)
        self.in_condicion_iva_receptor.setEnabled(enabled)

        self.cb_cliente.setEnabled(enabled)
        self.btn_cliente_limpiar.setEnabled(enabled)

        self.in_observaciones.setReadOnly(not enabled)

        self.tbl_detalle.setEditTriggers(
            QAbstractItemView.AllEditTriggers if enabled else QAbstractItemView.NoEditTriggers
        )

        self.btn_add_row.setEnabled(enabled)
        self.btn_del_row.setEnabled(enabled)

        self.btn_guardar.setEnabled(enabled)
        self.btn_cancelar_edicion.setEnabled(enabled)

        self.btn_pdf.setEnabled(True)

        self._apply_edit_visibility()

        if self._factura is not None:
            self._reload_detail_for_mode()

        self._update_nc_button_state()

    def _reload_detail_for_mode(self) -> None:
        db = SessionLocal()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT
                        vehiculo_id,
                        descripcion,
                        cantidad,
                        precio_unitario,
                        alicuota_iva,
                        importe_neto,
                        importe_iva,
                        importe_total
                    FROM facturas_detalle
                    WHERE factura_id = :fid
                    ORDER BY id ASC
                    """
                ),
                {"fid": self._factura_id},
            ).mappings().all()
        finally:
            db.close()

        self._load_detalle_grid(rows)
        self._ajustar_ancho_detalle()
        self._recalc_totales_from_grid()

    def _on_modificar(self) -> None:
        if not self._can_edit_current:
            NotifyPopup(
                "Esta factura no se puede modificar (está autorizada/anulada/baja).",
                "warning",
                self,
            ).show_centered()
            return

        self._snapshot_cabecera = {
            "tipo": self.in_tipo.currentData(),
            "pto_vta": self.in_pto_vta.currentData(),
            "numero": self.in_numero.text(),
            "fecha_emision": self.in_fecha_emision.text(),
            "moneda": self.in_moneda.text(),
            "condicion_iva_receptor_id": self.in_condicion_iva_receptor.currentData(),
            "observaciones": self.in_observaciones.toPlainText(),
            "cliente": self._selected_cliente,
        }
        self._set_edit_mode(True)

    def _on_cancelar_edicion(self) -> None:
        self._set_edit_mode(False)
        self._load_data()

    def _on_guardar_cambios(self) -> None:
        if not self._edit_mode:
            return

        cabecera = {
            "tipo": self.in_tipo.currentData() or self.in_tipo.currentText(),
            "pto_vta": self.in_pto_vta.currentData() or self.in_pto_vta.currentText(),
            "numero": int(self.in_numero.text().strip() or 0),
            "fecha_emision": self.in_fecha_emision.text().strip(),
            "moneda": self.in_moneda.text().strip() or "ARS",
            "cliente_id": (self._selected_cliente or {}).get("id") if self._selected_cliente else None,
            "condicion_iva_receptor_id": self.in_condicion_iva_receptor.currentData(),
            "subtotal": _parse_decimal(self.in_subtotal.text()),
            "iva": _parse_decimal(self.in_iva_total.text()),
            "total": _parse_decimal(self.in_total.text()),
            "observaciones": self.in_observaciones.toPlainText().strip(),
        }

        items: List[Dict[str, Any]] = []
        for r in range(self.tbl_detalle.rowCount()):
            vehiculo_id = None
            descripcion = ""

            w = self.tbl_detalle.cellWidget(r, self.COL_VEHICULO)
            if isinstance(w, VehiculoSelectorCombo):
                v = w.selected_vehiculo
                if v:
                    vehiculo_id = v.get("id")
                    descripcion = _vehiculo_label(v)
            else:
                it = self.tbl_detalle.item(r, self.COL_VEHICULO)
                descripcion = it.text() if it else ""

            cantidad = _parse_decimal(self.tbl_detalle.item(r, self.COL_CANT).text())
            precio_unitario = _parse_decimal(self.tbl_detalle.item(r, self.COL_PUNIT).text())
            alicuota_iva = _parse_decimal(self.tbl_detalle.item(r, self.COL_IVA_PCT).text())
            importe_neto = _parse_decimal(self.tbl_detalle.item(r, self.COL_NETO).text())
            importe_iva = _parse_decimal(self.tbl_detalle.item(r, self.COL_IVA).text())
            importe_total = _parse_decimal(self.tbl_detalle.item(r, self.COL_TOTAL).text())

            items.append(
                {
                    "vehiculo_id": vehiculo_id,
                    "descripcion": descripcion,
                    "cantidad": cantidad,
                    "precio_unitario": precio_unitario,
                    "alicuota_iva": alicuota_iva,
                    "importe_neto": importe_neto,
                    "importe_iva": importe_iva,
                    "importe_total": importe_total,
                }
            )

        db = SessionLocal()
        try:
            db.execute(
                text(
                    """
                    UPDATE facturas
                    SET
                        tipo = :tipo,
                        punto_venta = :pto_vta,
                        numero = :numero,
                        fecha_emision = :fecha_emision,
                        moneda = :moneda,
                        cliente_id = :cliente_id,
                        condicion_iva_receptor_id = :cond_iva,
                        subtotal = :subtotal,
                        iva = :iva,
                        total = :total,
                        observaciones = :obs
                    WHERE id = :id
                    """
                ),
                {
                    "tipo": cabecera["tipo"],
                    "pto_vta": cabecera["pto_vta"],
                    "numero": cabecera["numero"],
                    "fecha_emision": cabecera["fecha_emision"],
                    "moneda": cabecera["moneda"],
                    "cliente_id": cabecera["cliente_id"],
                    "cond_iva": cabecera["condicion_iva_receptor_id"],
                    "subtotal": cabecera["subtotal"],
                    "iva": cabecera["iva"],
                    "total": cabecera["total"],
                    "obs": cabecera["observaciones"],
                    "id": self._factura_id,
                },
            )

            db.execute(
                text("DELETE FROM facturas_detalle WHERE factura_id = :fid"),
                {"fid": self._factura_id},
            )

            for it in items:
                db.execute(
                    text(
                        """
                        INSERT INTO facturas_detalle (
                            factura_id,
                            vehiculo_id,
                            descripcion,
                            cantidad,
                            precio_unitario,
                            alicuota_iva,
                            importe_neto,
                            importe_iva,
                            importe_total
                        ) VALUES (
                            :factura_id,
                            :vehiculo_id,
                            :descripcion,
                            :cantidad,
                            :precio_unitario,
                            :alicuota_iva,
                            :importe_neto,
                            :importe_iva,
                            :importe_total
                        )
                        """
                    ),
                    {
                        "factura_id": self._factura_id,
                        "vehiculo_id": it["vehiculo_id"],
                        "descripcion": it["descripcion"],
                        "cantidad": it["cantidad"],
                        "precio_unitario": it["precio_unitario"],
                        "alicuota_iva": it["alicuota_iva"],
                        "importe_neto": it["importe_neto"],
                        "importe_iva": it["importe_iva"],
                        "importe_total": it["importe_total"],
                    },
                )

            db.commit()
        except Exception as ex:
            db.rollback()
            NotifyPopup(f"Error al guardar cambios de la factura:\n{ex}", "error", self).show_centered()
            return
        finally:
            db.close()

        NotifyPopup("Cambios guardados correctamente.", "success", self).show_centered()
        self._load_data()

    # ---------------- Popup info ----------------

    def _on_ver_info(self) -> None:
        if not self._factura:
            return

        pto = self._factura.get("punto_venta") or self._factura.get("pto_vta") or ""
        nro = self._factura.get("numero") or ""
        tipo = self._factura.get("tipo") or ""
        fecha = self._factura.get("fecha_emision") or self._factura.get("fecha") or ""
        total = _format_money(float(self._factura.get("total") or 0.0))
        cae = str(self._factura.get("cae") or "")
        vto_cae = str(self._factura.get("vto_cae") or "")
        cliente = str(self._factura.get("cliente") or "")

        fields = [
            ("Tipo", str(tipo)),
            ("Punto de venta", str(pto)),
            ("Número", str(nro)),
            ("Comprobante", f"{str(pto).zfill(4)}-{str(nro).zfill(8)}"),
            ("Fecha", str(fecha)),
            ("Cliente", cliente),
            ("Total", total),
            ("CAE", cae),
            ("Vto CAE", vto_cae),
        ]

        dlg = MovableDialog(self)
        dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.resize(700, 520)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("Panel")
        card.setStyleSheet(
            """
            QFrame#Panel {
                background: white;
                border-radius: 12px;
            }
            QToolButton#CopyButton {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 3px 8px;
                background: #f7f7f7;
            }
            QToolButton#CopyButton:hover { background: #eaeaea; }
            QToolButton#CopyButton:pressed { background: #dddddd; }
            """
        )
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(20, 20, 20, 20)
        card_l.setSpacing(10)

        title = QLabel("Información de la factura")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        card_l.addWidget(title)

        subtitle = QLabel("Usá los botones de copiar para pegar rápido en otros sistemas.")
        subtitle.setWordWrap(True)
        card_l.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        card_l.addWidget(scroll, 1)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(container)

        copy_icon = QIcon.fromTheme("edit-copy")
        if copy_icon.isNull():
            copy_icon = QApplication.style().standardIcon(QStyle.SP_DialogSaveButton)

        for row, (label, value) in enumerate(fields):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            txt = QLineEdit(value)
            txt.setReadOnly(True)
            txt.setObjectName("TextInput")

            btn_copy = QToolButton()
            btn_copy.setObjectName("CopyButton")
            btn_copy.setIcon(copy_icon)
            btn_copy.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn_copy.setCursor(Qt.PointingHandCursor)

            def make_handler(val=value, lab=label):
                def _h():
                    QApplication.clipboard().setText(val)
                    NotifyPopup.info(self, f"Copiado: {lab}")
                return _h

            btn_copy.clicked.connect(make_handler())

            grid.addWidget(lbl, row, 0)
            grid.addWidget(txt, row, 1)
            grid.addWidget(btn_copy, row, 2)

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(dlg.accept)
        btn_close.setMinimumWidth(120)
        card_l.addWidget(btn_close, alignment=Qt.AlignHCenter)

        root.addWidget(card)
        dlg.exec()

    # ---------------- Nota de crédito ----------------

    def _update_nc_button_state(self) -> None:
        """
        FIX IMPORTANTE: además de enable/tooltip, ahora también controlamos VISIBILIDAD,
        para que NO aparezca el botón cuando no corresponde (como pediste).
        """
        tipo = (self._tipo or "").upper()
        estado_id = self._estado_id
        estado_nombre = (self.in_estado.text() or "").strip().lower()

        # defaults
        self.btn_nc.setVisible(True)
        self.btn_nc.setEnabled(True)
        self.btn_nc.setToolTip("Generar una nota de crédito que anule esta factura.")

        try:
            st_aut = getattr(self._svc_facturas, "ESTADO_AUTORIZADA", None)
            st_anulada = getattr(self._svc_facturas, "ESTADO_ANULADA", None)
            st_baja = getattr(self._svc_facturas, "ESTADO_DADA_DE_BAJA", None)
            st_anulada_nc = getattr(self._svc_facturas, "ESTADO_ANULADA_POR_NC", None)
        except Exception:
            st_aut = st_anulada = st_baja = st_anulada_nc = None

        # 1) Baja/anulada => ocultar
        if getattr(self, "_baja", False):
            self.btn_nc.setVisible(False)
            return
        if (st_baja is not None and estado_id == st_baja) or ("baja" in estado_nombre):
            self.btn_nc.setVisible(False)
            return
        if (st_anulada is not None and estado_id == st_anulada) or ("anulad" in estado_nombre):
            self.btn_nc.setVisible(False)
            return

        # 2) No permitir sobre NC (ocultar)
        if tipo.startswith("NC"):
            self.btn_nc.setVisible(False)
            return

        # 3) Solo si AUTORIZADA (si no, ocultar)
        if st_aut is not None:
            if estado_id != st_aut:
                self.btn_nc.setVisible(False)
                return
        else:
            # fallback por texto
            if "autoriz" not in estado_nombre:
                self.btn_nc.setVisible(False)
                return

        # 4) Si ya fue anulada por otra NC (ocultar)
        if st_anulada_nc is not None and estado_id == st_anulada_nc:
            self.btn_nc.setVisible(False)
            return

        # Si llegamos acá: visible y habilitado
        self.btn_nc.setVisible(True)
        self.btn_nc.setEnabled(True)

    def _registrar_error_arca_en_observaciones(self, mensaje: str) -> None:
        """
        FIX: en MySQL NO existe '||' para concatenar.
        Usamos CONCAT(...) + salto de línea.
        """
        if not mensaje:
            return
        db = SessionLocal()
        try:
            db.execute(
                text(
                    """
                    UPDATE facturas
                    SET observaciones = TRIM(
                        CONCAT(
                            COALESCE(observaciones, ''),
                            CASE
                                WHEN observaciones IS NULL OR observaciones = '' THEN ''
                                ELSE '\n'
                            END,
                            :msg
                        )
                    )
                    WHERE id = :id
                    """
                ),
                {"msg": mensaje, "id": self._factura_id},
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _on_generar_nc(self) -> None:
        generar_nc = getattr(self._svc_facturas, "generar_nota_credito", None)
        if not callable(generar_nc):
            NotifyPopup(
                "Aún no está implementada la generación de notas de crédito en el servicio.",
                "warning",
                self,
            ).show_centered()
            return

        tipo = self._tipo or ""
        nro = self.in_numero.text().strip()
        pto = self.in_pto_vta.currentText().strip()

        dlg = ConfirmDialog(
            "Generar nota de crédito",
            f"¿Generar una nota de crédito que anule la factura {tipo} {pto}-{nro}?",
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        self.btn_nc.setEnabled(False)
        old_cursor = self.cursor()
        self.setCursor(Qt.WaitCursor)
        QApplication.processEvents()

        try:
            result = generar_nc(self._factura_id)
        except Exception as ex:
            self.setCursor(old_cursor)
            self.btn_nc.setEnabled(True)
            msg = f"Error al generar la nota de crédito: {ex}"
            NotifyPopup(msg, "error", self).show_centered()
            self._registrar_error_arca_en_observaciones(msg)
            return

        self.setCursor(old_cursor)

        if not isinstance(result, dict):
            msg = "La respuesta del servicio de notas de crédito no es válida."
            NotifyPopup(msg, "error", self).show_centered()
            self._registrar_error_arca_en_observaciones(msg)
            self._update_nc_button_state()
            return

        msg = result.get("mensaje") or ""
        estado_nc_id = result.get("estado_nc_id")
        errores = result.get("errores") or []
        observaciones = result.get("observaciones") or []

        if result.get("aprobada"):
            detalle = (
                f"Nota de crédito generada y autorizada.\n"
                f"Tipo: {result.get('nc_tipo')} "
                f"{str(result.get('nc_pto_vta')).zfill(4) if result.get('nc_pto_vta') is not None else ''}-"
                f"{result.get('nc_numero')}\n"
                f"Total: {_format_money(float(result.get('nc_total') or 0.0))}\n"
                f"CAE: {result.get('cae')}\n"
                f"Vto CAE: {result.get('vto_cae')}"
            )
            if msg:
                detalle += "\n\n" + msg
            NotifyPopup(detalle, "success", self).show_centered()
            self._load_data()
            return

        if errores or observaciones:
            msg_extra = errores + observaciones
            if msg:
                msg += "\n"
            msg += "\n".join(f"- {e}" for e in msg_extra)

        if result.get("rechazada"):
            full_msg = "La nota de crédito fue rechazada por ARCA.\n" + msg
            NotifyPopup(full_msg, "error", self).show_centered()
            self._registrar_error_arca_en_observaciones(full_msg)
            self._load_data()
            return

        try:
            estado_error_com = self._svc_facturas.ESTADO_ERROR_COMUNICACION
        except Exception:
            estado_error_com = None

        if estado_error_com is not None and estado_nc_id == estado_error_com:
            full_msg = "Error de comunicación con ARCA al generar la nota de crédito.\n" + msg
            NotifyPopup(full_msg, "error", self).show_centered()
            self._registrar_error_arca_en_observaciones(full_msg)
            self._load_data()
            return

        full_msg = "No se pudo generar la nota de crédito.\n" + msg
        NotifyPopup(full_msg, "error", self).show_centered()
        self._registrar_error_arca_en_observaciones(full_msg)
        self._load_data()

    # ---------------- Navegación ----------------

    def _on_volver(self) -> None:
        # 🔁 Si la factura se abrió desde el perfil del cliente,
        # volvemos explícitamente a ese cliente
        if self._return_to == "cliente" and self._cliente_id:
            mw = self._main_window
            if mw and hasattr(mw, "open_page"):
                mw.open_page(
                    "clientes_detalle",
                    cliente_id=int(self._cliente_id),
                )
            return
    
        # 🔙 Caso general: usar navegación normal
        self.go_back.emit()
    
