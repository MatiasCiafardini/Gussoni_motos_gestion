from __future__ import annotations
from typing import Any, Dict, List, Optional
import app.ui.app_message as popUp

from PySide6.QtCore import Qt, Signal, QSettings, QDate
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QSizePolicy, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHBoxLayout, QVBoxLayout, QLabel,
    QHeaderView, QAbstractItemView, QListView, QMainWindow, QMenu,
    QDateEdit, QAbstractSpinBox
)
from PySide6.QtCore import QTimer
from pathlib import Path
from app.ui.utils.table_utils import setup_compact_table
from PySide6.QtWidgets import QApplication

from app.services.remitos_service import RemitosService
from app.ui.utils.loading_decorator import with_loading


class RemitosPage(QWidget):
    open_detail = Signal(int)
    open_add = Signal()

    COL_ID = 0
    COL_FECHA = 1
    COL_PTO_VTA = 2
    COL_NUMERO = 3
    COL_CLIENTE = 4
    COL_ESTADO = 5
    COL_OBS = 6
    COL_ACCION = 7

    SETTINGS_HEADER_STATE = "RemitosPage/header_state_v1"
    SETTINGS_HIDDEN_COLS = "RemitosPage/hidden_columns_v1"
    SETTINGS_PAGE_SIZE = "RemitosPage/page_size_v1"

    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None):
        super().__init__(parent)
        self.setObjectName("RemitosPage")
        self.main_window: Optional[QMainWindow] = main_window

        try:
            self.service = RemitosService()
        except Exception as e:
            print("❌ Error creando RemitosService:", e)
            self.service = None
        self.settings = QSettings("Gussoni", "SistemaFacturacion")

        # ---------------- Filtros ----------------

        self.in_pto_vta = QComboBox()
        self._setup_combo(self.in_pto_vta)
        self.in_pto_vta.addItem("Todos", None)

        self.in_numero = QLineEdit()
        self.in_numero.setPlaceholderText("Número")

        self.in_cliente = QLineEdit()
        self.in_cliente.setPlaceholderText("Cliente")

        self.in_fecha_desde = QDateEdit()
        self._setup_date(self.in_fecha_desde)

        self.in_fecha_hasta = QDateEdit()
        self._setup_date(self.in_fecha_hasta)

        self._set_default_date_range()

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.setObjectName("BtnPrimary")

        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.setObjectName("BtnGhost")

        self.btn_columnas = QPushButton("Columnas")
        self.btn_columnas.setObjectName("BtnGhost")

        self.btn_agregar = QPushButton("Agregar")
        self.btn_agregar.setObjectName("BtnPrimary")

        grid = QGridLayout()
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1); grid.setColumnStretch(3, 3)
        grid.setColumnStretch(4, 1); grid.setColumnStretch(5, 3)
        grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("Pto Vta"), 0, 0)
        grid.addWidget(self.in_pto_vta, 0, 1)
        grid.addWidget(QLabel("Número"), 0, 2)
        grid.addWidget(self.in_numero, 0, 3)
        grid.addWidget(QLabel("Cliente"), 0, 4)
        grid.addWidget(self.in_cliente, 0, 5)

        grid.addWidget(QLabel("Fecha desde"), 1, 0)
        grid.addWidget(self.in_fecha_desde, 1, 1)
        grid.addWidget(QLabel("Fecha hasta"), 1, 2)
        grid.addWidget(self.in_fecha_hasta, 1, 3)

        btns_wrap = QWidget()
        h = QHBoxLayout(btns_wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        for b in (self.btn_buscar, self.btn_limpiar, self.btn_columnas, self.btn_agregar):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            h.addWidget(b)

        grid.addWidget(btns_wrap, 1, 4, 1, 2)

        # ---------------- Tabla ----------------

        self.table = QTableWidget(0, 8, self)
        self.table.setObjectName("DataTable")
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Fecha",
            "Pto Vta",
            "Número",
            "Cliente",
            "Estado",
            "Observaciones",
            "Acción",
        ])

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        setup_compact_table(self.table)

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_ACCION, QHeaderView.ResizeToContents)

        self.table.setColumnHidden(self.COL_ID, True)
        self.table.setColumnHidden(self.COL_OBS, True)

        # ---------------- Paginación ----------------

        self.page = 1
        self.total = 0
        self.page_size = int(self.settings.value(self.SETTINGS_PAGE_SIZE, 25))

        self.cmb_page_size = QComboBox()
        for n in (10, 25, 50, 100):
            self.cmb_page_size.addItem(f"Mostrar: {n}", n)

        self.lbl_pages = QLabel("Página 1/1")
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setObjectName("BtnGhost")
        self.btn_next = QPushButton("▶")
        self.btn_next.setObjectName("BtnGhost")

        pager = QHBoxLayout()
        pager.addWidget(self.cmb_page_size)
        pager.addStretch(1)
        pager.addWidget(self.btn_prev)
        pager.addWidget(self.lbl_pages)
        pager.addWidget(self.btn_next)

        root = QVBoxLayout(self)
        root.addLayout(grid)
        root.addWidget(self.table, 1)
        root.addLayout(pager)

        # ---------------- Eventos ----------------

        self.btn_buscar.clicked.connect(self.on_search_clicked)
        self.btn_limpiar.clicked.connect(self.on_clear_filters_clicked)
        self.btn_columnas.clicked.connect(self.on_columnas_clicked)
        self.btn_agregar.clicked.connect(self._abrir_pantalla_agregar)

        self.cmb_page_size.currentIndexChanged.connect(self.on_page_size_changed)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)

        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)

        

        self._load_filter_data()
        QTimer.singleShot(0, self.reload)

    # ---------------- Helpers ----------------

    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        lv = QListView()
        lv.setUniformItemSizes(True)
        cb.setView(lv)

    def _setup_date(self, de: QDateEdit):
        de.setDisplayFormat("dd/MM/yyyy")
        de.setCalendarPopup(True)
        de.setButtonSymbols(QAbstractSpinBox.NoButtons)

    def _set_default_date_range(self):
        today = QDate.currentDate()
        self.in_fecha_hasta.setDate(today)
        self.in_fecha_desde.setDate(today.addMonths(-1))

    def _load_filter_data(self):
        # Puntos de venta
        # (Si más adelante querés traerlos de BD lo agregamos)
        self.in_pto_vta.clear()
        self.in_pto_vta.addItem("Todos", None)

    # ---------------- Lógica ----------------

    def gather_filters(self) -> Dict[str, Any]:
        return {
            "pto_vta": self.in_pto_vta.currentData(),
            "numero": self.in_numero.text().strip() or None,
            "cliente": self.in_cliente.text().strip() or None,
            "fecha_desde": self.in_fecha_desde.date().toString("yyyy-MM-dd"),
            "fecha_hasta": self.in_fecha_hasta.date().toString("yyyy-MM-dd"),
        }

    @with_loading("Cargando remitos...")
    def reload(self, reset_page: bool = False):

        if reset_page:
            self.page = 1

        filtros = self.gather_filters()

        try:
            rows, total = self.service.search(
                filtros,
                page=self.page,
                page_size=self.page_size,
            )
        except Exception as e:
            print("❌ Error en RemitosPage.reload:", e)
            rows, total = [], 0

        self.total = total
        self.populate_table(rows)

        pages = max((total + self.page_size - 1) // self.page_size, 1)
        self.lbl_pages.setText(f"Página {self.page}/{pages}")

    def populate_table(self, rows: List[Dict[str, Any]]):
        self.table.setRowCount(0)

        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, self.COL_ID, QTableWidgetItem(str(r.get("id"))))
            self.table.setItem(row, self.COL_FECHA, QTableWidgetItem(self._fmt_date(r.get("fecha_emision"))))
            self.table.setItem(row, self.COL_PTO_VTA, QTableWidgetItem(str(r.get("punto_venta") or "")))
            self.table.setItem(row, self.COL_NUMERO, QTableWidgetItem(str(r.get("numero") or "")))
            self.table.setItem(row, self.COL_CLIENTE, QTableWidgetItem(r.get("cliente") or ""))
            self.table.setItem(row, self.COL_ESTADO, QTableWidgetItem(r.get("estado") or ""))

            obs = r.get("observaciones") or ""
            obs_item = QTableWidgetItem(obs[:120] + ("..." if len(obs) > 120 else ""))
            obs_item.setToolTip(obs)
            self.table.setItem(row, self.COL_OBS, obs_item)

            rid = r.get("id")
            btn = QPushButton("🔍")
            btn.setObjectName("BtnGhost")
            btn.clicked.connect(lambda _, _rid=rid: self._abrir_consultar(_rid))
            self.table.setCellWidget(row, self.COL_ACCION, btn)

    # ---------------- Utils ----------------

    def _fmt_date(self, v: Any) -> str:
        if not v:
            return ""
        s = str(v)
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return f"{s[8:10]}/{s[5:7]}/{s[:4]}"
        return s

    # ---------------- Navegación ----------------

    def _abrir_consultar(self, remito_id: Optional[int]):
        if not remito_id:
            return
        mw = getattr(self, "main_window", None) or self.window()
        if hasattr(mw, "open_page"):
            mw.open_page("remitos_detalle", remito_id=remito_id)

    def _on_table_double_clicked(self, row: int, _col: int):
        id_item = self.table.item(row, self.COL_ID)
        if id_item:
            self._abrir_consultar(int(id_item.text()))

    def _abrir_pantalla_agregar(self):
        mw = getattr(self, "main_window", None) or self.window()
        if hasattr(mw, "open_page"):
            mw.open_page("remitos_agregar")

    # ---------------- Eventos ----------------

    def on_search_clicked(self):
        self.reload(reset_page=True)

    def on_clear_filters_clicked(self):
        self.in_pto_vta.setCurrentIndex(0)
        self.in_numero.clear()
        self.in_cliente.clear()
        self._set_default_date_range()
        self.reload(reset_page=True)

    def on_columnas_clicked(self):
        menu = QMenu(self)
        for col in range(1, self.table.columnCount() - 1):
            title = self.table.horizontalHeaderItem(col).text()
            act = QAction(title, menu, checkable=True)
            act.setChecked(not self.table.isColumnHidden(col))
            act.toggled.connect(lambda checked, c=col: self.table.setColumnHidden(c, not checked))
            menu.addAction(act)

        menu.exec(self.btn_columnas.mapToGlobal(self.btn_columnas.rect().bottomLeft()))

    def on_page_size_changed(self, _):
        self.page_size = int(self.cmb_page_size.currentData())
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