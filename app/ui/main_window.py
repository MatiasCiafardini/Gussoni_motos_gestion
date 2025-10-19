from __future__ import annotations
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QThreadPool, QRunnable, QObject, Signal

from app.ui.pages.vehiculos_agregar import VehiculosAgregarPage

# -------- Páginas actuales del proyecto (con fallback a placeholders) --------
try:
    from app.ui.pages.dashboard_page import DashboardPage  # tu dashboard real
except Exception:
    from app.ui.pages.placeholder_page import PlaceholderPage as DashboardPage

from app.ui.pages.placeholder_page import PlaceholderPage

# Proveedores (si existe)
try:
    from app.ui.pages.proveedores_page import ProveedoresPage
except Exception:
    ProveedoresPage = None  # fallback a placeholder

# Vehículos (listado principal)
VehiculosPage = None
try:
    # tu versión nueva (sin args en ctor)
    from app.ui.pages.vehiculos_page import VehiculosPage as _VehiculosPage
    VehiculosPage = _VehiculosPage
except Exception:
    try:
        # por si en tu repo el nombre difiere
        from app.ui.pages.vehiculos_page import VehiculosPage as _VehiculosPage
        VehiculosPage = _VehiculosPage
    except Exception:
        VehiculosPage = None

# Detalle de Vehículo (si existe)
VehiculoDetailPage = None
try:
    from app.ui.pages.vehiculos_detail_page import VehiculoDetailPage as _VehiculoDetailPage
    VehiculoDetailPage = _VehiculoDetailPage
except Exception:
    VehiculoDetailPage = None

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
    - Páginas fijas: Inicio, Clientes, Vehículos, Facturación, Proveedores, Reportes, Configuración
    - Navegación apilada para detalle (navigate_to/widget) + volver (navigate_back)
    - Toast minimal y NotifyPopup integrados
    - Warmup de catálogos al iniciar (y lazy si todavía no cargó)
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

        # referencia para reusar la pantalla de "Agregar Vehículo"
        self._vehiculos_agregar_ref: Optional[VehiculosAgregarPage] = None

        # Páginas fijas (usa tus reales si existen)
        self.page_inicio = DashboardPage() if DashboardPage else PlaceholderPage("Inicio")
        self.page_clientes = PlaceholderPage("Clientes")

        # Vehículos: intentamos distintas firmas de constructor y le conectamos el detalle
        self.page_vehiculos = self._make_vehiculos_page()

        self.page_facturacion = PlaceholderPage("Facturación")
        self.page_proveedores = ProveedoresPage() if ProveedoresPage else PlaceholderPage("Proveedores")
        self.page_reportes = PlaceholderPage("Reportes")
        self.page_config = PlaceholderPage("Configuración")

        for p in (
            self.page_inicio, self.page_clientes, self.page_vehiculos, self.page_facturacion,
            self.page_proveedores, self.page_reportes, self.page_config
        ):
            self.stack.addWidget(p)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)

        # Conexiones menú (resetean historial)
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

        # Estilos mínimos
        self._apply_base_qss()

        # =============== Warmup de catálogos al iniciar ===============
        self._preload_catalogos_async()

    # ---------------------------------------------------------------------
    # Warmup: async al iniciar + lazy en navegación si hiciera falta
    # ---------------------------------------------------------------------
    def _preload_catalogos_async(self):
        task = _WarmupTask()
        task.signals.done.connect(lambda _: print("[Warmup] Catálogos precargados"))
        task.signals.error.connect(lambda msg: print(f"[Warmup] Falló: {msg}"))
        QThreadPool.globalInstance().start(task)

    def _ensure_catalogs_ready(self):
        """Carga catálogos si aún no se precalcularon."""
        if not CatalogCache.get().loaded_once():
            try:
                CatalogosService().warmup_all()
            except Exception as e:
                print(f"[Warmup Lazy] Falló: {e}")

    # ---------------------------------------------------------------------
    # Integración flexible de Vehículos
    # ---------------------------------------------------------------------
    def _make_vehiculos_page(self) -> QWidget:
        """
        Intenta crear la página de Vehículos con diferentes firmas de ctor:
        - VehiculosPage()                       (nueva)
        - VehiculosPage(notify=..., navigate=..., navigate_back=...)  (compat)
        Además conecta la señal open_detail(int) si existe.
        """
        if not VehiculosPage:
            return PlaceholderPage("Vehículos")

        page: Optional[QWidget] = None

        # 1) Intento sin argumentos (nueva API)
        try:
            page = VehiculosPage()
        except TypeError:
            page = None

        # 2) Intento con callbacks (API anterior/compat)
        if page is None:
            try:
                page = VehiculosPage(
                    notify=self.notify,
                    navigate=self.navigate_to,
                    navigate_back=self.navigate_back
                )
            except Exception:
                page = PlaceholderPage("Vehículos")

        # Conectar señal open_detail si existe
        try:
            if hasattr(page, "open_detail"):
                page.open_detail.connect(lambda vid: self.open_vehiculo_detail(int(vid)))
        except Exception:
            pass

        return page

    def open_vehiculo_detail(self, vehiculo_id: int):
        """
        Abre el detalle de vehículo (si la página existe).
        """
        self._ensure_catalogs_ready()

        if not VehiculoDetailPage:
            self.notify("La página de detalle de vehículo no está disponible.", "error")
            return

        detail = VehiculoDetailPage(vehiculo_id)

        def _back_and_refresh():
            self.navigate_back()
            try:
                if getattr(self, "page_vehiculos", None):
                    if hasattr(self.page_vehiculos, "refresh_from_parent"):
                        self.page_vehiculos.refresh_from_parent()
                    else:
                        self.page_vehiculos.reload(reset_page=False)
            except Exception:
                pass

        try:
            if hasattr(detail, "navigate_back"):
                detail.navigate_back.connect(_back_and_refresh)
        except Exception:
            pass

        self.navigate_to(detail)

    def open_page(self, name: str, *args, **kwargs):
        """
        Router simple por nombre.
        Soporta:
          - 'vehiculos' → listado
          - 'vehiculos_detalle' → usa open_vehiculo_detail(vehiculo_id=...)
          - 'vehiculos_agregar' → alta (reusando instancia para performance)
        """
        # Garantiza que haya catálogos disponibles la primera vez
        self._ensure_catalogs_ready()

        if name == "vehiculos":
            self.show_fixed_page(self.page_vehiculos)
            return

        if name == "vehiculos_detalle":
            vehiculo_id = kwargs.get("vehiculo_id") or (args[0] if args else None)
            if vehiculo_id is None:
                self.notify("Falta vehiculo_id para abrir el detalle.", "error")
                return
            self.open_vehiculo_detail(int(vehiculo_id))
            return

        if name == "vehiculos_agregar":
            # Reusar la pantalla si ya fue creada (mucho más rápido)
            if self._vehiculos_agregar_ref is None:
                page = VehiculosAgregarPage(self)
                # Conectar señales una vez
                if hasattr(page, "go_back"):
                    page.go_back.connect(lambda: self.open_page("vehiculos"))
                if hasattr(page, "go_to_detalle"):
                    page.go_to_detalle.connect(lambda vid: self.open_page("vehiculos_detalle", vehiculo_id=vid))
                self._vehiculos_agregar_ref = page
                self.stack.setCurrentWidget(self._mount(page))
            else:
                page = self._vehiculos_agregar_ref
                # limpiar si el page lo implementa
                if hasattr(page, "_limpiar_formulario"):
                    try:
                        page._limpiar_formulario()
                    except Exception:
                        pass
                self.stack.setCurrentWidget(self._mount(page))
            return

        # Si llega un nombre desconocido:
        self.notify(f"Ruta no reconocida: {name}", "error")

    # ---------------------------------------------------------------------
    # Navegación apilada (detalle -> volver)
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
        # limpieza del widget apilado
        current.setParent(None)
        current.deleteLater()

    # ---------------------------------------------------------------------
    # Navegación a páginas fijas (limpia historial)
    # ---------------------------------------------------------------------
    def show_fixed_page(self, page: QWidget):
        # Asegura catálogos antes de mostrar páginas que podrían usarlos
        self._ensure_catalogs_ready()

        while self._page_history:
            current = self.stack.currentWidget()
            prev = self._page_history.pop()
            self.stack.setCurrentWidget(prev)
            current.setParent(None)
            current.deleteLater()
        self.stack.setCurrentWidget(page)

    # ---------------------------------------------------------------------
    # Toast overlay
    # ---------------------------------------------------------------------
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w = 320
        h = 36
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

        /* Sidebar */
        #Sidebar { background: #1E2330; }
        #SideTitle { color: #E8EAED; font-weight: 700; margin: 6px 0 8px 0; }
        #SideButton {
          color: #E8EAED; background: #2A3040; border: 1px solid #3A4050;
          border-radius: 10px; padding: 10px 14px; text-align: left; font-size: 14px;
        }
        #SideButton:hover { background: #343B4D; }
        #SideButton:checked { background: #6C5CE7; border-color: #6C5CE7; color: white; }

        /* Panel genérico (si lo usan en páginas) */
        #Panel { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; }



        /* Toast */
        #Toast {
          background: rgba(15, 23, 42, 0.92); color: white;
          padding: 8px 12px; border-radius: 8px; font-weight: 600;
        }
        """)

    def _mount(self, widget: QWidget) -> QWidget:
        """
        Asegura que el widget esté en el stack y devuelve el widget mostrado.
        Evita duplicados y conserva la referencia para que no lo recolecte el GC.
        """
        idx = self.stack.indexOf(widget)
        if idx == -1:
            self.stack.addWidget(widget)
        return widget
