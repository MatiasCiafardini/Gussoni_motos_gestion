from __future__ import annotations
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QThreadPool, QRunnable, QObject, Signal

# -------- Páginas actuales del proyecto (con fallback a placeholders) --------
try:
    from app.ui.pages.dashboard_page import DashboardPage  # tu dashboard real
except Exception:
    from app.ui.pages.placeholder_page import PlaceholderPage as DashboardPage

from app.ui.pages.placeholder_page import PlaceholderPage

# =================== VEHÍCULOS ===================
VehiculosPage = None
try:
    from app.ui.pages.vehiculos_page import VehiculosPage as _VehiculosPage
    VehiculosPage = _VehiculosPage
except Exception:
    VehiculosPage = None

VehiculoDetailPage = None
try:
    from app.ui.pages.vehiculos_detail_page import VehiculoDetailPage as _VehiculoDetailPage
    VehiculoDetailPage = _VehiculoDetailPage
except Exception:
    VehiculoDetailPage = None

VehiculosAgregarPage = None
try:
    from app.ui.pages.vehiculos_agregar import VehiculosAgregarPage as _VehiculosAgregarPage
    VehiculosAgregarPage = _VehiculosAgregarPage
except Exception:
    VehiculosAgregarPage = None

# =================== CLIENTES ===================
ClientesPage = None
try:
    from app.ui.pages.clientes_page import ClientesPage as _ClientesPage
    ClientesPage = _ClientesPage
except Exception:
    ClientesPage = None

ClientesDetailPage = None
try:
    from app.ui.pages.clientes_detail_page import ClientesDetailPage as _ClientesDetailPage
    ClientesDetailPage = _ClientesDetailPage
except Exception:
    ClientesDetailPage = None

ClientesAgregarPage = None
try:
    from app.ui.pages.clientes_agregar import ClientesAgregarPage as _ClientesAgregarPage
    ClientesAgregarPage = _ClientesAgregarPage
except Exception:
    ClientesAgregarPage = None

# =================== FACTURACIÓN ===================
FacturacionPage = None
try:
    from app.ui.pages.facturas_page import FacturasPage as _FacturacionPage
    FacturacionPage = _FacturacionPage
except Exception:
    FacturacionPage = None

# =================== CONFIGURACIÓN (cards) ===================
ConfiguracionPage = None
try:
    from app.ui.pages.configuracion_page import ConfiguracionPage as _ConfiguracionPage
    ConfiguracionPage = _ConfiguracionPage
except Exception:
    ConfiguracionPage = None

# =================== USUARIOS ===================
UsuariosPage = None
try:
    from app.ui.pages.usuarios_page import UsuariosPage as _UsuariosPage
    UsuariosPage = _UsuariosPage
except Exception:
    UsuariosPage = None

UsuariosDetailPage = None
try:
    from app.ui.pages.usuarios_detail_page import UsuariosDetailPage as _UsuariosDetailPage
    UsuariosDetailPage = _UsuariosDetailPage
except Exception:
    UsuariosDetailPage = None

UsuariosAgregarPage = None
try:
    from app.ui.pages.usuarios_agregar import UsuariosAgregarPage as _UsuariosAgregarPage
    UsuariosAgregarPage = _UsuariosAgregarPage
except Exception:
    UsuariosAgregarPage = None

# NotifyPopup propio
from app.ui.notify import NotifyPopup

# ==== Warmup de catálogos (carga en background) ====
from app.services.catalogos_service import CatalogosService
from app.core.catalog_cache import CatalogCache


class _WarmupSignals(QObject):
    done = Signal(dict)
    error = Signal(str)


class _WarmupTask(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = _WarmupSignals()

    def run(self):
        try:
            data = CatalogosService().warmup_all()
            self.signals.done.emit(data)
        except Exception as e:
            self.signals.error.emit(str(e))


class MainWindow(QMainWindow):
    """
    Ventana principal con Sidebar + QStackedWidget.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestión de Motos")
        self.resize(1100, 720)
        self.setObjectName("MainWindow")

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # =============== Sidebar ===============
        sidebar = QFrame(self)
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sbl = QVBoxLayout(sidebar)
        sbl.setContentsMargins(14, 14, 14, 14)
        sbl.setSpacing(10)

        title = QLabel("Agencia Motos", sidebar)
        title.setObjectName("SideTitle")
        title.setAlignment(Qt.AlignHCenter)
        sbl.addWidget(title)

        self.btn_inicio       = self._mk_btn("Inicio")
        self.btn_clientes     = self._mk_btn("Clientes")
        self.btn_vehiculos    = self._mk_btn("Vehículos")
        self.btn_facturacion  = self._mk_btn("Facturación")
        self.btn_proveedores  = self._mk_btn("Proveedores")
        self.btn_reportes     = self._mk_btn("Reportes")
        self.btn_config       = self._mk_btn("Configuración")

        for b in (
            self.btn_inicio, self.btn_clientes, self.btn_vehiculos, self.btn_facturacion,
            self.btn_proveedores, self.btn_reportes, self.btn_config
        ):
            sbl.addWidget(b)
        sbl.addStretch(1)

        # =============== Stack + historial ===============
        self.stack = QStackedWidget(self)
        self._page_history: list[QWidget] = []

        self._vehiculos_agregar_ref: Optional[Widget] = None
        self._clientes_agregar_ref: Optional[QWidget] = None

        # Páginas fijas
        self.page_inicio = DashboardPage() if DashboardPage else PlaceholderPage("Inicio")
        self.page_clientes = self._make_clientes_page()
        self.page_vehiculos = self._make_vehiculos_page()
        self.page_facturacion = self._make_facturacion_page()

        try:
            from app.ui.pages.proveedores_page import ProveedoresPage
            self.page_proveedores = ProveedoresPage()
        except Exception:
            self.page_proveedores = PlaceholderPage("Proveedores")

        self.page_reportes = PlaceholderPage("Reportes")
        self.page_config = self._make_configuracion_page()

        for p in (
            self.page_inicio, self.page_clientes, self.page_vehiculos, self.page_facturacion,
            self.page_proveedores, self.page_reportes, self.page_config
        ):
            self.stack.addWidget(p)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)

        # Conexiones menú
        self.btn_inicio.clicked.connect(lambda: self.show_fixed_page(self.page_inicio))
        self.btn_clientes.clicked.connect(lambda: self.show_fixed_page(self.page_clientes))
        self.btn_vehiculos.clicked.connect(lambda: self.show_fixed_page(self.page_vehiculos))
        self.btn_facturacion.clicked.connect(lambda: self.show_fixed_page(self.page_facturacion))
        self.btn_proveedores.clicked.connect(lambda: self.show_fixed_page(self.page_proveedores))
        self.btn_reportes.clicked.connect(lambda: self.show_fixed_page(self.page_reportes))
        self.btn_config.clicked.connect(lambda: self.show_fixed_page(self.page_config))
        self.btn_inicio.setChecked(True)

        # =============== Toast simple (overlay) ===============
        self._toast = QLabel("", self)
        self._toast.setObjectName("Toast")
        self._toast.setVisible(False)
        self._toast.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._toast.setAlignment(Qt.AlignCenter)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast.setVisible(False))

        self._apply_base_qss()
        self._preload_catalogos_async()

    # ---------------------------------------------------------------------
    # Warmup de catálogos
    # ---------------------------------------------------------------------
    def _preload_catalogos_async(self):
        task = _WarmupTask()
        task.signals.done.connect(lambda _: print("[Warmup] Catálogos precargados"))
        task.signals.error.connect(lambda msg: print(f"[Warmup] Falló: {msg}"))
        QThreadPool.globalInstance().start(task)

    def _ensure_catalogs_ready(self):
        if not CatalogCache.get().loaded_once():
            try:
                CatalogosService().warmup_all()
            except Exception as e:
                print(f"[Warmup Lazy] Falló: {e}")

    # ---------------------------------------------------------------------
    # Integraciones de Páginas
    # ---------------------------------------------------------------------
    def _make_vehiculos_page(self) -> QWidget:
        if not VehiculosPage:
            return PlaceholderPage("Vehículos")
        try:
            page = VehiculosPage()
        except Exception:
            page = PlaceholderPage("Vehículos")
        try:
            if hasattr(page, "open_detail"):
                page.open_detail.connect(lambda vid: self.open_vehiculo_detail(int(vid)))
        except Exception:
            pass
        return page

    def _make_clientes_page(self) -> QWidget:
        if not ClientesPage:
            return PlaceholderPage("Clientes")
        try:
            page = ClientesPage()
        except Exception:
            page = PlaceholderPage("Clientes")
        try:
            if hasattr(page, "open_detail"):
                page.open_detail.connect(lambda cid: self.open_cliente_detail(int(cid)))
        except Exception:
            pass
        return page

    def _make_facturacion_page(self) -> QWidget:
        if not FacturacionPage:
            return PlaceholderPage("Facturación")
        try:
            page = FacturacionPage()
        except Exception:
            page = PlaceholderPage("Facturación")
        return page

    def _make_configuracion_page(self) -> QWidget:
        """
        Crea la página de Configuración (cards). Si no existe, usa Placeholder.
        Además conecta la señal para abrir páginas hijas (Usuarios).
        """
        if not ConfiguracionPage:
            return PlaceholderPage("Configuración")
        try:
            page = ConfiguracionPage(parent=self, main_window=self)
        except Exception:
            return PlaceholderPage("Configuración")

        # Si la ConfiguracionPage emite open_page_requested(QWidget), la montamos.
        if hasattr(page, "open_page_requested"):
            try:
                page.open_page_requested.connect(self._on_open_page_requested)
            except Exception:
                pass
        return page

    # ---------------------------------------------------------------------
    # Detalles
    # ---------------------------------------------------------------------
    def open_vehiculo_detail(self, vehiculo_id: int):
        self._ensure_catalogs_ready()
        if not VehiculoDetailPage:
            self.notify("La página de detalle de vehículo no está disponible.", "error")
            return
        detail = VehiculoDetailPage(vehiculo_id)
        if hasattr(detail, "navigate_back"):
            detail.navigate_back.connect(lambda: self.navigate_back())
        self.navigate_to(detail)

    def open_cliente_detail(self, cliente_id: int):
        self._ensure_catalogs_ready()
        if not ClientesDetailPage:
            self.notify("La página de detalle de cliente no está disponible.", "error")
            return
        detail = ClientesDetailPage(cliente_id)
        if hasattr(detail, "navigate_back"):
            detail.navigate_back.connect(lambda: self.navigate_back())
        self.navigate_to(detail)

    def open_usuario_detail(self, user_id: int):
        """
        Navega al detalle de usuario (si existe la página).
        """
        if not UsuariosDetailPage:
            self.notify("La página de detalle de usuario no está disponible.", "error")
            return
        detail = UsuariosDetailPage(user_id=user_id, parent=self, main_window=self)
        if hasattr(detail, "navigate_back"):
            try:
                detail.navigate_back.connect(lambda: self.navigate_back())
            except Exception:
                pass
        self.navigate_to(detail)

    # ---------------------------------------------------------------------
    # Router
    # ---------------------------------------------------------------------
    def open_page(self, name: str, *args, **kwargs):
        self._ensure_catalogs_ready()

        # -------- Vehículos --------
        if name == "vehiculos":
            self.show_fixed_page(self.page_vehiculos)
            return
        if name == "vehiculos_detalle":
            vid = kwargs.get("vehiculo_id") or (args[0] if args else None)
            if vid:
                self.open_vehiculo_detail(int(vid))
            return
        if name == "vehiculos_agregar" and VehiculosAgregarPage:
            page = VehiculosAgregarPage(self)
            self.stack.setCurrentWidget(self._mount(page))
            return

        # -------- Clientes --------
        if name == "clientes":
            self.show_fixed_page(self.page_clientes)
            return
        if name == "clientes_detalle":
            cid = kwargs.get("cliente_id") or (args[0] if args else None)
            if cid:
                self.open_cliente_detail(int(cid))
            return
        if name == "clientes_agregar" and ClientesAgregarPage:
            page = ClientesAgregarPage(self)
            self.stack.setCurrentWidget(self._mount(page))
            return

        # -------- Usuarios --------
        if name == "usuarios":
            # Si existe UsuariosPage real, la montamos temporal o la reutilizamos.
            if UsuariosPage:
                page = UsuariosPage(parent=self, main_window=self)
                # Conectar señales si están disponibles (abrir agregar/detalle)
                try:
                    if hasattr(page, "open_add_user_requested"):
                        page.open_add_user_requested.connect(lambda: self.open_page("usuarios_agregar"))
                except Exception:
                    pass
                try:
                    if hasattr(page, "open_user_detail_requested"):
                        page.open_user_detail_requested.connect(lambda uid: self.open_page("usuarios_detalle", usuario_id=int(uid)))
                except Exception:
                    pass
                self.stack.setCurrentWidget(self._mount(page))
            else:
                self.notify("La página de usuarios no está disponible.", "error")
            return

        if name == "usuarios_detalle":
            uid = kwargs.get("usuario_id") or (args[0] if args else None)
            if uid:
                self.open_usuario_detail(int(uid))
            else:
                self.notify("Falta usuario_id para abrir detalle.", "error")
            return

        # -------- Usuarios --------
        if name == "usuarios_agregar":
            if UsuariosAgregarPage:
                page = UsuariosAgregarPage(parent=self, main_window=self)
        
                # ← conectar el botón Volver (con confirm) a la navegación hacia atrás
                if hasattr(page, "go_back"):
                    page.go_back.connect(self.navigate_back)
        
                # opcional: si tu alta emite ir a detalle
                if hasattr(page, "go_to_detalle"):
                    page.go_to_detalle.connect(lambda uid: self.open_page("usuarios_detalle", usuario_id=uid))
        
                # ← MUY IMPORTANTE: usar navigate_to para apilar en el historial
                self.navigate_to(page)
            else:
                self.notify("La página de alta de usuario no está disponible.", "error")
            return


        # -------- Facturación --------
        if name == "facturacion":
            self.show_fixed_page(self.page_facturacion)
            return

        self.notify(f"Ruta no reconocida: {name}", "error")

    # ---------------------------------------------------------------------
    # Manejo de páginas emitidas desde Configuración (cards)
    # ---------------------------------------------------------------------
    def _on_open_page_requested(self, page_widget: QWidget):
        """
        Permite que ConfiguracionPage nos pida abrir una subpágina (por ejemplo, UsuariosPage).
        """
        if page_widget is None:
            return
        # Intentamos montarla y mostrarla.
        self.stack.setCurrentWidget(self._mount(page_widget))

    # ---------------------------------------------------------------------
    # Navegación y helpers
    # ---------------------------------------------------------------------
    def navigate_to(self, widget: QWidget):
        self._page_history.append(self.stack.currentWidget())
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

    def navigate_back(self):
        if not self._page_history:
            return
        current = self.stack.currentWidget()
        prev = self._page_history.pop()
        self.stack.setCurrentWidget(prev)
        current.setParent(None)
        current.deleteLater()

    def show_fixed_page(self, page: QWidget):
        self._ensure_catalogs_ready()
        while self._page_history:
            current = self.stack.currentWidget()
            prev = self._page_history.pop()
            self.stack.setCurrentWidget(prev)
            current.setParent(None)
            current.deleteLater()
        self.stack.setCurrentWidget(page)

    # ---------------------------------------------------------------------
    # Toast & notify
    # ---------------------------------------------------------------------
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = 320, 36
        x = (self.width() - w) // 2
        y = self.height() - h - 20
        self._toast.setGeometry(x, y, w, h)

    def toast(self, text: str, msec: int = 2500):
        self._toast.setText(text)
        self._toast.setVisible(True)
        self._toast_timer.start(msec)

    def notify(self, text: str, tipo: str = "info"):
        popup = NotifyPopup(text, tipo, parent=self)
        popup.adjustSize()
        popup.show_centered()

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _mk_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("SideButton")
        b.setCheckable(True)
        b.setAutoExclusive(True)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b.setMinimumHeight(44)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _apply_base_qss(self):
        self.setStyleSheet("""
        QMainWindow#MainWindow { background: #F5F7FB; }
        #Sidebar { background: #1E2330; }
        #SideTitle { color: #E8EAED; font-weight: 700; margin: 6px 0 8px 0; }
        #SideButton {
          color: #E8EAED; background: #2A3040; border: 1px solid #3A4050;
          border-radius: 10px; padding: 10px 14px; text-align: left; font-size: 14px;
        }
        #SideButton:hover { background: #343B4D; }
        #SideButton:checked { background: #6C5CE7; border-color: #6C5CE7; color: white; }
        #Panel { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; }
        #Toast {
          background: rgba(15, 23, 42, 0.92); color: white;
          padding: 8px 12px; border-radius: 8px; font-weight: 600;
        }
        """)

    def _mount(self, widget: QWidget) -> QWidget:
        idx = self.stack.indexOf(widget)
        if idx == -1:
            self.stack.addWidget(widget)
        return widget
