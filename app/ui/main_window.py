from __future__ import annotations
from typing import Optional, Callable
import time
from app.core.updater import check_for_update
from app.core.downloader import download_file
from pathlib import Path
import sys
import os
import subprocess
from app.ui.widgets.loading_overlay import LoadingOverlay
from PySide6.QtWidgets import QTableView
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSizePolicy, QApplication
)
import app.ui.app_message as popUp
from PySide6.QtCore import Qt, QTimer, QThreadPool, QRunnable, QObject, Signal
import ctypes
# -------- Páginas actuales del proyecto (con fallback a placeholders) --------
try:
    from app.ui.pages.dashboard_page import DashboardPage  # tu dashboard real
except Exception:
    from app.ui.pages.placeholder_page import PlaceholderPage as DashboardPage
from app.ui.pages.placeholder_page import PlaceholderPage
from PySide6.QtWidgets import QDialog
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
except Exception as e:
    print("ERROR importando ClientesDetailPage:", e)
    raise

ClientesAgregarPage = None
try:
    from app.ui.pages.clientes_agregar import ClientesAgregarPage as _ClientesAgregarPage
    ClientesAgregarPage = _ClientesAgregarPage
except Exception:
    ClientesAgregarPage = None
# =================== REPORTES ===================
ReportesPage = None
try:
    from app.ui.pages.reportes_page import ReportesPage as _ReportesPage
    ReportesPage = _ReportesPage
except Exception as e:
    print("ERROR importando ReportesPage:", e)
    ReportesPage = None

# =================== FACTURACIÓN ===================
FacturacionPage = None
try:
    from app.ui.pages.facturas_page import FacturasPage as _FacturacionPage
    FacturacionPage = _FacturacionPage
except Exception:
    FacturacionPage = None

FacturasAgregarPage = None
try:
    from app.ui.pages.facturas_agregar import FacturasAgregarPage as _FacturasAgregarPage
    FacturasAgregarPage = _FacturasAgregarPage
except Exception:
    FacturasAgregarPage = None

# NUEVO: página de consulta de factura
FacturasConsultarPage = None
try:
    from app.ui.pages.facturas_consultar import FacturasConsultarPage as _FacturasConsultarPage
    FacturasConsultarPage = _FacturasConsultarPage
except Exception as e:
    print("❌ ERROR importando FacturasConsultarPage:", e)
    raise

# =================== DOCUMENTACIÓN ===================
DocumentacionPage = None
try:
    from app.ui.pages.documentacion_page import DocumentacionPage as _DocumentacionPage
    DocumentacionPage = _DocumentacionPage
except Exception as e:
    print("ERROR importando DocumentacionPage:", e)
    DocumentacionPage = None

# =================== CONFIGURACIÓN ===================
ConfiguracionPage = None
try:
    from app.ui.pages.configuracion_page import ConfiguracionPage as _ConfiguracionPage
    ConfiguracionPage = _ConfiguracionPage
except Exception:
    ConfiguracionPage = None
# =================== REMITOS ===================
RemitosPage = None
try:
    from app.ui.pages.remitos_page import RemitosPage as _RemitosPage
    RemitosPage = _RemitosPage
except Exception:
    RemitosPage = None

RemitosAgregarPage = None
try:
    from app.ui.pages.remitos_agregar import RemitosAgregarPage as _RemitosAgregarPage
    RemitosAgregarPage = _RemitosAgregarPage
except Exception:
    RemitosAgregarPage = None

RemitosDetailPage = None
try:
    from app.ui.pages.remitos_detail_page import RemitosDetailPage as _RemitosDetailPage
    RemitosDetailPage = _RemitosDetailPage
except Exception:
    RemitosDetailPage = None
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
# ==== Warmup de catálogos ====
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
    logout_requested = Signal()

    def __init__(self, *, current_user: Optional[dict] = None, on_logout: Optional[Callable[[], None]] = None):
        super().__init__()


        self.setWindowTitle("Gestión de Motos")
        self.resize(1100, 720)
        # IMPORTANTE: fijamos un mínimo razonable para romper el min gigante de los hijos
        self.setMinimumSize(900, 600)
        self.setObjectName("MainWindow")

        self.current_user = current_user
        self._on_logout_callback = on_logout
        self.central = QWidget(self)
        # Permitimos que el central no imponga un mínimo enorme
        self.central.setMinimumSize(0, 0)
        self.setCentralWidget(self.central)
        # 👇 ACÁ
        self.loading = LoadingOverlay(self.central, text="Cargando…")
        self.loading.hide_overlay()
        root_v = QVBoxLayout(self.central)
        root_v.setContentsMargins(0, 0, 0, 0)
        root_v.setSpacing(0)

        
        # Layout horizontal real (sidebar + contenido)
        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        root_v.addLayout(root, 1)
        

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
        self.btn_remitos  = self._mk_btn("Remitos")
        self.btn_documentacion= self._mk_btn("Documentación")
        self.btn_proveedores  = self._mk_btn("Proveedores")
        self.btn_reportes     = self._mk_btn("Reportes")
        self.btn_config       = self._mk_btn("Configuración")

        for b in (
            self.btn_inicio, self.btn_clientes, self.btn_vehiculos, self.btn_facturacion,self.btn_remitos,self.btn_documentacion,
            self.btn_proveedores, self.btn_reportes, self.btn_config
        ):
            sbl.addWidget(b)
        sbl.addStretch(1)

        self.btn_logout = self._mk_btn("Cerrar sesión")
        self.btn_logout.setObjectName("SideLogout")
        sbl.addWidget(self.btn_logout)

        # =============== Stack + historial ===============
        self.stack = QStackedWidget(self)
        # Que el stack tampoco arrastre mínimos enormes
        self.stack.setMinimumSize(0, 0)

        self._page_history: list[QWidget] = []

        self._vehiculos_agregar_ref: Optional[QWidget] = None
        self._clientes_agregar_ref: Optional[QWidget] = None

        # Timestamp del warmup fallido
        self._catalog_warmup_fail_ts: Optional[float] = None

        # =============== Páginas principales ===============
        self.page_inicio = DashboardPage() if DashboardPage else PlaceholderPage("Inicio")
        self.page_clientes = self._make_clientes_page()
        self.page_vehiculos = self._make_vehiculos_page()
        self.page_facturacion = self._make_facturacion_page()
        self.page_remitos = self._make_remitos_page()
        if DocumentacionPage:
            self.page_documentacion = DocumentacionPage()
        else:
            self.page_documentacion = PlaceholderPage("Documentación")

        try:
            from app.ui.pages.proveedores_page import ProveedoresPage
            self.page_proveedores = ProveedoresPage()
        except Exception:
            self.page_proveedores = PlaceholderPage("Proveedores")

        if ReportesPage:
            self.page_reportes = ReportesPage(parent=self, main_window=self)
        else:
            self.page_reportes = PlaceholderPage("Reportes")


        self.page_config = self._make_configuracion_page()

        for p in (
            self.page_inicio, self.page_clientes, self.page_vehiculos, self.page_facturacion,self.page_remitos,self.page_documentacion,
            self.page_proveedores, self.page_reportes, self.page_config
        ):
            self.stack.addWidget(p)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)

        # Sidebar events
        self.btn_inicio.clicked.connect(lambda: self.show_fixed_page(self.page_inicio))
        self.btn_clientes.clicked.connect(lambda: self.show_fixed_page(self.page_clientes))
        self.btn_vehiculos.clicked.connect(lambda: self.show_fixed_page(self.page_vehiculos))
        self.btn_facturacion.clicked.connect(lambda: self.show_fixed_page(self.page_facturacion))
        self.btn_remitos.clicked.connect(lambda: self.show_fixed_page(self.page_remitos))
        self.btn_documentacion.clicked.connect(lambda: self.show_fixed_page(self.page_documentacion))
        self.btn_proveedores.clicked.connect(lambda: self.show_fixed_page(self.page_proveedores))
        self.btn_reportes.clicked.connect(
            lambda: self.open_page("reportes")
        )

        self.btn_config.clicked.connect(lambda: self.show_fixed_page(self.page_config))
        self.btn_inicio.setChecked(True)

        self.btn_logout.clicked.connect(self._handle_logout)
        self.logout_requested.connect(self._emit_logout_callback)

        self._apply_base_qss()
        self._preload_catalogos_async()
        QTimer.singleShot(0, self.showMaximized)
        QTimer.singleShot(0, self._refresh_tables_fonts)
        QTimer.singleShot(1500, self._check_updates_on_startup)



    # ---------------------------------------------------------------------
    # Warmup de catálogos
    # ---------------------------------------------------------------------
    def _preload_catalogos_async(self):
        task = _WarmupTask()
        task.signals.done.connect(self._on_catalog_warmup_done)
        task.signals.error.connect(self._on_catalog_warmup_error)
        QThreadPool.globalInstance().start(task)

    def _on_catalog_warmup_done(self, _data: dict):
        self._catalog_warmup_fail_ts = None

    def _on_catalog_warmup_error(self, msg: str):
        self._catalog_warmup_fail_ts = time.monotonic()

    def _ensure_catalogs_ready(self, *, force: bool = False):
        cache = CatalogCache.get()
        if cache.loaded_once():
            return

        if not force and self._catalog_warmup_fail_ts is not None:
            if time.monotonic() - self._catalog_warmup_fail_ts < 30:
                return

        try:
            CatalogosService().warmup_all()
            self._catalog_warmup_fail_ts = None
        except Exception as e:
            self._catalog_warmup_fail_ts = time.monotonic()
            print(f"[Warmup Lazy] Falló: {e}")

    def _route_requires_catalogs(self, route: str) -> bool:
        return route.startswith(("vehiculos", "remitos", "facturas"))
    def show_loading(self, text: str = "Cargando…"):
        self.loading.lbl_text.setText(text)
        self.loading.show_overlay()
        QApplication.processEvents()


    def hide_loading(self):
        self.loading.hide_overlay()

    # ---------------------------------------------------------------------
    # Integración de páginas
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
            page = FacturacionPage(parent=self, main_window=self)
        except Exception:
            return PlaceholderPage("Facturación")

        try:
            if hasattr(page, "open_add"):
                page.open_add.connect(lambda: self.open_page("facturas_agregar"))

            if hasattr(page, "open_detail"):
                # AHORA: abrir pantalla de consulta de factura
                page.open_detail.connect(
                    lambda fid: self.open_page("facturas_consultar", factura_id=int(fid))
                )
        except Exception:
            pass

        return page
    def _make_remitos_page(self) -> QWidget:
        if not RemitosPage:
            return PlaceholderPage("Remitos")

        try:
            page = RemitosPage(parent=self, main_window=self)
        except Exception:
            return PlaceholderPage("Remitos")

        try:
            if hasattr(page, "open_add"):
                page.open_add.connect(lambda: self.open_page("remitos_agregar"))

            if hasattr(page, "open_detail"):
                page.open_detail.connect(
                    lambda rid: self.open_page(
                        "remitos_detalle",
                        remito_id=int(rid)
                    )
                )
        except Exception:
            pass

        return page
    def _make_configuracion_page(self) -> QWidget:
        if not ConfiguracionPage:
            return PlaceholderPage("Configuración")
        try:
            page = ConfiguracionPage(parent=self, main_window=self)
        except Exception:
            return PlaceholderPage("Configuración")

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
        self._ensure_catalogs_ready(force=True)
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

        # volver
        if hasattr(detail, "navigate_back"):
            detail.navigate_back.connect(lambda: self.navigate_back())

        # 👉 abrir factura existente (lupa)
        if hasattr(detail, "navigate_to_factura"):
            detail.navigate_to_factura.connect(
                lambda fid, cid=cliente_id: self.open_page(
                    "facturas_consultar",
                    factura_id=int(fid),
                    return_to="cliente",
                    cliente_id=cid,
                )
            )

        # 🔥 NUEVO: abrir factura nueva con cliente precargado
        if hasattr(detail, "navigate_to_factura_nueva"):
            detail.navigate_to_factura_nueva.connect(
                lambda cid=cliente_id: self.open_page(
                    "facturas_agregar",
                    cliente_id=cid,
                    return_to="cliente"
                )
            )


        self.navigate_to(detail)

        
    
    def open_usuario_detail(self, user_id: int):
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
    # buscador de actualizaciones
    # ---------------------------------------------------------------------
    def check_updates_ui(self, *, interactive: bool = True):
        try:
            update = check_for_update()
            if not update:
                if interactive:
                    popUp.info(
                        self,
                        "Actualizaciones",
                        "La aplicación ya está actualizada.",
                    )
                    return
            if interactive:
                if not popUp.confirm(
                    self,
                    "Actualización disponible",
                    f"Hay una nueva versión disponible: {update['version']}\n\n"
                    f"{update.get('changelog', '')}",
                    ok_text="Actualizar ahora",
                    cancel_text="Más tarde",
                    icon="⬆️",
                ):
                    return

            # -------- descargar --------
            updates_dir = Path(os.getenv("LOCALAPPDATA")) / "GussoniApp" / "updates"
            updates_dir.mkdir(parents=True, exist_ok=True)

            dest = updates_dir / Path(update["url"]).name
            download_file(update["url"], dest)

            popUp.info(
                self,
                "Actualización lista",
                "La actualización se descargó correctamente.\n"
                "La aplicación se cerrará para instalarla.",
            )

            # -------- lanzar updater --------
            current_exe = Path(sys.executable)
            updater_exe = current_exe.parent / "updater.exe"

            if not updater_exe.exists():
                raise RuntimeError("No se encontró updater.exe")

            params = f'"{current_exe}" "{dest}" "{update["version"]}"'

            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                str(updater_exe),
                params,
                None,
                1,
            )

            os._exit(0)

        except Exception as e:
            popUp.error(
                self,
                "Error al actualizar",
                str(e),
            )




    # ---------------------------------------------------------------------
    # Router
    # ---------------------------------------------------------------------
    def open_page(self, name: str, *args, **kwargs):
        self.show_loading("Cargando…")
        if self._ensure_catalogs_ready and self._route_requires_catalogs(name):
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
        # -------- Remitos --------
        if name == "remitos":
            self.show_fixed_page(self.page_remitos)
            return
        if name == "remitos_agregar":

            if not RemitosAgregarPage:
                self.notify("La página de alta de remito no está disponible.", "error")
                return

            page = RemitosAgregarPage(parent=self, main_window=self)

            if hasattr(page, "go_back"):
                page.go_back.connect(self.navigate_back)

            if hasattr(page, "go_to_detalle"):
                page.go_to_detalle.connect(
                    lambda rid: self.open_page(
                        "remitos_detalle",
                        remito_id=rid
                    )
                )

            self.navigate_to(page)
            return
        if name == "remitos_detalle":

            current = self.stack.currentWidget()
            if isinstance(current, RemitosDetailPage):
                return

            rid = kwargs.get("remito_id") or (args[0] if args else None)
            if not rid:
                self.notify("Falta remito_id para abrir el detalle.", "error")
                return

            if not RemitosDetailPage:
                self.notify("La página de detalle de remito no está disponible.", "error")
                return

            page = RemitosDetailPage(
                remito_id=int(rid),
                parent=self,
                main_window=self,
            )

            if hasattr(page, "go_back"):
                page.go_back.connect(self.navigate_back)

            self.navigate_to(page)
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
        
        # -------- Documentación --------
        if name == "documentacion":
            self.show_fixed_page(self.page_documentacion)
            return


        # -------- Usuarios --------
        if name == "usuarios":
            if UsuariosPage:
                page = UsuariosPage(parent=self, main_window=self)

                try:
                    if hasattr(page, "open_add_user_requested"):
                        page.open_add_user_requested.connect(
                            lambda: self.open_page("usuarios_agregar")
                        )
                except Exception:
                    pass

                try:
                    if hasattr(page, "open_user_detail_requested"):
                        page.open_user_detail_requested.connect(
                            lambda uid: self.open_page("usuarios_detalle", usuario_id=int(uid))
                        )
                except Exception:
                    pass

                self.navigate_to(page)  # 👈 CLAVE
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

        if name == "usuarios_agregar":
            if UsuariosAgregarPage:
                page = UsuariosAgregarPage(parent=self, main_window=self)
                if hasattr(page, "go_back"):
                    page.go_back.connect(self.navigate_back)
                if hasattr(page, "go_to_detalle"):
                    page.go_to_detalle.connect(lambda uid: self.open_page("usuarios_detalle", usuario_id=uid))
                self.navigate_to(page)
            else:
                self.notify("La página de alta de usuario no está disponible.", "error")
            return
        # -------- Reportes --------
        if name == "reportes":
            # 🔒 FIX: si ya estoy en Reportes, no mostrar loading
            if self.stack.currentWidget() is self.page_reportes:
                self.loading.hide_overlay()
                return

            self.show_fixed_page(self.page_reportes)
            return


        # -------- Facturación --------
        if name == "facturacion":
            self.show_fixed_page(self.page_facturacion)
            return

        if name == "facturas_agregar":
            if FacturasAgregarPage:

                cliente_id = kwargs.get("cliente_id")
                return_to = kwargs.get("return_to")

                page = FacturasAgregarPage(
                    parent=self,
                    main_window=self,
                    cliente_id=cliente_id
                )

                # 🔥 CONEXIÓN INTELIGENTE DE VOLVER
                if hasattr(page, "go_back"):
                    page.go_back.connect(self.navigate_back)


                if hasattr(page, "go_to_detalle"):
                    page.go_to_detalle.connect(
                        lambda fid: self.open_page(
                            "facturas_consultar",
                            factura_id=fid
                        )
                    )

                self.navigate_to(page)

            else:
                self.notify("La página de alta de factura no está disponible.", "error")

            return


        # NUEVO: consulta de factura
        if name == "facturas_consultar":

            # 🔒 FIX: si ya estoy viendo una factura, no volver a abrirla
            current = self.stack.currentWidget()
            if isinstance(current, FacturasConsultarPage):
                return

            fid = kwargs.get("factura_id") or (args[0] if args else None)
            if not fid:
                self.notify("Falta factura_id para abrir la consulta.", "error")
                return

            if not FacturasConsultarPage:
                self.notify("La página de consulta de factura no está disponible.", "error")
                return
            try:
                return_to = kwargs.get("return_to")
                cliente_id = kwargs.get("cliente_id")

                page = FacturasConsultarPage(
                    factura_id=int(fid),
                    parent=self,
                    main_window=self,
                    return_to=return_to,
                    cliente_id=cliente_id,
                )

            except Exception as ex:
                print("Error creando FacturasConsultarPage:", ex)
                self.notify("No se pudo abrir la consulta de factura.", "error")
                return

            if hasattr(page, "go_back"):
                try:
                    if return_to == "cliente" and cliente_id:
                        page.go_back.connect(
                            lambda: self.open_page(
                                "clientes_detalle",
                                cliente_id=cliente_id
                            )
                        )
                    else:
                        page.go_back.connect(self.navigate_back)
                except Exception:
                    pass
                
            self.navigate_to(page)
            return

        self.notify(f"Ruta no reconocida: {name}", "error")

    # ---------------------------------------------------------------------
    # Navegación
    # ---------------------------------------------------------------------
    def _on_open_page_requested(self, page_widget: QWidget):
        if page_widget is None:
            return
        self.stack.setCurrentWidget(self._mount(page_widget))

    def navigate_to(self, widget: QWidget):
        current = self.stack.currentWidget()

        # 🔒 FIX CLAVE: no apilar si ya estamos en la MISMA PÁGINA
        if current is not None and current is widget:
            return

        # 🔒 FIX EXTRA: no duplicar por clase (caso facturas_consultar)
        if current is not None and type(current) is type(widget):
            return

        self._page_history.append(current)
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        QTimer.singleShot(0, self.loading.hide_overlay)



    def navigate_back(self):
        if not self._page_history:
            return

        current = self.stack.currentWidget()
        prev = self._page_history.pop()

        self.stack.setCurrentWidget(prev)

        # 🔥 SOLO recargar si volvemos desde FacturasConsultar a Facturacion
        if (
            isinstance(current, FacturasConsultarPage)
            and prev is self.page_facturacion
        ):
            try:
                self.page_facturacion.reload(reset_page=False)
            except Exception:
                pass
        if isinstance(current, RemitosDetailPage) and prev is self.page_remitos:
            try:
                self.page_remitos.reload(reset_page=False)
            except Exception:
                pass          
        current.setParent(None)
        current.deleteLater()

        QTimer.singleShot(0, self.loading.hide_overlay)


    def show_fixed_page(self, page: QWidget):
        if self.stack.currentWidget() is page:
            return

        if page is self.page_vehiculos:
            self._ensure_catalogs_ready()
        while self._page_history:
            current = self.stack.currentWidget()
            self._page_history.pop()
            current.setParent(None)
            current.deleteLater()

        self.stack.setCurrentWidget(page)
        QTimer.singleShot(0, self.loading.hide_overlay)
    def _check_updates_on_startup(self):
        """
        Chequea actualizaciones al iniciar y pregunta si desea instalar.
        Silencioso si no hay update.
        """
        try:
            update = check_for_update()
            if not update:
                return  # no molestar si no hay nada

            if popUp.confirm(
                self,
                title="Actualización disponible",
                text=f"Hay una nueva versión disponible: {update['version']}",
                informative_text=update.get("changelog"),
                ok_text="Actualizar ahora",
                cancel_text="Más tarde",
                icon="⬆️",
            ):
                self.check_updates_ui(interactive=False)

        except Exception as e:
            # IMPORTANTE: no romper el arranque por un error de update
            print("Error chequeando actualizaciones:", e)

    # ---------------------------------------------------------------------
    # Toast & Notify
    # ---------------------------------------------------------------------
    def notify(self, text: str, tipo: str = "info"):
        from app.ui import app_message
        app_message.toast(self, text, kind=tipo)


    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _mk_btn(self, text: str, *, checkable: bool = True) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("SideButton")
        b.setCheckable(checkable)
        b.setAutoExclusive(checkable)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b.setMinimumHeight(44)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _handle_logout(self):
        self.logout_requested.emit()

    def _emit_logout_callback(self):
        self.close()
        if self._on_logout_callback:
            self._on_logout_callback()

    def _apply_base_qss(self):
        self.setStyleSheet("""
        QMainWindow#MainWindow { background: #F5F7FB; }
        #Sidebar { background: #1E2330; }
        #SideTitle { color: #E8EAED; font-weight: 700; margin: 6px 0 8px 0; }
        #SideButton {
          color: #E8EAED; background: #2A3040; border: 1px solid #3A4050;
          border-radius: 10px; padding: 10px 14px; text-align: left; font-size: 1em;
        }
        #SideButton:hover { background: #343B4D; }
        #SideButton:checked { background: #6C5CE7; border-color: #6C5CE7; color: white; }
        #Panel { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; }
        #Toast {
          background: rgba(15, 23, 42, 0.92); color: white;
          padding: 8px 12px; border-radius: 8px; font-weight: 600;
        }                  
        """)
    def _refresh_tables_fonts(self):
        """
        Fuerza a QTableView y QHeaderView a recalcular
        fontMetrics usando el font global ya escalado.
        """
        app_font = QApplication.font()

        for table in self.findChildren(QTableView):
            # 👉 forzar font en la tabla
            table.setFont(app_font)

            header_h = table.horizontalHeader()
            header_v = table.verticalHeader()

            # 👉 forzar font en headers (CLAVE)
            header_h.setFont(app_font)
            header_v.setFont(app_font)

            # 👉 resetear tamaños cacheados
            header_h.setDefaultSectionSize(header_h.defaultSectionSize())
            header_v.setDefaultSectionSize(header_v.defaultSectionSize())

            table.resizeRowsToContents()
            table.resizeColumnsToContents()

            header_h.repaint()
            header_v.repaint()


    def _mount(self, widget: QWidget) -> QWidget:
        idx = self.stack.indexOf(widget)
        if idx == -1:
            self.stack.addWidget(widget)
        return widget
