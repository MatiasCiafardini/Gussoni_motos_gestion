from __future__ import annotations
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox, QTextEdit,
    QPushButton, QHBoxLayout, QSizePolicy, QListView, QFrame, QSpacerItem, QMessageBox
)

from app.services.usuarios_service import UsuariosService
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
            data = self.svc.warmup_all()  # usamos el mismo warmup; si no trae Usuarios, hacemos fallback
            self.signals.done.emit(data or {})
        except Exception as e:
            self.signals.error.emit(str(e))


# ============================== Página ===================================

class UsuariosAgregarPage(QWidget):
    """
    Pantalla de Alta de Usuario (estilo detalle, sin título).
    - Validaciones mínimas.
    - Botones: Guardar y seguir | Guardar y abrir detalle | Volver.
    """

    go_back = Signal()
    go_to_detalle = Signal(int)  # usuario_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UsuariosAgregarPage")

        self.service = UsuariosService()
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
        self.in_nombre = QLineEdit();     self.in_nombre.setPlaceholderText("Ej: Juan")
        self.in_apellido = QLineEdit();   self.in_apellido.setPlaceholderText("Ej: Pérez")

        self.in_tipo_doc = QComboBox();   self._setup_combo(self.in_tipo_doc)
        self.in_nro_doc = QLineEdit();    self.in_nro_doc.setPlaceholderText("Ej: 30111222 (sólo números)")
        self.in_nro_doc.setValidator(QIntValidator(0, 99999999, self))

        self.in_email = QLineEdit();      self.in_email.setPlaceholderText("Ej: nombre@mail.com")
        self.in_telefono = QLineEdit();   self.in_telefono.setPlaceholderText("Ej: 11-6000-1111")
        self.in_direccion = QLineEdit();  self.in_direccion.setPlaceholderText("Ej: San Martín 200, CABA")

        self.in_estado = QComboBox();     self._setup_combo(self.in_estado)

        self.in_observaciones = QTextEdit(); self.in_observaciones.setPlaceholderText("Observaciones (opcional)")
        self.in_observaciones.setFixedHeight(70)

        # === Filas (3 columnas) ===
        form.addWidget(QLabel("Nombre *"), 0, 0);       form.addWidget(self.in_nombre, 0, 1)
        form.addWidget(QLabel("Apellido"), 0, 2);       form.addWidget(self.in_apellido, 0, 3)
        form.addWidget(QLabel("Tipo doc *"), 0, 4);     form.addWidget(self.in_tipo_doc, 0, 5)

        form.addWidget(QLabel("N° Documento *"), 1, 0); form.addWidget(self.in_nro_doc, 1, 1)
        form.addWidget(QLabel("Email"), 1, 2);          form.addWidget(self.in_email, 1, 3)
        form.addWidget(QLabel("Teléfono"), 1, 4);       form.addWidget(self.in_telefono, 1, 5)

        form.addWidget(QLabel("Dirección"), 2, 0);      form.addWidget(self.in_direccion, 2, 1, 1, 3)
        form.addWidget(QLabel("Estado *"), 2, 4);       form.addWidget(self.in_estado, 2, 5)

        form.addWidget(QLabel("Observaciones"), 3, 0);  form.addWidget(self.in_observaciones, 3, 1, 1, 5)

        form_wrap.addLayout(form)
        content_l.addWidget(form_panel)
        content_l.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))  # evita empuje hacia abajo
        root.addWidget(content)

        # ===================== FOOTER CENTRADO ABAJO =====================
        root.addStretch(1)
        footer = QWidget(self)
        footer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        f = QHBoxLayout(footer)
        f.setContentsMargins(0, 0, 0, 0)
        f.setSpacing(12)

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
        for w in (self.in_nombre, self.in_apellido, self.in_nro_doc, self.in_email, self.in_telefono, self.in_direccion):
            w.textChanged.connect(self._mark_dirty)
        for cb in (self.in_tipo_doc, self.in_estado):
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
        for cb in (self.in_tipo_doc, self.in_estado):
            cb.setEnabled(False); cb.clear(); cb.addItem("Cargando...", None)

        task = _LoadCatalogosTask(self._catalogos)
        task.signals.done.connect(self._fill_catalogos)
        task.signals.error.connect(lambda msg: NotifyPopup(f"No se pudieron cargar catálogos: {msg}", "error", self).show_centered())
        QThreadPool.globalInstance().start(task)

    def _fill_catalogos(self, data: dict):
        # Tipos de documento
        self.in_tipo_doc.clear(); self.in_tipo_doc.addItem("Seleccione...", None)
        tipos = (data.get("tipos_documento") or
                 data.get("tipos_doc") or
                 [{"codigo": "DNI", "nombre": "DNI"}, {"codigo": "CUIT", "nombre": "CUIT"}, {"codigo": "CUIL", "nombre": "CUIL"}])
        for t in tipos:
            codigo = t.get("codigo") or t.get("nombre") or ""
            nombre = t.get("nombre") or t.get("codigo") or codigo
            self.in_tipo_doc.addItem(nombre, codigo)

        # Estados de usuario (1 Activo / 0 Inactivo por defecto)
        self.in_estado.clear()
        estados = (data.get("estados_usuarios") or
                   [{"id": 10, "nombre": "Activo"}, {"id": 11, "nombre": "Inactivo"}])
        for e in estados:
            self.in_estado.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

        # Preseleccionar Activo
        idx = self.in_estado.findText("Activo", Qt.MatchContains)
        self.in_estado.setCurrentIndex(idx if idx != -1 else 0)

        for cb in (self.in_tipo_doc, self.in_estado):
            cb.setEnabled(True)

    # -------------------- Guardar --------------------
    def _on_guardar(self, abrir_detalle: bool):
        data = self._collect_data()
        ok, errs = self._validate(data)
        if not ok:
            msg = "\n".join(f"• {v}" for v in errs.values())
            NotifyPopup(msg, "warning", self).show_centered()
            return

        try:
            new_id = self.service.create_user(data)
        except Exception as ex:
            NotifyPopup(f"Error al guardar: {ex}", "error", self).show_centered()
            return

        self._dirty = False
        if abrir_detalle:
            NotifyPopup("Usuario guardado correctamente.\nAbriendo detalle…", "success", self).show_centered()
            try:
                self.go_to_detalle.emit(int(new_id))
            except Exception:
                pass
        else:
            NotifyPopup("Usuario guardado correctamente.", "success", self).show_centered()
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
            self.in_nombre.text().strip(), self.in_apellido.text().strip(),
            self.in_nro_doc.text().strip(), self.in_email.text().strip(),
            self.in_telefono.text().strip(), self.in_direccion.text().strip(),
            self.in_observaciones.toPlainText().strip()
        ]
        if any(campos_texto):
            return True
        if any(cb.currentData() for cb in (self.in_tipo_doc, self.in_estado)):
            return True
        return False

    # -------------------- Utils --------------------
    def _collect_data(self) -> Dict[str, Any]:
        return {
            "tipo_doc": self.in_tipo_doc.currentData(),
            "nro_doc": self._only_digits(self.in_nro_doc.text()),
            "nombre": self.in_nombre.text().strip() or None,
            "apellido": self.in_apellido.text().strip() or None,
            "telefono": self.in_telefono.text().strip() or None,
            "email": self.in_email.text().strip() or None,
            "direccion": self.in_direccion.text().strip() or None,
            "estado_id": self.in_estado.currentData(),
            "observaciones": self.in_observaciones.toPlainText().strip() or None,
        }

    def _validate(self, d: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        errs: Dict[str, str] = {}
        if not d["nombre"]:
            errs["nombre"] = "El nombre es obligatorio."
        if not d["tipo_doc"]:
            errs["tipo_doc"] = "Seleccioná el tipo de documento."
        if not d["nro_doc"]:
            errs["nro_doc"] = "Ingresá el número de documento."
        elif not d["nro_doc"].isdigit():
            errs["nro_doc"] = "El N° de documento debe contener sólo números."
        if d.get("email") and ("@" not in d["email"] or "." not in d["email"].split("@")[-1]):
            errs["email"] = "Email inválido."
        if d.get("estado_id") is None:
            errs["estado_id"] = "Seleccioná el estado."
        return (len(errs) == 0, errs)

    def _only_digits(self, s: str) -> Optional[str]:
        s = (s or "").strip()
        digits = "".join(ch for ch in s if ch.isdigit())
        return digits or None

    def _limpiar_formulario(self):
        self.in_nombre.clear()
        self.in_apellido.clear()
        self.in_tipo_doc.setCurrentIndex(0)
        self.in_nro_doc.clear()
        self.in_email.clear()
        self.in_telefono.clear()
        self.in_direccion.clear()
        self.in_observaciones.clear()
        # estado vuelve al primero (probablemente Activo)
        if self.in_estado.count() > 0:
            self.in_estado.setCurrentIndex(0)
