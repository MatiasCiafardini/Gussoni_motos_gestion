from __future__ import annotations
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, QSize, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QSizePolicy, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QVBoxLayout, QLabel, QHeaderView, 
    QAbstractItemView, QListView, QMainWindow, QMenu
)
import app.ui.app_message as popUp
# ----- Servicios/Páginas específicas de Clientes -----
from app.services.clientes_service import ClientesService
try:
    from app.ui.pages.clientes_agregar import ClientesAgregarPage
except Exception:
    ClientesAgregarPage = None  # fallback si aún no existe

from app.ui.widgets.loading_overlay import LoadingOverlay
from app.ui.utils.loading_decorator import with_loading


class ClientesPage(QWidget):
    open_detail = Signal(int)

    COL_ID = 0
    COL_TIPO_DOC = 1
    COL_NRO_DOC = 2
    COL_NOMBRE = 3
    COL_APELLIDO = 4
    COL_TELEFONO = 5
    COL_EMAIL = 6
    COL_DIRECCION = 7
    COL_ESTADO = 8
    COL_OBS = 9
    COL_ACCION = 10

    SETTINGS_HEADER_STATE = "ClientesPage/header_state_v1"
    SETTINGS_HIDDEN_COLS = "ClientesPage/hidden_columns_v1"
    SETTINGS_PAGE_SIZE = "ClientesPage/page_size_v1"

    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None):
        super().__init__(parent)
        self.setObjectName("ClientesPage")
        self.main_window: Optional[QMainWindow] = main_window
        self._clientes_agregar_ref: Optional[QWidget] = None

        self.service = ClientesService()
        self.settings = QSettings("Gussoni", "SistemaFacturacion")

        # ---- Filtros ----
        self.in_nombre = QLineEdit(); self.in_nombre.setPlaceholderText("Nombre")
        self.in_apellido = QLineEdit(); self.in_apellido.setPlaceholderText("Apellido")
        self.in_tipo_doc = QComboBox(); self._setup_combo(self.in_tipo_doc); self.in_tipo_doc.addItem("Todos", None)
        # valores comunes; si tu servicio trae catálogo, los sobreescribimos más abajo
        for td in ("DNI", "CUIT", "CUIL", "LE", "LC"):
            self.in_tipo_doc.addItem(td, td)
        self.in_nro_doc = QLineEdit(); self.in_nro_doc.setPlaceholderText("N° documento")

        self.in_email = QLineEdit(); self.in_email.setPlaceholderText("Email")
        self.in_direccion = QLineEdit(); self.in_direccion.setPlaceholderText("Dirección")

        self.in_estado = QComboBox(); self._setup_combo(self.in_estado); self.in_estado.addItem("Todos", None)
        # por defecto
        self.in_estado.addItem("Activo", 1)
        self.in_estado.addItem("Inactivo", 0)

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

        # Fila 0
        grid.addWidget(QLabel("Nombre"), 0, 0);    grid.addWidget(self.in_nombre, 0, 1)
        grid.addWidget(QLabel("Apellido"), 0, 2);  grid.addWidget(self.in_apellido, 0, 3)
        grid.addWidget(QLabel("Tipo doc"), 0, 4);  grid.addWidget(self.in_tipo_doc, 0, 5)

        # Fila 1
        grid.addWidget(QLabel("N° Documento"), 1, 0); grid.addWidget(self.in_nro_doc, 1, 1)
        grid.addWidget(QLabel("Email"), 1, 2);        grid.addWidget(self.in_email, 1, 3)
        grid.addWidget(QLabel("Dirección"), 1, 4);    grid.addWidget(self.in_direccion, 1, 5)

        # Fila 2
        grid.addWidget(QLabel("Estado"), 2, 0);       grid.addWidget(self.in_estado, 2, 1)

        # Botonera
        btns_wrap = QWidget()
        h = QHBoxLayout(btns_wrap); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        for b in (self.btn_buscar, self.btn_limpiar, self.btn_columnas, self.btn_agregar):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            h.addWidget(b)
        grid.addWidget(btns_wrap, 2, 4, 1, 2)

        # ---- Tabla ----
        self.table = QTableWidget(0, 11, self)
        self.table.setObjectName("DataTable")
        self.table.setHorizontalHeaderLabels([
            "ID", "Tipo doc", "N° doc", "Nombre", "Apellido",
            "Teléfono", "Email", "Dirección", "Estado", "Observaciones", "Acción"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_ACCION, QHeaderView.ResizeToContents)

        self.table.setColumnHidden(self.COL_ID, True)
        self.table.setColumnHidden(self.COL_OBS, True)

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

        self.loading_overlay = LoadingOverlay(self, text="")

        self._column_menu = QMenu(self)
        self._build_column_menu()

        # ---- Eventos ----
        self.btn_buscar.clicked.connect(self.on_search_clicked)
        self.btn_limpiar.clicked.connect(self.on_clear_filters_clicked)
        self.btn_columnas.clicked.connect(self.on_columnas_clicked)
        self.btn_agregar.clicked.connect(self._abrir_pantalla_agregar)
        self.cmb_page_size.currentIndexChanged.connect(self.on_page_size_changed)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)

        self._load_filter_data()   # intenta cargar catálogos si existen
        self._restore_table_state()

        header.sectionResized.connect(lambda *_: self._save_table_state())
        header.sortIndicatorChanged.connect(lambda *_: self._save_table_state())

    # ---------------- Helpers ----------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        lv = QListView(); lv.setObjectName("ComboPopup"); lv.setUniformItemSizes(True); lv.setSpacing(2)
        cb.setView(lv)

    def _load_filter_data(self):
        """
        Si tu ClientesService expone catálogos (p. ej. tipos de doc o estados),
        aquí los cargamos. Si falla, dejamos los defaults.
        """
        # Tipos de documento desde el servicio (opcional)
        try:
            tipos = self.service.get_tipos_documento()
            if tipos:
                self.in_tipo_doc.clear()
                self.in_tipo_doc.addItem("Todos", None)
                for t in tipos:
                    self.in_tipo_doc.addItem(t.get("nombre", t.get("codigo", "")) or "", t.get("codigo") or t.get("nombre"))
        except Exception:
            pass

        # Estados (opcional)
        try:
            estados = self.service.get_estados_clientes()
            if estados:
                self.in_estado.clear()
                self.in_estado.addItem("Todos", None)
                for e in estados:
                    self.in_estado.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))
        except Exception:
            pass

    def _build_column_menu(self):
        self._column_menu.clear()
        self._column_menu.setStyleSheet("""
            QMenu {
                background-color: #111827;
                color: #FFFFFF;
                border: 1px solid #1f2937;
                padding: 6px;
            }
            QMenu::item { padding: 6px 12px; background-color: transparent; }
            QMenu::item:selected { background-color: #1f2937; color: #FFFFFF; }
        """)
        togglables = [
            (self.COL_TIPO_DOC, "Tipo doc"), (self.COL_NRO_DOC, "N° doc"),
            (self.COL_NOMBRE, "Nombre"), (self.COL_APELLIDO, "Apellido"),
            (self.COL_TELEFONO, "Teléfono"), (self.COL_EMAIL, "Email"),
            (self.COL_DIRECCION, "Dirección"), (self.COL_ESTADO, "Estado"),
            (self.COL_OBS, "Observaciones"),
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
        return {
            "nombre": self.in_nombre.text().strip() or None,
            "apellido": self.in_apellido.text().strip() or None,
            "tipo_doc": self.in_tipo_doc.currentData(),
            "nro_doc": self.in_nro_doc.text().strip() or None,
            "email": self.in_email.text().strip() or None,
            "direccion": self.in_direccion.text().strip() or None,
            "estado_id": self.in_estado.currentData(),
        }

    @with_loading("Cargando clientes...")
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

                estado_nombre = r.get("estado", "") or r.get("estado_nombre", "")
                if not estado_nombre and r.get("estado_id") is not None:
                    estado_nombre = "Activo" if int(r.get("estado_id")) == 1 else "Inactivo"

                values = {
                    self.COL_TIPO_DOC: r.get("tipo_doc", ""),
                    self.COL_NRO_DOC: r.get("nro_doc", ""),
                    self.COL_NOMBRE: r.get("nombre", ""),
                    self.COL_APELLIDO: r.get("apellido", "") or "",
                    self.COL_TELEFONO: r.get("telefono", "") or "",
                    self.COL_EMAIL: r.get("email", "") or "",
                    self.COL_DIRECCION: r.get("direccion", "") or "",
                    self.COL_ESTADO: estado_nombre,
                    self.COL_OBS: r.get("observaciones", "") or r.get("obs", ""),
                }

                for col, val in values.items():
                    item = QTableWidgetItem(val if isinstance(val, str) else str(val))
                    self.table.setItem(row, col, item)

                btn = QPushButton("🔍"); btn.setObjectName("BtnGhost")
                btn.setToolTip("Consultar"); btn.setCursor(Qt.PointingHandCursor)
                try: cid = int(id_val)
                except Exception: cid = None
                btn.clicked.connect(lambda _=False, _cid=cid: (self.open_detail.emit(_cid) if _cid is not None else None))
                self.table.setCellWidget(row, self.COL_ACCION, btn)

            self.table.resizeRowsToContents()
        finally:
            if was_sorting:
                self.table.setSortingEnabled(True)
            self._save_table_state()

    def on_search_clicked(self): self.reload(reset_page=True)

    def on_clear_filters_clicked(self):
        for le in (self.in_nombre, self.in_apellido, self.in_nro_doc, self.in_email, self.in_direccion):
            le.clear()
        self.in_tipo_doc.setCurrentIndex(0)
        self.in_estado.setCurrentIndex(0)
        self.reload(reset_page=True)

    def on_columnas_clicked(self):
        self._build_column_menu()
        self._column_menu.exec(self.btn_columnas.mapToGlobal(self.btn_columnas.rect().bottomLeft()))

    def _abrir_pantalla_agregar(self):
        mw = getattr(self, "main_window", None) or self.window()
        if not isinstance(mw, QMainWindow):
            popUp.critical(self, "Error", "No pude abrir la pantalla de alta (MainWindow no disponible).")
            return

        if ClientesAgregarPage is None:
            popUp.info(self, "Clientes", "La pantalla de alta de clientes aún no está disponible.")
            return

        if self._clientes_agregar_ref is None:
            page = ClientesAgregarPage(mw)
            if hasattr(page, "go_back") and hasattr(mw, "open_page"):
                page.go_back.connect(lambda: mw.open_page("clientes"))
            if hasattr(page, "go_to_detalle") and hasattr(mw, "open_page"):
                page.go_to_detalle.connect(lambda cid: mw.open_page("clientes_detalle", cliente_id=cid))
            self._clientes_agregar_ref = page
            if hasattr(mw, "_mount") and callable(mw._mount):
                mw.stack.setCurrentWidget(mw._mount(page))
            else:
                if mw.stack.indexOf(page) == -1: mw.stack.addWidget(page)
                mw.stack.setCurrentWidget(page)
        else:
            page = self._clientes_agregar_ref
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
