from __future__ import annotations
from typing import Any, Dict, List, Optional

from loguru import logger

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QSizePolicy, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QVBoxLayout, QLabel, QHeaderView, QMessageBox,
    QAbstractItemView, QListView, QMainWindow, QMenu
)

from app.services.usuarios_service import UsuariosService
from app.ui.pages.usuarios_agregar import UsuariosAgregarPage
from app.ui.widgets.loading_overlay import LoadingOverlay
from app.ui.utils.loading_decorator import with_loading


class UsuariosPage(QWidget):
    open_detail = Signal(int)

    # Columnas
    COL_ID = 0
    COL_NOMBRE = 1
    COL_USERNAME = 2
    COL_ROL = 3
    COL_ESTADO = 4
    COL_EMAIL = 5
    COL_OBS = 6
    COL_ACCION = 7

    SETTINGS_HEADER_STATE = "UsuariosPage/header_state_v1"
    SETTINGS_HIDDEN_COLS = "UsuariosPage/hidden_columns_v1"
    SETTINGS_PAGE_SIZE = "UsuariosPage/page_size_v1"

    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None):
        super().__init__(parent)
        self.setObjectName("UsuariosPage")
        self.main_window: Optional[QMainWindow] = main_window
        self._usuarios_agregar_ref: Optional[UsuariosAgregarPage] = None

        self.service = UsuariosService()
        self.settings = QSettings("Gussoni", "SistemaFacturacion")

        # ---- Filtros ----
        self.in_nombre = QLineEdit();   self.in_nombre.setPlaceholderText("Nombre")
        self.in_username = QLineEdit(); self.in_username.setPlaceholderText("Usuario")
        self.in_email = QLineEdit();    self.in_email.setPlaceholderText("Email")

        # Combos dinámicos
        self.in_rol = QComboBox();     self._setup_combo(self.in_rol);     self.in_rol.addItem("Todos", None)
        self.in_estado = QComboBox();  self._setup_combo(self.in_estado);  self.in_estado.addItem("Todos", None)

        # Botones
        self.btn_buscar = QPushButton("Buscar");   self.btn_buscar.setObjectName("BtnPrimary")
        self.btn_limpiar = QPushButton("Limpiar"); self.btn_limpiar.setObjectName("BtnGhost")
        self.btn_columnas = QPushButton("Columnas"); self.btn_columnas.setObjectName("BtnGhost")
        self.btn_agregar = QPushButton("Agregar"); self.btn_agregar.setObjectName("BtnPrimary")

        grid = QGridLayout()
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1); grid.setColumnStretch(3, 3)
        grid.setColumnStretch(4, 1); grid.setColumnStretch(5, 3)
        grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)

        # Filtros
        grid.addWidget(QLabel("Nombre"),   0, 0); grid.addWidget(self.in_nombre,   0, 1)
        grid.addWidget(QLabel("Usuario"),  0, 2); grid.addWidget(self.in_username, 0, 3)
        grid.addWidget(QLabel("Email"),    0, 4); grid.addWidget(self.in_email,    0, 5)
        grid.addWidget(QLabel("Rol"),      1, 0); grid.addWidget(self.in_rol,      1, 1)
        grid.addWidget(QLabel("Estado"),   1, 2); grid.addWidget(self.in_estado,   1, 3)

        btns_wrap = QWidget()
        h = QHBoxLayout(btns_wrap); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        for b in (self.btn_buscar, self.btn_limpiar, self.btn_columnas, self.btn_agregar):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            h.addWidget(b)
        grid.addWidget(btns_wrap, 1, 4, 1, 2)

        # ---- Tabla ----
        self.table = QTableWidget(0, 8, self)
        self.table.setObjectName("DataTable")
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Usuario", "Rol", "Estado", "Email", "Observaciones", "Acción"
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

        # Doble click abre detalle
        self.table.cellDoubleClicked.connect(self._on_row_dblclick)

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

        # Conexiones
        self.btn_buscar.clicked.connect(self.on_search_clicked)
        self.btn_limpiar.clicked.connect(self.on_clear_filters_clicked)
        self.btn_columnas.clicked.connect(self.on_columnas_clicked)
        self.btn_agregar.clicked.connect(self._abrir_pantalla_agregar)
        self.cmb_page_size.currentIndexChanged.connect(self.on_page_size_changed)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)

        # Conectar señal de abrir detalle
        self.open_detail.connect(self._open_detalle)

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
        try: roles = self.service.get_roles()
        except Exception: roles = []
        for r in roles:
            self.in_rol.addItem(r.get("nombre", f"ID {r.get('id')}"), r.get("id"))

        try: estados = self.service.get_estados()
        except Exception: estados = []
        for e in estados:
            self.in_estado.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

    def _build_column_menu(self):
        self._column_menu.clear()
        self._column_menu.setStyleSheet("""
            QMenu {
                background-color: #111827;
                color: #FFFFFF;
                border: 1px solid #1f2937;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 12px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #1f2937;
                color: #FFFFFF;
            }
        """)
        togglables = [
            (self.COL_NOMBRE, "Nombre"), (self.COL_USERNAME, "Usuario"),
            (self.COL_ROL, "Rol"), (self.COL_ESTADO, "Estado"),
            (self.COL_EMAIL, "Email"),
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
            "username": self.in_username.text().strip() or None,
            "email": self.in_email.text().strip() or None,
            "rol_id": self.in_rol.currentData(),
            "estado_id": self.in_estado.currentData(),
        }

    @with_loading("Cargando usuarios...")
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

                id_val = r.get("id") or r.get("usuario_id") or r.get("id_usuario")
                try:
                    uid = int(id_val) if id_val is not None else None
                except Exception:
                    uid = None

                id_item = QTableWidgetItem("" if uid is None else str(uid))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, self.COL_ID, id_item)

                values = {
                    self.COL_NOMBRE: r.get("nombre", ""),
                    self.COL_USERNAME: r.get("username", "") or r.get("usuario", ""),
                    self.COL_ROL: r.get("rol", "") or r.get("rol_nombre", ""),
                    self.COL_ESTADO: r.get("estado", "") or r.get("estado_nombre", ""),
                    self.COL_EMAIL: r.get("email", ""),
                    self.COL_OBS: r.get("observaciones", "") or r.get("obs", ""),
                }
                for col, val in values.items():
                    item = QTableWidgetItem(val if isinstance(val, str) else str(val))
                    self.table.setItem(row, col, item)

                # --- Botón Consultar (idéntico a VehiculosPage) ---
                btn = QPushButton("🔍"); btn.setObjectName("BtnGhost")
                btn.setToolTip("Consultar"); btn.setCursor(Qt.PointingHandCursor)
                try:
                    _uid = int(uid) if uid is not None else None
                except Exception:
                    _uid = None
                btn.clicked.connect(lambda _=False, _uid=_uid: (self.open_detail.emit(_uid) if _uid is not None else None))
                self.table.setCellWidget(row, self.COL_ACCION, btn)

            self.table.resizeRowsToContents()
        finally:
            if was_sorting:
                self.table.setSortingEnabled(True)
            self._save_table_state()

    # --- Navegación / acciones ---
    def _on_row_dblclick(self, row: int, _col: int):
        item = self.table.item(row, self.COL_ID)
        if not item:
            return
        try:
            uid = int(item.text())
        except Exception:
            return
        self._open_detalle(uid)

    def on_search_clicked(self): self.reload(reset_page=True)

    def on_clear_filters_clicked(self):
        for le in (self.in_nombre, self.in_username, self.in_email):
            le.clear()
        self.in_rol.setCurrentIndex(0); self.in_estado.setCurrentIndex(0)
        self.reload(reset_page=True)

    def on_columnas_clicked(self):
        self._build_column_menu()
        self._column_menu.exec(self.btn_columnas.mapToGlobal(self.btn_columnas.rect().bottomLeft()))

    def _abrir_pantalla_agregar(self):
        mw = getattr(self, "main_window", None) or self.window()
        if not isinstance(mw, QMainWindow):
            QMessageBox.critical(self, "Error", "No pude abrir la pantalla de alta (MainWindow no disponible).")
            return
        if self._usuarios_agregar_ref is None:
            page = UsuariosAgregarPage(parent=mw, main_window=mw)
            if hasattr(page, "go_back") and hasattr(mw, "open_page"):
                page.go_back.connect(lambda: mw.open_page("usuarios"))
            if hasattr(page, "go_to_detalle") and hasattr(mw, "open_page"):
                page.go_to_detalle.connect(lambda uid: mw.open_page("usuarios_detalle", usuario_id=uid))
            self._usuarios_agregar_ref = page
            if hasattr(mw, "_mount") and callable(mw._mount):
                mw.stack.setCurrentWidget(mw._mount(page))
            else:
                if mw.stack.indexOf(page) == -1: mw.stack.addWidget(page)
                mw.stack.setCurrentWidget(page)
        else:
            page = self._usuarios_agregar_ref
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

    # -------- Ir al detalle --------
    def _open_detalle(self, user_id: int):
        logger.debug(f"Abrir detalle usuario id={user_id}")
        mw = getattr(self, "main_window", None) or self.window()
        if not isinstance(mw, QMainWindow):
            QMessageBox.critical(self, "Error", "No pude abrir el detalle (MainWindow no disponible).")
            return

        # Ruta preferida (si tu MainWindow tiene router)
        if hasattr(mw, "open_page") and callable(mw.open_page):
            try:
                mw.open_page("usuarios_detalle", usuario_id=user_id)
                return
            except Exception as e:
                logger.exception("Falló mw.open_page('usuarios_detalle')")
                QMessageBox.critical(self, "Error", f"No pude abrir el detalle.\n\n{e}")
                return

        # Fallback: crear la página manualmente
        try:
            from app.ui.pages.usuarios_detail_page import UsuariosDetailPage
            # Constructor de tu clase: UsuariosDetailPage(Usuario_id, parent)
            page = UsuariosDetailPage(Usuario_id=user_id, parent=mw)
            page.setObjectName("UsuariosDetailPage")
            if hasattr(mw, "_mount") and callable(mw._mount):
                mw.stack.setCurrentWidget(mw._mount(page))
            else:
                if mw.stack.indexOf(page) == -1:
                    mw.stack.addWidget(page)
                mw.stack.setCurrentWidget(page)
        except Exception as e:
            logger.exception("Creación de UsuariosDetailPage falló")
            QMessageBox.critical(self, "Error", f"No pude crear UsuariosDetailPage.\n\n{e}")
