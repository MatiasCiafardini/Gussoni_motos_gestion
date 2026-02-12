from __future__ import annotations
from typing import Any, Dict, List, Optional
import app.ui.app_message as popUp
from PySide6.QtCore import Qt, Signal, QSettings, QDate
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QSizePolicy, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QVBoxLayout, QLabel, QHeaderView,
    QAbstractItemView, QListView, QMainWindow, QMenu, QDateEdit, QAbstractSpinBox,
    
)
from pathlib import Path
from app.ui.utils.table_utils import setup_compact_table
from PySide6.QtWidgets import QApplication
ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
from app.services.facturas_service import FacturasService
from app.ui.utils.loading_decorator import with_loading


class FacturasPage(QWidget):
    open_detail = Signal(int)
    # Nueva signal para abrir la pantalla de alta de factura
    open_add = Signal()

    COL_ID = 0
    COL_FECHA = 1
    COL_TIPO = 2
    COL_PTO_VTA = 3
    COL_NUMERO = 4
    COL_CLIENTE = 5
    COL_CUIT = 6
    COL_TOTAL = 7
    COL_ESTADO = 8
    COL_CAE = 9
    COL_CAE_VTO = 10
    COL_OBS = 11
    COL_ACCION = 12

    SETTINGS_HEADER_STATE = "FacturasPage/header_state_v1"
    SETTINGS_HIDDEN_COLS = "FacturasPage/hidden_columns_v1"
    SETTINGS_PAGE_SIZE = "FacturasPage/page_size_v1"

    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None):
        super().__init__(parent)
        self.setObjectName("FacturasPage")
        self.main_window: Optional[QMainWindow] = main_window
        self._already_shown_once = False

        self.service = FacturasService()
        self.settings = QSettings("Gussoni", "SistemaFacturacion")

        # ---- Filtros ----
        self.in_tipo = QComboBox()
        self._setup_combo(self.in_tipo)
        self.in_tipo.addItem("Todos", None)

        # Pto Vta ahora como combo desplegable (como en agregar)
        self.in_pto_vta = QComboBox()
        self._setup_combo(self.in_pto_vta)
        self.in_pto_vta.addItem("Todos", None)

        self.in_numero = QLineEdit()
        self.in_numero.setPlaceholderText("Número")
        self.in_cliente = QLineEdit()
        self.in_cliente.setPlaceholderText("Cliente")
        self.in_cuit = QLineEdit()
        self.in_cuit.setPlaceholderText("CUIT/CUIL")

        self.in_estado = QComboBox()
        self._setup_combo(self.in_estado)
        self.in_estado.addItem("Todos", None)

        # Fechas
        self.in_fecha_desde = QDateEdit()
        self._setup_date(self.in_fecha_desde)
        self.in_fecha_hasta = QDateEdit()
        self._setup_date(self.in_fecha_hasta)
        self._set_default_date_range()

        # Botones
        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.setObjectName("BtnPrimary")
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.setObjectName("BtnGhost")
        self.btn_columnas = QPushButton("Columnas")
        self.btn_columnas.setObjectName("BtnGhost")
        self.btn_sync_arca = QPushButton("Sincronizar con ARCA")
        self.btn_sync_arca.setObjectName("BtnGhost")
        self.btn_agregar = QPushButton("Agregar")
        self.btn_agregar.setObjectName("BtnPrimary")

        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 3)
        grid.setColumnStretch(4, 1)
        grid.setColumnStretch(5, 3)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        # Fila 0
        grid.addWidget(QLabel("Tipo"), 0, 0)
        grid.addWidget(self.in_tipo, 0, 1)
        grid.addWidget(QLabel("Pto Vta"), 0, 2)
        grid.addWidget(self.in_pto_vta, 0, 3)
        grid.addWidget(QLabel("Número"), 0, 4)
        grid.addWidget(self.in_numero, 0, 5)
        # Fila 1
        grid.addWidget(QLabel("Cliente"), 1, 0)
        grid.addWidget(self.in_cliente, 1, 1)
        grid.addWidget(QLabel("CUIT/CUIL"), 1, 2)
        grid.addWidget(self.in_cuit, 1, 3)
        grid.addWidget(QLabel("Estado"), 1, 4)
        grid.addWidget(self.in_estado, 1, 5)
        # Fila 2
        grid.addWidget(QLabel("Fecha desde"), 2, 0)
        grid.addWidget(self.in_fecha_desde, 2, 1)
        grid.addWidget(QLabel("Fecha hasta"), 2, 2)
        grid.addWidget(self.in_fecha_hasta, 2, 3)

        btns_wrap = QWidget()
        h = QHBoxLayout(btns_wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        for b in (self.btn_buscar, self.btn_limpiar, self.btn_columnas, self.btn_sync_arca, self.btn_agregar):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            h.addWidget(b)
        grid.addWidget(btns_wrap, 2, 4, 1, 2)

        # ---- Tabla ----
        self.table = QTableWidget(0, 13, self)
        self.table.setObjectName("DataTable")
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Fecha",
                "Tipo",
                "Pto Vta",
                "Número",
                "Cliente",
                "CUIT/CUIL",
                "Total",
                "Estado",
                "CAE",
                "Vto CAE",
                "Observaciones",
                "Acción",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setSortingEnabled(True)

        # Altura fija de filas y sin word-wrap para que Observaciones no agrande la fila
        setup_compact_table(self.table)


        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_ACCION, QHeaderView.ResizeToContents)

        # Ocultamos ID y Observaciones por defecto
        self.table.setColumnHidden(self.COL_ID, True)
        self.table.setColumnHidden(self.COL_OBS, True)

        # Alinear Total a la derecha
        total_header_item = self.table.horizontalHeaderItem(self.COL_TOTAL)
        if total_header_item:
            total_header_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # ---- Paginación ----
        self.page = 1
        self.total = 0
        self.page_size = int(self.settings.value(self.SETTINGS_PAGE_SIZE, 25))
        self.cmb_page_size = QComboBox()
        self.cmb_page_size.setObjectName("BtnGhost")
        for n in (10, 25, 50, 100):
            self.cmb_page_size.addItem(f"Mostrar: {n}", n)
        idx = (10, 25, 50, 100).index(self.page_size) if self.page_size in (10, 25, 50, 100) else 1
        self.cmb_page_size.setCurrentIndex(idx)

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

        # ---- Layout raíz ----
        root = QVBoxLayout(self)
        root.addLayout(grid)
        root.addWidget(self.table, 1)
        root.addLayout(pager)
        root.setStretch(1, 1)


        # Menú de columnas con estilo propio
        self._column_menu = QMenu(self)
        self._column_menu.setObjectName("ColumnMenu")
        self._build_column_menu()

        # Eventos
        self.btn_buscar.clicked.connect(self.on_search_clicked)
        self.btn_limpiar.clicked.connect(self.on_clear_filters_clicked)
        self.btn_columnas.clicked.connect(self.on_columnas_clicked)
        self.btn_sync_arca.clicked.connect(self.on_sync_arca_clicked)
        self.btn_agregar.clicked.connect(self._abrir_pantalla_agregar)
        self.cmb_page_size.currentIndexChanged.connect(self.on_page_size_changed)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)

        # Doble click en la fila también consulta
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)

        self._load_filter_data()
        self._restore_table_state()

        header.sectionResized.connect(lambda *_: self._save_table_state())
        header.sortIndicatorChanged.connect(lambda *_: self._save_table_state())

    # ---------------- Helpers ----------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        lv = QListView()
        lv.setObjectName("ComboPopup")
        lv.setUniformItemSizes(True)
        lv.setSpacing(2)
        cb.setView(lv)

    def _setup_date(self, de: QDateEdit):
        """Config básica; el estilo visual lo pone theme.py."""
        de.setDisplayFormat("dd/MM/yyyy")
        de.setCalendarPopup(True)
        de.setButtonSymbols(QAbstractSpinBox.NoButtons)
        de.setMinimumDate(QDate(1900, 1, 1))
        de.setMaximumDate(QDate(7999, 12, 31))

    def _set_default_date_range(self):
        """Desde = hoy-1 mes, Hasta = hoy (editable)."""
        today = QDate.currentDate()
        self.in_fecha_hasta.setDate(today)
        self.in_fecha_desde.setDate(today.addMonths(-1))

    def _load_filter_data(self):
        # Tipos de comprobante
        try:
            tipos = self.service.get_tipos_comprobante()
        except Exception:
            tipos = []
        for t in tipos:
            nombre = t.get("nombre") or t.get("codigo") or ""
            tipo_id = t.get("id")   # 👈 USAR ID REAL
            self.in_tipo.addItem(nombre, tipo_id)


        # Estados
        try:
            estados = self.service.get_estados_facturas()
        except Exception:
            estados = []
        for e in estados:
            self.in_estado.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

        # Puntos de venta (como en agregar)
        try:
            pvs = self.service.get_puntos_venta()
        except Exception:
            pvs = []

        self.in_pto_vta.blockSignals(True)
        self.in_pto_vta.clear()
        self.in_pto_vta.addItem("Todos", None)

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
        self.in_pto_vta.setCurrentIndex(0)

    def _build_column_menu(self):
        self._column_menu.clear()
        togglables = [
            (self.COL_FECHA, "Fecha"),
            (self.COL_TIPO, "Tipo"),
            (self.COL_PTO_VTA, "Pto Vta"),
            (self.COL_NUMERO, "Número"),
            (self.COL_CLIENTE, "Cliente"),
            (self.COL_CUIT, "CUIT/CUIL"),
            (self.COL_TOTAL, "Total"),
            (self.COL_ESTADO, "Estado"),
            (self.COL_CAE, "CAE"),
            (self.COL_CAE_VTO, "Vto CAE"),
            (self.COL_OBS, "Observaciones"),
        ]
        for col, title in togglables:
            act = QAction(title, self._column_menu, checkable=True)
            act.setChecked(not self.table.isColumnHidden(col))
            act.toggled.connect(
                lambda checked, c=col: (self.table.setColumnHidden(c, not checked), self._save_table_state())
            )
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
        fd = self.in_fecha_desde.date().toString("yyyy-MM-dd")
        fh = self.in_fecha_hasta.date().toString("yyyy-MM-dd")
        return {
            "tipo_comprobante_id": self.in_tipo.currentData(),
            "pto_vta": self.in_pto_vta.currentData(),
            "numero": (self.in_numero.text().strip() or None),
            "cliente": (self.in_cliente.text().strip() or None),
            "documento": (self.in_cuit.text().strip() or None),
            "estado_id": self.in_estado.currentData(),
            "fecha_desde": fd,
            "fecha_hasta": fh,
        }

    @with_loading("Cargando facturas...")
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

                obs_full = r.get("observaciones", "") or r.get("obs", "") or ""
                # texto visible acotado para no romper la fila
                max_obs_len = 140
                obs_display = obs_full.replace("\n", " ")
                if len(obs_display) > max_obs_len:
                    obs_display = obs_display[:max_obs_len].rstrip() + "..."
                # --- Resolver tipo correctamente ---
                tipo_codigo = r.get("tipo_codigo") or r.get("tipo")
                tipo_nombre = r.get("tipo_nombre")

                if tipo_nombre:
                    tipo_display = tipo_nombre
                else:
                    idx = self.in_tipo.findData(tipo_codigo)
                    tipo_display = self.in_tipo.itemText(idx) if idx >= 0 else str(tipo_codigo or "")

                values = {
                    self.COL_FECHA: self._fmt_date(r.get("fecha")),
                    self.COL_TIPO: tipo_display,
                    self.COL_PTO_VTA: str(r.get("pto_vta", "") or ""),
                    self.COL_NUMERO: str(r.get("numero", "") or ""),
                    self.COL_CLIENTE: r.get("cliente", "") or r.get("cliente_nombre", ""),
                    self.COL_CUIT: r.get("documento", "") or "",
                    self.COL_TOTAL: self._fmt_currency(r.get("total")),
                    self.COL_ESTADO: r.get("estado", "") or r.get("estado_nombre", ""),
                    self.COL_CAE: r.get("cae", "") or "",
                    self.COL_CAE_VTO: self._fmt_date(r.get("vto_cae")),
                    self.COL_OBS: obs_display,
                }

                for col, val in values.items():
                    item = QTableWidgetItem()

                    # 👉 columnas numéricas
                    if col == self.COL_NUMERO:
                        try:
                            item.setData(Qt.DisplayRole, int(val))
                        except Exception:
                            item.setData(Qt.DisplayRole, 0)

                    elif col == self.COL_PTO_VTA:
                        try:
                            item.setData(Qt.DisplayRole, int(val))
                        except Exception:
                            item.setData(Qt.DisplayRole, 0)

                    elif col == self.COL_TOTAL:
                        try:
                            num = float(r.get("total") or 0)
                            item.setData(Qt.DisplayRole, num)
                            item.setText(self._fmt_currency(num))
                            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        except Exception:
                            item.setData(Qt.DisplayRole, 0.0)

                    # 👉 columnas normales (texto)
                    else:
                        item.setData(Qt.DisplayRole, val or "")

                    if col == self.COL_OBS:
                        item.setToolTip(obs_full)

                    self.table.setItem(row, col, item)



                try:
                    fid = int(id_val)
                except Exception:
                    fid = None

                btn = QPushButton("🔍")
                btn.setObjectName("BtnGhost")
                btn.setToolTip("Consultar")
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(
                    lambda _=False, _fid=fid: self._abrir_consultar(_fid)
                )
                self.table.setCellWidget(row, self.COL_ACCION, btn)

            # ya no hacemos resizeRowsToContents() para que la altura quede fija
        finally:
            if was_sorting:
                self.table.setSortingEnabled(True)
            self._save_table_state()

    # ---------------- Utils ----------------
    def _fmt_currency(self, v: Any) -> str:
        try:
            return f"$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return ""

    def _fmt_date(self, v: Any) -> str:
        if not v:
            return ""
        try:
            s = str(v)
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                y, m, d = s[:4], s[5:7], s[8:10]
                return f"{d}/{m}/{y}"
        except Exception:
            pass
        return str(v)

    # ---------------- Navegación / eventos ----------------
    def _abrir_consultar(self, factura_id: Optional[int]) -> None:
        print(">>> Abrir consultar factura_id =", factura_id)

        if factura_id is None:
            print(">>> factura_id es None")
            return

        mw = getattr(self, "main_window", None) or self.window()
        print(">>> main_window =", mw)

        try:
            mw.open_page("facturas_consultar", factura_id=factura_id)
        except Exception as e:
            print(">>> ERROR open_page:", repr(e))


    def _on_table_double_clicked(self, row: int, _col: int) -> None:
        id_item = self.table.item(row, self.COL_ID)
        if not id_item:
            return
        try:
            fid = int(id_item.text())
        except Exception:
            fid = None
        self._abrir_consultar(fid)

    # ---------------- Eventos ----------------
    def on_search_clicked(self):
        self.reload(reset_page=True)

    def on_clear_filters_clicked(self):
        self.in_pto_vta.setCurrentIndex(0)
        for le in (self.in_numero, self.in_cliente, self.in_cuit):
            le.clear()
        self.in_tipo.setCurrentIndex(0)
        self.in_estado.setCurrentIndex(0)
        self._set_default_date_range()
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
        self.open_add.emit()
        mw = getattr(self, "main_window", None) or self.window()
        if not isinstance(mw, QMainWindow):
            return
        try:
            if hasattr(mw, "open_page"):
                mw.open_page("facturas_agregar")
        except Exception:
            pass

    @with_loading("Sincronizando con ARCA...")
    def on_sync_arca_clicked(self):
        print(">>> [FacturasPage] on_sync_arca_clicked: inicio sincronización con ARCA")
        try:
            resumen = self.service.sincronizar_borradores_con_arca()
        except Exception as e:
            print(">>> [FacturasPage] ERROR en sincronizar_borradores_con_arca:", repr(e))
            popUp.toast(
                self,
                f"Ocurrió un error al sincronizar con ARCA:\n{e}",
            )
            return

        print(">>> [FacturasPage] Resumen sincronización:", resumen)

        procesadas = resumen.get("procesadas", 0)
        aprobadas = resumen.get("aprobadas", 0)
        rechazadas = resumen.get("rechazadas", 0)
        errores = resumen.get("error_comunicacion", 0)
        detalles = resumen.get("detalles") or []

        if procesadas == 0 and not detalles:
            popUp.info(
                self,
                "Sincronización con ARCA",
                (
                    "No se encontraron facturas en estado BORRADOR o ERROR DE COMUNICACIÓN "
                    "para sincronizar con ARCA.\n\n"
                    "Recordá que las facturas RECHAZADAS por ARCA no se reenvían desde este botón."
                ),
            )
            self.reload(reset_page=False)
            return

        msg = (
            "Sincronización finalizada.\n\n"
            f"Procesadas: {procesadas}\n"
            f"Aprobadas: {aprobadas}\n"
            f"Rechazadas: {rechazadas}\n"
            f"Errores de comunicación: {errores}"
        )

        if detalles:
            max_lines = 30
            lines = list(detalles)
            preview = "\n".join(lines[:max_lines])
            if len(lines) > max_lines:
                preview += f"\n... ({len(lines) - max_lines} líneas más)"
            msg += "\n\nDetalle:\n" + preview

        popUp.info(self, "Sincronización con ARCA", msg)
        self.reload(reset_page=False)

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
