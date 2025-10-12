from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QSizePolicy, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QVBoxLayout, QLabel, QHeaderView,
    QAbstractItemView, QListView
)
from app.services.vehiculos_service import VehiculosService


class VehiculosPage(QWidget):
    """
    Página principal de Vehículos:
      - Buscador (grid 1-3-1-3-1-3 estilo bootstrap)
      - Tabla paginada (responsive, llena todo el espacio)
      - Acción 🔍 → emite open_detail(int)
      - No carga datos al iniciar; solo al presionar Buscar.
    """
    open_detail = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VehiculosPage")

        self.service = VehiculosService()

        # ---- Filtros (1-3-1-3-1-3 + botón) ----
        self.in_marca = QLineEdit();   self.in_marca.setPlaceholderText("Marca")
        self.in_modelo = QLineEdit();  self.in_modelo.setPlaceholderText("Modelo")

        # Año: campo numérico sin flechas
        self.in_anio = QLineEdit();    self.in_anio.setPlaceholderText("Año")
        self.in_anio.setValidator(QIntValidator(1900, 2100, self))

        self.in_nro_cuadro = QLineEdit(); self.in_nro_cuadro.setPlaceholderText("N° de cuadro")
        self.in_nro_motor  = QLineEdit(); self.in_nro_motor.setPlaceholderText("N° de motor")

        # Combos dinámicos
        self.in_color = QComboBox();     self._setup_combo(self.in_color);     self.in_color.addItem("Todos", None)
        self.in_estado = QComboBox();    self._setup_combo(self.in_estado);    self.in_estado.addItem("Todos", None)
        self.in_condicion = QComboBox(); self._setup_combo(self.in_condicion); self.in_condicion.addItem("Todas", None)

        self.btn_buscar = QPushButton("Buscar"); self.btn_buscar.setObjectName("BtnPrimary")

        grid = QGridLayout()
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1); grid.setColumnStretch(3, 3)
        grid.setColumnStretch(4, 1); grid.setColumnStretch(5, 3)
        grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)

        # Fila 0
        grid.addWidget(QLabel("Marca"), 0, 0);   grid.addWidget(self.in_marca, 0, 1)
        grid.addWidget(QLabel("Modelo"), 0, 2);  grid.addWidget(self.in_modelo, 0, 3)
        grid.addWidget(QLabel("Año"), 0, 4);     grid.addWidget(self.in_anio, 0, 5)

        # Fila 1
        grid.addWidget(QLabel("N° Cuadro"), 1, 0); grid.addWidget(self.in_nro_cuadro, 1, 1)
        grid.addWidget(QLabel("N° Motor"), 1, 2);  grid.addWidget(self.in_nro_motor, 1, 3)
        grid.addWidget(QLabel("Color"), 1, 4);     grid.addWidget(self.in_color, 1, 5)

        # Fila 2: Estado + Condición + Botón al final
        grid.addWidget(QLabel("Estado stock"), 2, 0); grid.addWidget(self.in_estado, 2, 1)
        grid.addWidget(QLabel("Condición"), 2, 2);    grid.addWidget(self.in_condicion, 2, 3)
        spacer = QHBoxLayout(); spacer.addStretch(1); spacer_w = QWidget(); spacer_w.setLayout(spacer)
        grid.addWidget(spacer_w, 2, 4)
        grid.addWidget(self.btn_buscar, 2, 5)

        # ---- Tabla (responsive) ----
        # 12 columnas: [0] ID (OCULTA) + 1..11 visibles
        self.table = QTableWidget(0, 12, self)
        self.table.setObjectName("DataTable")
        self.table.setHorizontalHeaderLabels([
            "ID", "Marca", "Modelo", "Año", "N° Cuadro", "N° Motor",
            "Color", "Estado", "Condición", "Proveedor", "Precio lista", "Acción"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(11, QHeaderView.ResizeToContents)  # Acción
        self.table.setColumnHidden(0, True)  # ocultamos ID

        # ---- Paginación ----
        self.page = 1
        self.total = 0
        self.page_size = 25

        self.cmb_page_size = QComboBox(); self.cmb_page_size.setObjectName("BtnGhost")
        for n in (10, 25, 50, 100): self.cmb_page_size.addItem(f"Mostrar: {n}", n)
        self.cmb_page_size.setCurrentIndex(1)

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
        root.setStretch(0, 0); root.setStretch(1, 1); root.setStretch(2, 0)

        # ---- Señales ----
        self.btn_buscar.clicked.connect(self.on_search_clicked)
        self.cmb_page_size.currentIndexChanged.connect(self.on_page_size_changed)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)

        # Cargar combos dinámicos (sin disparar búsqueda)
        self._load_filter_data()
        # NO búsqueda inicial

    # ---------------- Data de filtros ----------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        lv = QListView(); lv.setObjectName("ComboPopup"); lv.setUniformItemSizes(True); lv.setSpacing(2)
        cb.setView(lv)

    def _load_filter_data(self):
        """Puebla combos desde la BD si el servicio lo soporta."""
        # Colores
        try:
            colores = self.service.get_colores()
        except Exception:
            colores = []
        for c in colores:
            self.in_color.addItem(c.get("nombre", f"ID {c.get('id')}"), c.get("id"))

        # Estados stock
        try:
            estados_stock = self.service.get_estados_stock()
        except Exception:
            estados_stock = []
        for e in estados_stock:
            self.in_estado.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

        # Condición (nueva/usada)
        try:
            condiciones = self.service.get_estados_condicion()
        except Exception:
            condiciones = []
        for e in condiciones:
            self.in_condicion.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

    # ---------------- Logic ----------------
    def gather_filters(self) -> Dict[str, Any]:
        anio_txt = self.in_anio.text().strip()
        anio_val = int(anio_txt) if anio_txt.isdigit() else None

        return {
            "marca": self.in_marca.text().strip() or None,
            "modelo": self.in_modelo.text().strip() or None,
            "anio": anio_val,
            "nro_cuadro": self.in_nro_cuadro.text().strip() or None,
            "nro_motor": self.in_nro_motor.text().strip() or None,
            "color_id": self.in_color.currentData(),
            "color": None,  # evita LIKE por nombre
            "estado_stock_id": self.in_estado.currentData(),
            "estado_moto_id": self.in_condicion.currentData(),
        }

    def refresh_from_parent(self):
        """Llamado por MainWindow al volver del detalle."""
        self.reload(reset_page=False)

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
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # ID oculto (col 0)
            id_val = r.get("id", "")
            id_item = QTableWidgetItem(str(id_val))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, id_item)

            # Proveedor (varios posibles nombres desde el repo/consulta)
            proveedor_nombre = (
                r.get("proveedor")
                or r.get("proveedor_nombre")
                or r.get("proveedor_razon_social")
                or r.get("proveedor_nombre_fantasia")
                or ""
            )

            # Visibles (col 1..11, excepto 11 que es Acción)
            values = [
                r.get("marca", ""),
                r.get("modelo", ""),
                str(r.get("anio", "") or ""),
                r.get("numero_cuadro", "") or r.get("nro_cuadro", ""),
                r.get("numero_motor", ""),
                r.get("color", "") or r.get("color_nombre", ""),
                r.get("estado_stock", "") or r.get("estado_stock_nombre", ""),
                r.get("estado_moto", "") or r.get("estado_moto_nombre", "") or r.get("condicion", ""),
                proveedor_nombre,
                self._fmt_currency(r.get("precio_lista")),
            ]
            for col, val in enumerate(values, start=1):
                item = QTableWidgetItem(val if isinstance(val, str) else str(val))
                self.table.setItem(row, col, item)

            # Acción (col 11)
            btn = QPushButton("🔍")
            btn.setObjectName("BtnGhost")
            btn.setToolTip("Consultar")
            btn.setAccessibleName("Consultar")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, vid=int(id_val): self.open_detail.emit(vid))
            self.table.setCellWidget(row, 11, btn)

        self.table.resizeRowsToContents()

    def _fmt_currency(self, v: Any) -> str:
        try:
            return f"$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return ""

    # ---- Events ----
    def on_search_clicked(self):
        self.reload(reset_page=True)

    def on_page_size_changed(self, _idx: int):
        self.page_size = int(self.cmb_page_size.currentData())
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
