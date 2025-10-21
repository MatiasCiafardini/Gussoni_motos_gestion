from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal, QSize, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QSizePolicy, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QVBoxLayout, QLabel, QHeaderView, QMessageBox,
    QAbstractItemView, QListView, QMainWindow, QMenu
)
# Usamos loguru para el logging, como se usa en el resto de la aplicación [29]
from loguru import logger 

# ----- Servicios/Páginas específicas de Usuarios (Asumiendo que existen) -----
# Reemplace esto con la ruta correcta a su servicio de usuarios
from app.services.usuarios_service import UsuariosService 
from app.ui.pages.usuarios_agregar import UsuariosAgregarPage
from app.ui.widgets.loading_overlay import LoadingOverlay # Widget existente [3]
from app.ui.utils.loading_decorator import with_loading # Decorador existente [3]

class UsuariosPage(QWidget):
    open_detail = Signal(int)

    # 1. Definición de Columnas de la Tabla de Usuarios
    COL_ID = 0
    COL_NOMBRE = 1
    COL_USUARIO = 2
    COL_ROL = 3
    COL_EMAIL = 4
    COL_ACTIVO = 5
    COL_FECHA_CREACION = 6
    COL_ACCION = 7 
    
    COL_COUNT = 8 # Total de columnas (7 datos + 1 acción)

    # 2. Configuración de Guardado de Estado  [4, 30]
    SETTINGS_HEADER_STATE = "UsuariosPage/header_state_v1"
    SETTINGS_HIDDEN_COLS = "UsuariosPage/hidden_columns_v1"
    SETTINGS_PAGE_SIZE = "UsuariosPage/page_size_v1"

    def __init__(self, parent=None, main_window: Optional[QMainWindow] = None):
        super().__init__(parent)
        self.setObjectName("UsuariosPage")
        self.main_window: Optional[QMainWindow] = main_window
        self._usuarios_agregar_ref: Optional[QWidget] = None
        self.service = UsuariosService()
        self.settings = QSettings("Gussoni", "SistemaFacturacion") # Nombre de la organización [4]

        # ---- Filtros ----
        
        # Filtros de texto
        self.in_nombre = QLineEdit(); self.in_nombre.setPlaceholderText("Nombre")
        self.in_usuario = QLineEdit(); self.in_usuario.setPlaceholderText("Usuario")
        self.in_email = QLineEdit(); self.in_email.setPlaceholderText("Email")

        # Filtros Combo Box
        self.in_rol = QComboBox(); self._setup_combo(self.in_rol); self.in_rol.addItem("Todos", None)
        # Roles por defecto
        self.in_rol.addItem("Administrador", "admin")
        self.in_rol.addItem("Vendedor", "vendedor")
        self.in_rol.addItem("Técnico", "tecnico")

        self.in_activo = QComboBox(); self._setup_combo(self.in_activo); self.in_activo.addItem("Todos", None)
        self.in_activo.addItem("Activo", 1) # 1
        self.in_activo.addItem("Inactivo", 0) # 0

        # Botones [6, 7]
        self.btn_buscar = QPushButton("Buscar"); self.btn_buscar.setObjectName("BtnPrimary")
        self.btn_limpiar = QPushButton("Limpiar"); self.btn_limpiar.setObjectName("BtnGhost")
        self.btn_columnas = QPushButton("Columnas"); self.btn_columnas.setObjectName("BtnGhost")
        self.btn_agregar = QPushButton("Agregar"); self.btn_agregar.setObjectName("BtnPrimary")

        # ---- Layout de Filtros (Grid) ---- [7, 8]
        grid = QGridLayout()
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1); grid.setColumnStretch(3, 3)
        grid.setColumnStretch(4, 1); grid.setColumnStretch(5, 3)
        grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)

        # Fila 0 (3 filtros)
        grid.addWidget(QLabel("Nombre"), 0, 0); grid.addWidget(self.in_nombre, 0, 1)
        grid.addWidget(QLabel("Usuario"), 0, 2); grid.addWidget(self.in_usuario, 0, 3)
        grid.addWidget(QLabel("Email"), 0, 4); grid.addWidget(self.in_email, 0, 5)

        # Fila 1 (2 filtros y 4 botones)
        grid.addWidget(QLabel("Rol"), 1, 0); grid.addWidget(self.in_rol, 1, 1)
        grid.addWidget(QLabel("Estado"), 1, 2); grid.addWidget(self.in_activo, 1, 3)

        # Botonera [9]
        btns_wrap = QWidget()
        h = QHBoxLayout(btns_wrap); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        for b in (self.btn_buscar, self.btn_limpiar, self.btn_columnas, self.btn_agregar):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            h.addWidget(b)
        grid.addWidget(btns_wrap, 1, 4, 1, 2) 

        # ---- Tabla ----
        self.table = QTableWidget(0, self.COL_COUNT, self)
        self.table.setObjectName("DataTable")
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Usuario", "Rol", "Email",
            "Activo", "Fecha Creación", "Acción"
        ])
        
        # Propiedades de tabla copiadas de las fuentes [10, 31]
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_ACCION, QHeaderView.ResizeToContents)
        self.table.setColumnHidden(self.COL_ID, True) # Ocultar ID [11]

        # ---- Paginación ---- [11, 12]
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

        # ---- Layout raíz ---- [12, 13]
        root = QVBoxLayout(self)
        root.addLayout(grid)
        root.addWidget(self.table, 1)
        root.addLayout(pager)
        root.setStretch(1, 1)
        
        self.loading_overlay = LoadingOverlay(self, text="")
        self._column_menu = QMenu(self)
        self._build_column_menu()

        # ---- Eventos ---- [13]
        self.btn_buscar.clicked.connect(self.on_search_clicked)
        self.btn_limpiar.clicked.connect(self.on_clear_filters_clicked)
        self.btn_columnas.clicked.connect(self.on_columnas_clicked)
        self.btn_agregar.clicked.connect(self._abrir_pantalla_agregar)
        self.cmb_page_size.currentIndexChanged.connect(self.on_page_size_changed)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)

        # Carga inicial y restauración de estado [14]
        # self._load_filter_data() # No se implementa ya que no tenemos catálogos de usuarios en las fuentes
        self._restore_table_state()
        header.sectionResized.connect(lambda *_: self._save_table_state())
        header.sortIndicatorChanged.connect(lambda *_: self._save_table_state())

    # ---------------- Helpers & UI Lógica  ----------------
    
    # [14]
    def _setup_combo(self, cb: QComboBox):
        """Helper para estilizar los QComboBoxes de filtro."""
        cb.setObjectName("FilterCombo")
        lv = QListView(); lv.setObjectName("ComboPopup"); lv.setUniformItemSizes(True); lv.setSpacing(2)
        cb.setView(lv)

    # [16, 32]
    def _build_column_menu(self):
        """Crea el menú de columnas visibles/ocultas."""
        self._column_menu.clear()
        self._column_menu.setStyleSheet("""
            QMenu { background-color: #111827; color: #FFFFFF; border: 1px solid #1f2937; padding: 6px; }
            QMenu::item { padding: 6px 12px; background-color: transparent; }
            QMenu::item:selected { background-color: #1f2937; color: #FFFFFF; }
        """)

        togglables = [
            (self.COL_NOMBRE, "Nombre"), (self.COL_USUARIO, "Usuario"),
            (self.COL_ROL, "Rol"), (self.COL_EMAIL, "Email"),
            (self.COL_ACTIVO, "Activo"), (self.COL_FECHA_CREACION, "Fecha Creación"),
        ]
        
        for col, title in togglables:
            act = QAction(title, self._column_menu, checkable=True)
            act.setChecked(not self.table.isColumnHidden(col))
            act.toggled.connect(lambda checked, c=col: (self.table.setColumnHidden(c, not checked), self._save_table_state()))
            self._column_menu.addAction(act)

    # [18, 33]
    def _save_table_state(self):
        """Guarda el estado de la tabla (columnas, ancho, orden)."""
        try:
            state = self.table.horizontalHeader().saveState()
            self.settings.setValue(self.SETTINGS_HEADER_STATE, state)
            hidden = [i for i in range(self.table.columnCount()) if self.table.isColumnHidden(i)]
            self.settings.setValue(self.SETTINGS_HIDDEN_COLS, hidden)
            self.settings.setValue(self.SETTINGS_PAGE_SIZE, self.page_size)
        except Exception:
            logger.error("Error al guardar estado de la tabla de usuarios.") # Uso de logger [29]
            pass
            
    # [19, 34]
    def _restore_table_state(self):
        """Restaura el estado de la tabla al inicio."""
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
            # No hay COL_OBS en usuarios, solo limpiamos el ID
        except Exception:
            self.table.setColumnHidden(self.COL_ID, True)

    # ---------------- Lógica de Datos y ABM ---------------- [20]

    def gather_filters(self) -> Dict[str, Any]:
        """
        Recopila los filtros de la interfaz. 
        Se combina Nombre y Email en `nombre_o_email` para el servicio, 
        y se usa Usuario como filtro independiente.
        """
        nombre_input = self.in_nombre.text().strip()
        email_input = self.in_email.text().strip()
        
        # Si el service espera nombre_o_email:
        nombre_o_email_val = nombre_input or email_input or None
        
        return {
            "usuario": self.in_usuario.text().strip() or None,
            "nombre_o_email": nombre_o_email_val, 
            "rol": self.in_rol.currentData(),
            "activo": self.in_activo.currentData(),
        }

    @with_loading("Cargando usuarios...") # Decorador existente [20, 35]
    def reload(self, reset_page: bool = False):
        """Ejecuta la búsqueda de usuarios."""
        if reset_page:
            self.page = 1

        filtros = self.gather_filters()
        
        rows, total = self.service.search(filtros, page=self.page, page_size=self.page_size) [21]
        
        self.total = total
        self.populate_table(rows)
        
        # Lógica de paginación [21, 36]
        pages = max((total + self.page_size - 1) // self.page_size, 1)
        self.lbl_pages.setText(f"Página {self.page}/{pages}")
        self.btn_prev.setEnabled(self.page > 1)
        self.btn_next.setEnabled(self.page < pages)

    def populate_table(self, rows: List[Dict[str, Any]]):
        """Llena la tabla con los datos de usuarios.""" [22, 36]
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

                # Mapeo de Activo (0/1) a texto [22]
                activo_val = r.get("activo")
                activo_str = "Activo" if activo_val in (1, True, "1") else "Inactivo" 
                
                values = {
                    self.COL_NOMBRE: r.get("nombre", ""),
                    self.COL_USUARIO: r.get("usuario", ""),
                    self.COL_ROL: r.get("rol", "") or "N/A",
                    self.COL_EMAIL: r.get("email", ""),
                    self.COL_ACTIVO: activo_str,
                    self.COL_FECHA_CREACION: str(r.get("fecha_creacion", "") or ""),
                }

                for col, val in values.items():
                    item = QTableWidgetItem(val if isinstance(val, str) else str(val))
                    self.table.setItem(row, col, item)

                # Botón de Acción (Consultar/Editar) [23, 24, 37]
                btn = QPushButton("🔍"); btn.setObjectName("BtnGhost")
                btn.setToolTip("Consultar/Editar"); btn.setCursor(Qt.PointingHandCursor)
                try: uid = int(id_val)
                except Exception: uid = None
                
                # Conexión del botón a la señal open_detail
                btn.clicked.connect(lambda _=False, _uid=uid: (self.open_detail.emit(_uid) if _uid is not None else None)) 
                self.table.setCellWidget(row, self.COL_ACCION, btn)

            self.table.resizeRowsToContents()
        finally:
            if was_sorting:
                self.table.setSortingEnabled(True)
            self._save_table_state()

    def on_search_clicked(self): self.reload(reset_page=True)
    
    # [25]
    def on_clear_filters_clicked(self):
        """Limpia todos los campos de filtro."""
        for le in (self.in_nombre, self.in_usuario, self.in_email):
            le.clear()
        self.in_rol.setCurrentIndex(0)
        self.in_activo.setCurrentIndex(0)
        self.reload(reset_page=True)

    def on_columnas_clicked(self):
        self._build_column_menu()
        self._column_menu.exec(self.btn_columnas.mapToGlobal(self.btn_columnas.rect().bottomLeft()))

    # Lógica de navegación compleja
    def _abrir_pantalla_agregar(self):
        """Abre la pantalla de alta de usuarios."""
        mw = getattr(self, "main_window", None) or self.window()

        if not isinstance(mw, QMainWindow):
            QMessageBox.critical(self, "Error", "No pude abrir la pantalla de alta (MainWindow no disponible).")
            return

        if UsuariosAgregarPage is None:
            QMessageBox.information(self, "Usuarios", "La pantalla de alta de usuarios aún no está disponible.")
            return

        if self._usuarios_agregar_ref is None:
            page = UsuariosAgregarPage(mw)
            
            # Conexión de señales (asumiendo que existen)
            if hasattr(page, "go_back") and hasattr(mw, "open_page"):
                page.go_back.connect(lambda: mw.open_page("usuarios"))
            if hasattr(page, "go_to_detalle") and hasattr(mw, "open_page"):
                page.go_to_detalle.connect(lambda uid: mw.open_page("usuarios_detalle", user_id=uid))
            self._usuarios_agregar_ref = page
            
            # Montaje en el stack de la ventana principal
            if hasattr(mw, "_mount") and callable(mw._mount):
                mw.stack.setCurrentWidget(mw._mount(page))
            else:
                if mw.stack.indexOf(page) == -1: mw.stack.addWidget(page)
                mw.stack.setCurrentWidget(page)
        else:
            page = self._usuarios_agregar_ref
            
            # Limpiar formulario si el método existe [27, 38]
            if hasattr(page, "_limpiar_formulario"):
                try: page._limpiar_formulario()
                except Exception: pass

            if hasattr(mw, "_mount") and callable(mw._mount):
                mw.stack.setCurrentWidget(mw._mount(page))
            else:
                mw.stack.setCurrentWidget(page)
    
    # ---- Lógica de Paginación ---- [28, 38, 39]
    
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