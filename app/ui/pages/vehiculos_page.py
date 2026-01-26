from __future__ import annotations
from typing import Any, Dict, List, Optional
import os

from PySide6.QtCore import Qt, Signal, QSize, QSettings
from PySide6.QtGui import QIntValidator, QAction, QIcon
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QSizePolicy, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QVBoxLayout, QLabel, QHeaderView, 
    QAbstractItemView, QListView, QMainWindow, QMenu
)
import app.ui.app_message as popUp
from app.services.vehiculos_service import VehiculosService
from app.ui.pages.vehiculos_agregar import VehiculosAgregarPage
from app.ui.utils.loading_decorator import with_loading
from pathlib import Path
from app.ui.utils.table_utils import setup_compact_table
from app.ui.utils.text_utils import tail_ellipsis
from PySide6.QtWidgets import QApplication
ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"

class VehiculosPage(QWidget):
    open_detail = Signal(int)

    COL_ID = 0
    COL_MARCA = 1
    COL_MODELO = 2
    COL_ANIO = 3
    COL_CERT = 4
    COL_DNRPA = 5
    COL_CUADRO = 6
    COL_MOTOR = 7
    COL_COLOR = 8
    COL_ESTADO = 9
    COL_CONDICION = 10
    COL_PROVEEDOR = 11
    COL_PRECIO = 12
    COL_OBS = 13
    COL_ACCION = 14

    SETTINGS_HEADER_STATE = "VehiculosPage/header_state_v1"
    SETTINGS_HIDDEN_COLS = "VehiculosPage/hidden_columns_v1"
    SETTINGS_PAGE_SIZE = "VehiculosPage/page_size_v1"

    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None):
        super().__init__(parent)
        self.setObjectName("VehiculosPage")
        self.main_window: Optional[QMainWindow] = main_window
        self._vehiculos_agregar_ref: Optional[VehiculosAgregarPage] = None

        self.service = VehiculosService()
        self.settings = QSettings("Gussoni", "SistemaFacturacion")

        # ---- Filtros ----
        self.in_marca = QLineEdit(); self.in_marca.setPlaceholderText("Marca")
        self.in_modelo = QLineEdit(); self.in_modelo.setPlaceholderText("Modelo")

        self.in_anio = QLineEdit(); self.in_anio.setPlaceholderText("Año")
        self.in_anio.setValidator(QIntValidator(1900, 2100, self))

        self.in_nro_cuadro = QLineEdit(); self.in_nro_cuadro.setPlaceholderText("N° de cuadro")
        self.in_nro_motor = QLineEdit(); self.in_nro_motor.setPlaceholderText("N° de motor")

        self.in_nro_certificado = QLineEdit(); self.in_nro_certificado.setPlaceholderText("N° certificado")
        self.in_nro_dnrpa = QLineEdit(); self.in_nro_dnrpa.setPlaceholderText("N° DNRPA")
        self.in_observaciones = QLineEdit(); self.in_observaciones.setPlaceholderText("Buscar en observaciones")

        # Combos dinámicos
        self.in_color = QComboBox(); self._setup_combo(self.in_color); self.in_color.addItem("Todos", None)
        self.in_estado = QComboBox(); self._setup_combo(self.in_estado); self.in_estado.addItem("Todos", None)
        self.in_condicion = QComboBox(); self._setup_combo(self.in_condicion); self.in_condicion.addItem("Todas", None)

        # Botones
        self.btn_buscar = QPushButton("Buscar"); self.btn_buscar.setObjectName("BtnPrimary")
        self.btn_limpiar = QPushButton("Limpiar"); self.btn_limpiar.setObjectName("BtnGhost")
        self.btn_columnas = QPushButton("Columnas"); self.btn_columnas.setObjectName("BtnGhost")
        self.btn_agregar = QPushButton("Agregar"); self.btn_agregar.setObjectName("BtnPrimary")

        grid = QGridLayout()
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1); grid.setColumnStretch(3, 3)
        grid.setColumnStretch(4, 1); grid.setColumnStretch(5, 3)
        grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)

        # Filtros
        grid.addWidget(QLabel("Marca"), 0, 0); grid.addWidget(self.in_marca, 0, 1)
        grid.addWidget(QLabel("Modelo"), 0, 2); grid.addWidget(self.in_modelo, 0, 3)
        grid.addWidget(QLabel("Año"), 0, 4); grid.addWidget(self.in_anio, 0, 5)
        grid.addWidget(QLabel("N° Cuadro"), 1, 0); grid.addWidget(self.in_nro_cuadro, 1, 1)
        grid.addWidget(QLabel("N° Motor"), 1, 2); grid.addWidget(self.in_nro_motor, 1, 3)
        grid.addWidget(QLabel("Color"), 1, 4); grid.addWidget(self.in_color, 1, 5)
        grid.addWidget(QLabel("N° Certificado"), 2, 0); grid.addWidget(self.in_nro_certificado, 2, 1)
        grid.addWidget(QLabel("N° DNRPA"), 2, 2); grid.addWidget(self.in_nro_dnrpa, 2, 3)
        grid.addWidget(QLabel("Observaciones"), 2, 4); grid.addWidget(self.in_observaciones, 2, 5)
        grid.addWidget(QLabel("Estado stock"), 3, 0); grid.addWidget(self.in_estado, 3, 1)
        grid.addWidget(QLabel("Condición"), 3, 2); grid.addWidget(self.in_condicion, 3, 3)

        btns_wrap = QWidget()
        h = QHBoxLayout(btns_wrap); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        for b in (self.btn_buscar, self.btn_limpiar, self.btn_columnas, self.btn_agregar):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            h.addWidget(b)
        grid.addWidget(btns_wrap, 3, 4, 1, 2)

        # ---- Tabla ----
        self.table = QTableWidget(0, 15, self)
        self.table.setObjectName("DataTable")
        self.table.setHorizontalHeaderLabels([
            "ID", "Marca", "Modelo", "Año",
            "N° Certificado", "N° DNRPA", "N° Cuadro", "N° Motor",
            "Color", "Estado", "Condición", "Proveedor", "Precio lista",
            "Observaciones", "Acción"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setSortingEnabled(True)
        setup_compact_table(self.table)

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_ACCION, QHeaderView.ResizeToContents)

        self.table.setColumnHidden(self.COL_ID, True)
        self.table.setColumnHidden(self.COL_OBS, True)

        # Header "Precio lista" a la derecha
        price_header_item = self.table.horizontalHeaderItem(self.COL_PRECIO)
        if price_header_item:
            price_header_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # ---- Paginación ----
        self.page = 1
        self.total = 0
        self.page_size = int(self.settings.value(self.SETTINGS_PAGE_SIZE, 25))
        self.cmb_page_size = QComboBox(); self.cmb_page_size.setObjectName("BtnGhost")
        for n in (10, 25, 50, 100): self.cmb_page_size.addItem(f"Mostrar: {n}", n)
        idx = (10, 25, 50, 100).index(self.page_size) if self.page_size in (10, 25, 50, 100) else 1
        self.cmb_page_size.setCurrentIndex(idx)

        self.lbl_pages = QLabel("Página 1/1")
        self.btn_prev = QPushButton("◀"); self.btn_prev.setObjectName("BtnGhost")
        self.btn_next = QPushButton("▶"); self.btn_next.setObjectName("BtnGhost")

        pager = QHBoxLayout()
        pager.addWidget(self.cmb_page_size)
        pager.addStretch(1)
        pager.addWidget(self.btn_prev)
        pager.addWidget(self.lbl_pages)
        pager.addWidget(self.btn_next)

        # ---- Layout raíz ----
        root = QVBoxLayout(self)
        root.addLayout(grid)
        root.addWidget(self.table, 1)
        root.addLayout(pager)
        root.setStretch(1, 1)

        self._column_menu = QMenu(self)
        self._build_column_menu()

        self.btn_buscar.clicked.connect(self.on_search_clicked)
        self.btn_limpiar.clicked.connect(self.on_clear_filters_clicked)
        self.btn_columnas.clicked.connect(self.on_columnas_clicked)
        self.btn_agregar.clicked.connect(self._abrir_pantalla_agregar)
        self.cmb_page_size.currentIndexChanged.connect(self.on_page_size_changed)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)

        self._load_filter_data()
        self._restore_table_state()

        header.sectionResized.connect(lambda *_: self._save_table_state())
        header.sortIndicatorChanged.connect(lambda *_: self._save_table_state())

    # ---------------- Helpers ----------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        lv = QListView(); lv.setObjectName("ComboPopup"); lv.setUniformItemSizes(True); lv.setSpacing(2)
        cb.setView(lv)

    def _load_filter_data(self):
        try: colores = self.service.get_colores()
        except Exception: colores = []
        for c in colores:
            self.in_color.addItem(c.get("nombre", f"ID {c.get('id')}"), c.get("id"))

        try: estados_stock = self.service.get_estados_stock()
        except Exception: estados_stock = []
        for e in estados_stock:
            self.in_estado.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

        try: condiciones = self.service.get_estados_condicion()
        except Exception: condiciones = []
        for e in condiciones:
            self.in_condicion.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

    def _build_column_menu(self):
        self._column_menu.clear()
        togglables = [
            (self.COL_MARCA, "Marca"), (self.COL_MODELO, "Modelo"), (self.COL_ANIO, "Año"),
            (self.COL_CERT, "N° Certificado"), (self.COL_DNRPA, "N° DNRPA"),
            (self.COL_CUADRO, "N° Cuadro"), (self.COL_MOTOR, "N° Motor"), (self.COL_COLOR, "Color"),
            (self.COL_ESTADO, "Estado"), (self.COL_CONDICION, "Condición"), (self.COL_PROVEEDOR, "Proveedor"),
            (self.COL_PRECIO, "Precio lista"), (self.COL_OBS, "Observaciones"),
        ]
        for col, title in togglables:
            act = QAction(title, self._column_menu, checkable=True)
            act.setChecked(not self.table.isColumnHidden(col))
            act.toggled.connect(lambda checked, c=col: (self.table.setColumnHidden(c, not checked), self._save_table_state()))
            self._column_menu.addAction(act)

    def _save_table_state(self):
        try:
            state = self.table.horizontalHeader().saveState()
            self.settings.setValue(self.SETTINGS_HEADER_STATE, state)
            hidden = [i for i in range(self.table.columnCount()) if self.table.isColumnHidden(i)]
            self.settings.setValue(self.SETTINGS_HIDDEN_COLS, hidden)
            self.settings.setValue(self.SETTINGS_PAGE_SIZE, self.page_size)
        except Exception:
            pass

    def _restore_table_state(self):
        try:
            state = self.settings.value(self.SETTINGS_HEADER_STATE, None)
            if state is not None:
                self.table.horizontalHeader().restoreState(state)
            hidden = self.settings.value(self.SETTINGS_HIDDEN_COLS, None)
            if hidden is not None:
                if isinstance(hidden, str):
                    hidden = [int(x) for x in hidden.strip("[]").split(",") if x.strip().isdigit()]
                for i in range(self.table.columnCount()):
                    self.table.setColumnHidden(i, i in hidden)
                self.table.setColumnHidden(self.COL_ID, True)
            else:
                self.table.setColumnHidden(self.COL_OBS, True)
        except Exception:
            self.table.setColumnHidden(self.COL_ID, True)
            self.table.setColumnHidden(self.COL_OBS, True)

    # ---------------- Lógica ----------------
    def gather_filters(self) -> Dict[str, Any]:
        anio_txt = self.in_anio.text().strip()
        anio_val = int(anio_txt) if anio_txt.isdigit() else None
        return {
            "marca": self.in_marca.text().strip() or None,
            "modelo": self.in_modelo.text().strip() or None,
            "anio": anio_val,
            "nro_cuadro": self.in_nro_cuadro.text().strip() or None,
            "nro_motor": self.in_nro_motor.text().strip() or None,
            "nro_certificado": self.in_nro_certificado.text().strip() or None,
            "nro_dnrpa": self.in_nro_dnrpa.text().strip() or None,
            "observaciones": self.in_observaciones.text().strip() or None,
            "color_id": self.in_color.currentData(),
            "estado_stock_id": self.in_estado.currentData(),
            "estado_moto_id": self.in_condicion.currentData(),
        }

    @with_loading("Cargando vehículos...")
    def reload(self, reset_page: bool = False):
        if reset_page:
            self.page = 1
        filtros = self.gather_filters()
        rows, total = self.service.search(filtros, page=self.page, page_size=self.page_size)
        self.total = total
        self.populate_table(rows)
        pages = max((total + self.page_size - 1) // self.page_size, 1)
        self.lbl_pages.setText(f"Página {self.page}/{pages}")
        self.btn_prev.setEnabled(self.page > 1)
        self.btn_next.setEnabled(self.page < pages)

    def populate_table(self, rows: List[Dict[str, Any]]):
        was_sorting = self.table.isSortingEnabled()
        if was_sorting:
            self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(0)
            for r in rows:
                row = self.table.rowCount()
                self.table.insertRow(row)
                id_val = r.get("id", "")
                id_item = QTableWidgetItem(str(id_val))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, self.COL_ID, id_item)
                proveedor_nombre = (
                    r.get("proveedor") or r.get("proveedor_nombre")
                    or r.get("proveedor_razon_social") or r.get("proveedor_nombre_fantasia") or ""
                )
                cert = r.get("nro_certificado", "") or r.get("numero_certificado", "")
                dnrpa = r.get("nro_dnrpa", "") or r.get("numero_dnrpa", "")
                cuadro = r.get("numero_cuadro", "") or r.get("nro_cuadro", "")
                motor = r.get("numero_motor", "") or r.get("nro_motor", "")
                values = {
                    self.COL_MARCA: r.get("marca", ""), self.COL_MODELO: r.get("modelo", ""),
                    self.COL_ANIO: str(r.get("anio", "") or ""),
                    self.COL_CERT: tail_ellipsis(cert, 8),
                    self.COL_DNRPA: tail_ellipsis(dnrpa, 8),
                    self.COL_CUADRO: tail_ellipsis(cuadro, 8),
                    self.COL_MOTOR: tail_ellipsis(motor, 8),
                    self.COL_COLOR: r.get("color", "") or r.get("color_nombre", ""),
                    self.COL_ESTADO: r.get("estado_stock", "") or r.get("estado_stock_nombre", ""),
                    self.COL_CONDICION: r.get("estado_moto", "") or r.get("estado_moto_nombre", "") or r.get("condicion", ""),
                    self.COL_PROVEEDOR: proveedor_nombre,
                    self.COL_PRECIO: self._fmt_currency(r.get("precio_lista")),
                    self.COL_OBS: r.get("observaciones", "") or r.get("obs", ""),
                }
                for col, display_text in values.items():
                    item = QTableWidgetItem(display_text if isinstance(display_text, str) else str(display_text))

                    # 🔹 Tooltip con valor completo
                    if col == self.COL_CERT:
                        item.setToolTip(cert)
                    elif col == self.COL_DNRPA:
                        item.setToolTip(dnrpa)
                    elif col == self.COL_CUADRO:
                        item.setToolTip(cuadro)
                    elif col == self.COL_MOTOR:
                        item.setToolTip(motor)

                    if col == self.COL_PRECIO:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                    self.table.setItem(row, col, item)

                btn = QPushButton("🔍"); btn.setObjectName("BtnGhost")
                btn.setToolTip("Consultar"); btn.setCursor(Qt.PointingHandCursor)
                try: vid = int(id_val)
                except Exception: vid = None
                btn.clicked.connect(lambda _=False, _vid=vid: (self.open_detail.emit(_vid) if _vid is not None else None))
                self.table.setCellWidget(row, self.COL_ACCION, btn)
        finally:
            if was_sorting:
                self.table.setSortingEnabled(True)
            self._save_table_state()

    def _fmt_currency(self, v: Any) -> str:
        try:
            return f"$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return ""

    def on_search_clicked(self): self.reload(reset_page=True)
    def on_clear_filters_clicked(self):
        for le in (self.in_marca, self.in_modelo, self.in_anio,
                   self.in_nro_cuadro, self.in_nro_motor,
                   self.in_nro_certificado, self.in_nro_dnrpa, self.in_observaciones): le.clear()
        self.in_color.setCurrentIndex(0); self.in_estado.setCurrentIndex(0); self.in_condicion.setCurrentIndex(0)
        self.reload(reset_page=True)

  

    def on_columnas_clicked(self):
        self._build_column_menu()

        # 👇 CLAVE: forzar font global (ya escalado)
        self._column_menu.setFont(QApplication.font())

        self._column_menu.exec(
            self.btn_columnas.mapToGlobal(
                self.btn_columnas.rect().bottomLeft()
            )
        )


    def _abrir_pantalla_agregar(self):
        mw = getattr(self, "main_window", None) or self.window()
        if not isinstance(mw, QMainWindow):
            popUp.toast(self, "Error", "No pude abrir la pantalla de alta (MainWindow no disponible).")
            return
        if self._vehiculos_agregar_ref is None:
            page = VehiculosAgregarPage(mw)
            if hasattr(page, "go_back") and hasattr(mw, "open_page"):
                page.go_back.connect(lambda: mw.open_page("vehiculos"))
            if hasattr(page, "go_to_detalle") and hasattr(mw, "open_page"):
                page.go_to_detalle.connect(lambda vid: mw.open_page("vehiculos_detalle", vehiculo_id=vid))
            self._vehiculos_agregar_ref = page
            if hasattr(mw, "_mount") and callable(mw._mount):
                mw.stack.setCurrentWidget(mw._mount(page))
            else:
                if mw.stack.indexOf(page) == -1: mw.stack.addWidget(page)
                mw.stack.setCurrentWidget(page)
        else:
            page = self._vehiculos_agregar_ref
            if hasattr(page, "_limpiar_formulario"):
                try: page._limpiar_formulario()
                except Exception: pass
            if hasattr(mw, "_mount") and callable(mw._mount):
                mw.stack.setCurrentWidget(mw._mount(page))
            else:
                mw.stack.setCurrentWidget(page)

    def on_page_size_changed(self, _idx: int):
        self.page_size = int(self.cmb_page_size.currentData())
        self._save_table_state()
        if self.total > 0:
            self.reload(reset_page=True)

    def on_prev(self):
        if self.page > 1:
            self.page -= 1
            self.reload()

    def on_next(self):
        pages = max((self.total + self.page_size - 1) // self.page_size, 1)
        if self.page < pages:
            self.page += 1
            self.reload()
