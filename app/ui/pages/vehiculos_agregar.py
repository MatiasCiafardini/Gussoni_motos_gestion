from __future__ import annotations
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox, QTextEdit,
    QPushButton, QHBoxLayout, QSizePolicy, QListView, QFrame, QSpacerItem
)

from app.services.vehiculos_service import VehiculosService
from app.services.catalogos_service import CatalogosService
from app.ui.widgets.confirm_dialog import ConfirmDialog
from app.ui.notify import NotifyPopup


# ====================== Carga asíncrona de catálogos ======================

class _LoaderSignals(QObject):
    done = Signal(dict)
    error = Signal(str)


class _LoadCatalogosTask(QRunnable):
    def __init__(self, svc: CatalogosService):
        super().__init__()
        self.svc = svc
        self.signals = _LoaderSignals()

    def run(self):
        try:
            data = self.svc.warmup_all()
            self.signals.done.emit(data)
        except Exception as e:
            self.signals.error.emit(str(e))


# ============================== Página ===================================

class VehiculosAgregarPage(QWidget):
    """
    Pantalla de Alta de Vehículo (estilo detalle, sin título).
    - Validaciones mínimas.
    - Botones: Guardar y seguir | Guardar y abrir detalle | Volver.
    """

    go_back = Signal()
    go_to_detalle = Signal(int)  # vehiculo_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VehiculosAgregarPage")

        self.service = VehiculosService()
        self._catalogos = CatalogosService()
        self._dirty = False  # para confirmar al volver si hay cambios

        # ===================== Layout raíz =====================
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 12, 24, 16)
        root.setSpacing(8)

        # ---------- Contenido (form) pegado arriba ----------
        content = QWidget(self)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(0, 0, 0, 0)
        content_l.setSpacing(6)

        # ===================== Formulario =====================
        form_panel = QFrame(content)
        form_panel.setObjectName("Panel")
        form_panel.setStyleSheet("#Panel { background: transparent; border: none; }")
        form_wrap = QVBoxLayout(form_panel)
        form_wrap.setContentsMargins(0, 0, 0, 0)
        form_wrap.setSpacing(4)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
        form.setColumnStretch(0, 1); form.setColumnStretch(1, 3)
        form.setColumnStretch(2, 1); form.setColumnStretch(3, 3)
        form.setColumnStretch(4, 1); form.setColumnStretch(5, 3)

        # --- Campos ---
        self.in_marca = QLineEdit();   self.in_marca.setPlaceholderText("Ej: Honda")
        self.in_modelo = QLineEdit();  self.in_modelo.setPlaceholderText("Ej: Wave 110")
        self.in_anio = QLineEdit();    self.in_anio.setValidator(QIntValidator(1900, 2100, self)); self.in_anio.setPlaceholderText("Ej: 2024")
        self.in_nro_certificado = QLineEdit(); self.in_nro_certificado.setPlaceholderText("Certificado (opcional)")
        self.in_nro_dnrpa = QLineEdit();       self.in_nro_dnrpa.setPlaceholderText("DNRPA (opcional)")
        self.in_numero_cuadro = QLineEdit();   self.in_numero_cuadro.setPlaceholderText("N° de cuadro")
        self.in_numero_motor = QLineEdit();    self.in_numero_motor.setPlaceholderText("N° de motor")
        self.in_precio_lista = QLineEdit("0,00"); self.in_precio_lista.setPlaceholderText("Ej: 2.200.000,00")

        self.in_color = QComboBox();        self._setup_combo(self.in_color)
        self.in_estado_stock = QComboBox(); self._setup_combo(self.in_estado_stock)
        self.in_estado_moto = QComboBox();  self._setup_combo(self.in_estado_moto)
        self.in_proveedor = QComboBox();    self._setup_combo(self.in_proveedor)

        self.in_observaciones = QTextEdit(); self.in_observaciones.setPlaceholderText("Observaciones (opcional)")
        self.in_observaciones.setFixedHeight(70)

        # === Filas (3 columnas) ===
        form.addWidget(QLabel("Marca *"), 0, 0);    form.addWidget(self.in_marca, 0, 1)
        form.addWidget(QLabel("Modelo *"), 0, 2);   form.addWidget(self.in_modelo, 0, 3)
        form.addWidget(QLabel("Año *"), 0, 4);      form.addWidget(self.in_anio, 0, 5)

        form.addWidget(QLabel("N° Certificado"), 1, 0); form.addWidget(self.in_nro_certificado, 1, 1)
        form.addWidget(QLabel("N° DNRPA"), 1, 2);       form.addWidget(self.in_nro_dnrpa, 1, 3)
        form.addWidget(QLabel("Precio lista *"), 1, 4); form.addWidget(self.in_precio_lista, 1, 5)

        form.addWidget(QLabel("N° Cuadro *"), 2, 0); form.addWidget(self.in_numero_cuadro, 2, 1)
        form.addWidget(QLabel("N° Motor *"), 2, 2);  form.addWidget(self.in_numero_motor, 2, 3)
        form.addWidget(QLabel("Proveedor"), 2, 4);   form.addWidget(self.in_proveedor, 2, 5)

        form.addWidget(QLabel("Color *"), 3, 0);          form.addWidget(self.in_color, 3, 1)
        form.addWidget(QLabel("Estado stock *"), 3, 2);   form.addWidget(self.in_estado_stock, 3, 3)
        form.addWidget(QLabel("Condición *"), 3, 4);      form.addWidget(self.in_estado_moto, 3, 5)

        form.addWidget(QLabel("Observaciones"), 4, 0); form.addWidget(self.in_observaciones, 4, 1, 1, 5)

        form_wrap.addLayout(form)
        content_l.addWidget(form_panel)

        # (opcional) un expansor interno para que el panel no empuje hacia abajo
        content_l.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))

        # Agregamos el bloque 'content' al root
        root.addWidget(content)

        # ===================== FOOTER CENTRADO ABAJO =====================
        # Un stretch empuja todo hacia arriba y deja el footer abajo
        root.addStretch(1)

        footer = QWidget(self)
        footer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        f = QHBoxLayout(footer)
        f.setContentsMargins(0, 0, 0, 0)
        f.setSpacing(12)

        # Botones (centrados)
        self.btn_volver = QPushButton("Volver"); self.btn_volver.setObjectName("BtnGhost")
        self.btn_guardar_seguir = QPushButton("Guardar y seguir"); self.btn_guardar_seguir.setObjectName("BtnPrimary")
        self.btn_guardar_abrir = QPushButton("Guardar y abrir detalle"); self.btn_guardar_abrir.setObjectName("BtnPrimary")

        f.addStretch(1)
        f.addWidget(self.btn_volver)
        f.addWidget(self.btn_guardar_seguir)
        f.addWidget(self.btn_guardar_abrir)
        f.addStretch(1)

        root.addWidget(footer)

        # ===================== Señales =====================
        self.btn_volver.clicked.connect(self._on_volver)
        self.btn_guardar_seguir.clicked.connect(lambda: self._on_guardar(abrir_detalle=False))
        self.btn_guardar_abrir.clicked.connect(lambda: self._on_guardar(abrir_detalle=True))

        # Cambios → marcar dirty
        for w in (
            self.in_marca, self.in_modelo, self.in_anio, self.in_numero_cuadro, self.in_numero_motor,
            self.in_precio_lista, self.in_nro_certificado, self.in_nro_dnrpa
        ):
            w.textChanged.connect(self._mark_dirty)
        for cb in (self.in_color, self.in_estado_stock, self.in_estado_moto, self.in_proveedor):
            cb.currentIndexChanged.connect(self._mark_dirty)
        self.in_observaciones.textChanged.connect(self._mark_dirty)

        # Cargar catálogos (async + cache)
        self._load_filter_data_async()

    # -------------------- Setup helpers --------------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        lv = QListView(); lv.setObjectName("ComboPopup"); lv.setUniformItemSizes(True); lv.setSpacing(2)
        cb.setView(lv)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _mark_dirty(self, *_):
        self._dirty = True

    # -------------------- Catálogos --------------------
    def _load_filter_data_async(self):
        for cb in (self.in_color, self.in_estado_stock, self.in_estado_moto, self.in_proveedor):
            cb.setEnabled(False); cb.clear(); cb.addItem("Cargando...", None)

        task = _LoadCatalogosTask(self._catalogos)
        task.signals.done.connect(self._fill_catalogos)
        task.signals.error.connect(lambda msg: NotifyPopup(f"No se pudieron cargar catálogos: {msg}", "error", self).show_centered())
        QThreadPool.globalInstance().start(task)

    def _fill_catalogos(self, data: dict):
        # Colores
        self.in_color.clear(); self.in_color.addItem("Seleccione...", None)
        for c in data.get("colores", []):
            self.in_color.addItem(c.get("nombre", f"ID {c.get('id')}"), c.get("id"))

        # Estados
        self.in_estado_stock.clear()
        for e in data.get("estados_stock", []):
            self.in_estado_stock.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))
        # Set por defecto: Disponible
        idx = self.in_estado_stock.findText("Disponible", Qt.MatchContains)
        self.in_estado_stock.setCurrentIndex(idx if idx != -1 else 0)

        # Condición
        self.in_estado_moto.clear()
        for e in data.get("condiciones", []):
            self.in_estado_moto.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))
        # Set por defecto: Nueva
        idx = self.in_estado_moto.findText("Nueva", Qt.MatchContains)
        self.in_estado_moto.setCurrentIndex(idx if idx != -1 else 0)

        # Proveedores
        self.in_proveedor.clear(); self.in_proveedor.addItem("Sin proveedor", None)
        for p in data.get("proveedores", []):
            label = p.get("razon_social") or p.get("nombre") or f"ID {p.get('id')}"
            self.in_proveedor.addItem(label, p.get("id"))

        for cb in (self.in_color, self.in_estado_stock, self.in_estado_moto, self.in_proveedor):
            cb.setEnabled(True)

    # -------------------- Guardar --------------------
    def _on_guardar(self, abrir_detalle: bool):
        data = self._collect_data()
        ok, errs = self._validate(data)
        if not ok:
            msg = "\n".join(f"• {v}" for v in errs.values())
            NotifyPopup(msg, "warning", self).show_centered()
            return

        data["precio_lista"] = self._parse_money(self.in_precio_lista.text())

        try:
            new_id = self.service.create_vehiculo(data)
        except Exception as ex:
            NotifyPopup(f"Error al guardar: {ex}", "error", self).show_centered()
            return

        self._dirty = False
        if abrir_detalle:
            NotifyPopup("Vehículo guardado correctamente.\nAbriendo detalle…", "success", self).show_centered()
            self.go_to_detalle.emit(int(new_id))
        else:
            NotifyPopup("Vehículo guardado correctamente.", "success", self).show_centered()
            self._limpiar_formulario()
            self._dirty = False

    # -------------------- Volver --------------------
    def _on_volver(self):
        if self._dirty and self._hay_info_cargada():
            if not ConfirmDialog.ask_discard(self):
                return
        self.go_back.emit()

    def _hay_info_cargada(self) -> bool:
        campos_texto = [
            self.in_marca.text().strip(), self.in_modelo.text().strip(), self.in_anio.text().strip(),
            self.in_numero_cuadro.text().strip(), self.in_numero_motor.text().strip(),
            self.in_precio_lista.text().strip(), self.in_nro_certificado.text().strip(),
            self.in_nro_dnrpa.text().strip(), self.in_observaciones.toPlainText().strip()
        ]
        if any(campos_texto):
            return True
        if any(cb.currentData() for cb in (self.in_color, self.in_estado_stock, self.in_estado_moto)):
            return True
        return False

    # -------------------- Utils --------------------
    def _collect_data(self) -> Dict[str, Any]:
        return {
            "marca": self.in_marca.text().strip() or None,
            "modelo": self.in_modelo.text().strip() or None,
            "anio": self._parse_int(self.in_anio.text()),
            "numero_cuadro": self.in_numero_cuadro.text().strip() or None,
            "numero_motor": self.in_numero_motor.text().strip() or None,
            "color_id": self.in_color.currentData(),
            "estado_stock_id": self.in_estado_stock.currentData(),
            "estado_moto_id": self.in_estado_moto.currentData(),
            "proveedor_id": self.in_proveedor.currentData(),
            "nro_certificado": self.in_nro_certificado.text().strip() or None,
            "nro_dnrpa": self.in_nro_dnrpa.text().strip() or None,
            "precio_lista": self._parse_money(self.in_precio_lista.text()),
            "observaciones": self.in_observaciones.toPlainText().strip() or None,
        }

    def _validate(self, d: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        errs: Dict[str, str] = {}
        if not d["marca"]: errs["marca"] = "La marca es obligatoria."
        if not d["modelo"]: errs["modelo"] = "El modelo es obligatorio."
        if not d["anio"] or not (1900 <= int(d["anio"]) <= 2100): errs["anio"] = "Año inválido."
        if not d["numero_cuadro"]: errs["numero_cuadro"] = "El N° de cuadro es obligatorio."
        if not d["numero_motor"]: errs["numero_motor"] = "El N° de motor es obligatorio."
        if not d["color_id"]: errs["color_id"] = "Seleccioná un color."
        if not d["estado_stock_id"]: errs["estado_stock_id"] = "Seleccioná el estado de stock."
        if not d["estado_moto_id"]: errs["estado_moto_id"] = "Seleccioná la condición."
        precio = self._parse_money(self.in_precio_lista.text())
        if precio is None or precio <= 0: errs["precio_lista"] = "Precio inválido."
        return (len(errs) == 0, errs)

    def _parse_int(self, s: str) -> Optional[int]:
        s = (s or "").strip()
        return int(s) if s.isdigit() else None

    def _parse_money(self, s: str) -> Optional[float]:
        if not s:
            return None
        s = s.strip().replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    def _limpiar_formulario(self):
        self.in_marca.clear()
        self.in_modelo.clear()
        self.in_anio.clear()
        self.in_numero_cuadro.clear()
        self.in_numero_motor.clear()
        self.in_precio_lista.setText("0,00")
        self.in_nro_certificado.clear()
        self.in_nro_dnrpa.clear()
        self.in_observaciones.clear()
