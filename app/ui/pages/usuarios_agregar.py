from __future__ import annotations
from typing import Any, Dict, Optional, Tuple

import os
import binascii
import hashlib

from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox, QTextEdit,
    QPushButton, QHBoxLayout, QSizePolicy, QListView, QFrame, QSpacerItem,
    QMessageBox
)

from app.services.usuarios_service import UsuariosService
from app.services.catalogos_service import CatalogosService
from app.ui.widgets.confirm_dialog import ConfirmDialog
from app.ui.notify import NotifyPopup
from loguru import logger 

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
            data = self.svc.warmup_all()  # Si falla, el signal devolverá excepción
            self.signals.done.emit(data or {})
        except Exception as e:
            self.signals.error.emit(str(e))


# ============================== Página ===================================

class UsuariosAgregarPage(QWidget):
    """
    Alta/Edición de usuario:
    - Campos: nombre, usuario, contraseña, rol, email, estado
    - contraseña se guarda como contraseña_hash (PBKDF2 + salt)
    - Señales: go_back, go_to_detalle
    """
    go_back = Signal()
    go_to_detalle = Signal(int)  # emite el id del nuevo usuario

    def __init__(self, parent=None, main_window: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("UsuariosAgregarPage")

        self.service = UsuariosService()
        self._catalogos = CatalogosService()
        self._dirty = False

        # ===================== Layout raíz =====================
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 16)
        root.setSpacing(10)

        # ---------- Contenido (form) ----------
        content = QWidget(self)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(0, 0, 0, 0)
        content_l.setSpacing(8)

        # Panel con estilo
        form_panel = QFrame(content)
        form_panel.setObjectName("Panel")
        form_panel.setStyleSheet("#Panel { background: transparent; border: none; }")
        form_wrap = QVBoxLayout(form_panel)
        form_wrap.setContentsMargins(0, 0, 0, 0)
        form_wrap.setSpacing(6)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setColumnStretch(0, 1); form.setColumnStretch(1, 3)
        form.setColumnStretch(2, 1); form.setColumnStretch(3, 3)
        form.setColumnStretch(4, 1); form.setColumnStretch(5, 3)

        # --- Campos solicitados ---
        self.in_nombre = QLineEdit(); self.in_nombre.setPlaceholderText("Ej: Juan Pérez")
        self.in_usuario = QLineEdit(); self.in_usuario.setPlaceholderText("Ej: j.perez")
        self.in_password = QLineEdit(); self.in_password.setPlaceholderText("Contraseña segura")
        self.in_password.setEchoMode(QLineEdit.Password)
        # Botón para mostrar/ocultar contraseña
        self.btn_toggle_password = QPushButton("Mostrar")
        self.btn_toggle_password.setCheckable(True)
        self.btn_toggle_password.setMaximumWidth(90)
        self.btn_toggle_password.setCursor(Qt.PointingHandCursor)

        self.in_email = QLineEdit(); self.in_email.setPlaceholderText("Ej: nombre@mail.com")

        self.in_rol = QComboBox(); self._setup_combo(self.in_rol)
        self.in_estado = QComboBox(); self._setup_combo(self.in_estado)

        # Añadimos campos al layout (orden sencillo, dos por fila)
        form.addWidget(QLabel("Nombre *"), 0, 0); form.addWidget(self.in_nombre, 0, 1)
        form.addWidget(QLabel("Usuario *"), 0, 2); form.addWidget(self.in_usuario, 0, 3)
        form.addWidget(QLabel("Rol *"), 0, 4); form.addWidget(self.in_rol, 0, 5)
        form.addWidget(QLabel("Contraseña *"), 1, 0)
        # password + toggle en el mismo lugar: ponemos una sub-widget
          # password + toggle en el mismo lugar: ponemos una sub-widget
        pwd_wrap = QWidget(); pwd_h = QHBoxLayout(pwd_wrap); pwd_h.setContentsMargins(0, 0, 0, 0); pwd_h.setSpacing(6)
        pwd_h.addWidget(self.in_password)
        pwd_h.addWidget(self.btn_toggle_password)
        form.addWidget(pwd_wrap, 1, 1, 1, 3)
        #form.addWidget(pwd_wrap, 1, 3)

        form.addWidget(QLabel("Estado *"), 1, 4); form.addWidget(self.in_estado, 1, 5)
        form.addWidget(QLabel("Email"), 2, 0); form.addWidget(self.in_email, 2, 1)
        

        form_wrap.addLayout(form)
        content_l.addWidget(form_panel)
        content_l.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))
        root.addWidget(content)

        # ===================== FOOTER (botones) =====================
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
        self.btn_toggle_password.toggled.connect(self._on_toggle_password)

        # Cambios → marcar dirty
        for w in (self.in_nombre, self.in_usuario, self.in_password, self.in_email):
            w.textChanged.connect(self._mark_dirty)
        for cb in (self.in_rol, self.in_estado):
            cb.currentIndexChanged.connect(self._mark_dirty)

        # Cargar catálogos (roles / estados) asíncrono
        self._load_cat_catalogos_async()

        # Aplicar estilos mínimos (puedes ajustar a tu qss global)
        self._apply_local_qss()

    # -------------------- Helpers UI --------------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        lv = QListView(); lv.setObjectName("ComboPopup"); lv.setUniformItemSizes(True); lv.setSpacing(2)
        cb.setView(lv)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _apply_local_qss(self):
        # Estilos básicos para botones y el panel (esto complementa tu style global)
        self.setStyleSheet("""
        QWidget#UsuariosAgregarPage QLabel { font-weight: 600; }
        QPushButton#BtnGhost { background: transparent; border: 1px solid #cbd5e1; padding: 8px 12px; border-radius: 8px; }
        QPushButton#BtnPrimary { background: #6C5CE7; color: white; border-radius: 8px; padding: 8px 14px; }
        QLineEdit, QComboBox, QTextEdit { padding: 8px; border: 1px solid #e6e9ef; border-radius: 8px; background: white; }
        """)

    def _mark_dirty(self, *_):
        self._dirty = True

    # -------------------- Catálogos --------------------
    def _load_cat_catalogos_async(self):
        # deshabilitar combos en inicio
        for cb in (self.in_rol, self.in_estado):
            cb.setEnabled(False); cb.clear(); cb.addItem("Cargando...", None)

        task = _LoadCatalogosTask(self._catalogos)
        task.signals.done.connect(self._fill_catalogos)
        task.signals.error.connect(lambda msg: NotifyPopup(f"No se pudieron cargar catálogos: {msg}", "error", self).show_centered())
        QThreadPool.globalInstance().start(task)

    def _fill_catalogos(self, data: dict):
        # roles
        self.in_rol.clear()
        roles = data.get("roles") or [{"codigo": "admin", "nombre": "Administrador"}, {"codigo": "vendedor", "nombre": "Vendedor"}]
        self.in_rol.addItem("Seleccione...", None)
        for r in roles:
            code = r.get("codigo") or r.get("id") or str(r)
            name = r.get("nombre") or str(r)
            self.in_rol.addItem(name, code)

        # estados
        self.in_estado.clear()
        estados = data.get("estados_usuarios") or [{"id": 1, "nombre": "Activo"}, {"id": 0, "nombre": "Inactivo"}]
        for e in estados:
            self.in_estado.addItem(e.get("nombre", str(e.get("id"))), e.get("id"))

        # preseleccionar Activo si existe
        idx = self.in_estado.findText("Activo", Qt.MatchContains)
        if idx != -1:
            self.in_estado.setCurrentIndex(idx)

        # habilitar combos
        self.in_rol.setEnabled(True)
        self.in_estado.setEnabled(True)

    # -------------------- Toggle password --------------------
    def _on_toggle_password(self, checked: bool):
        if checked:
            self.in_password.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_password.setText("Ocultar")
        else:
            self.in_password.setEchoMode(QLineEdit.Password)
            self.btn_toggle_password.setText("Mostrar")

    # -------------------- Guardar --------------------
    def _on_guardar(self, abrir_detalle: bool):

        data = self._collect_data()
        ok, errs = self._validate(data)
        if not ok:
            msg = "\n".join(f"• {v}" for v in errs.values())
            NotifyPopup(msg, "warning", self).show_centered()
            return
        # Hash de contraseña (si se indicó)
        raw_pwd = data.pop("contraseña_raw", None)
        if raw_pwd:
            data["contraseña_hash"] = self._hash_password(raw_pwd)
        else:
            # Si no se indicó contraseña, no incluyas la key (posible edición futura)
            data["contraseña_hash"] = None
        
        try:
            # Servicio debe aceptar keys: nombre, usuario, contraseña_hash, rol, email, activo
            new_id = self.service.create_user(data)
        except Exception as ex:
            NotifyPopup(f"Error al guardar: {ex}", "error", self).show_centered()
            return
        logger.error("Guardar25")
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
        campos = [
            self.in_nombre.text().strip(), self.in_usuario.text().strip(),
            self.in_password.text().strip(), self.in_email.text().strip()
        ]
        if any(campos):
            return True
        if any(cb.currentData() for cb in (self.in_rol, self.in_estado)):
            return True
        return False

    # -------------------- Utils --------------------
    def _collect_data(self) -> Dict[str, Any]:
        # Nota: retornamos también 'contraseña_raw' para hashing local antes de enviar
        return {
            "nombre": self.in_nombre.text().strip() or None,
            "usuario": self.in_usuario.text().strip() or None,
            "contraseña_raw": self.in_password.text() or None,
            "rol": self.in_rol.currentData(),
            "email": self.in_email.text().strip() or None,
            "activo": int(self.in_estado.currentData()) if self.in_estado.currentData() is not None else None,
        }

    def _validate(self, d: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        errs: Dict[str, str] = {}
        if not d["nombre"]:
            errs["nombre"] = "El nombre es obligatorio."
        if not d["usuario"]:
            errs["usuario"] = "El nombre de usuario es obligatorio."
        if d.get("contraseña_raw") is None or d.get("contraseña_raw") == "":
            errs["contraseña"] = "La contraseña es obligatoria."
        elif len(d.get("contraseña_raw", "")) < 8:
            errs["contraseña"] = "La contraseña debe tener al menos 8 caracteres."
        if d.get("email"):
            # validación simple de email
            if "@" not in d["email"] or "." not in d["email"].split("@")[-1]:
                errs["email"] = "Email inválido."
        if d.get("rol") is None:
            errs["rol"] = "Seleccioná un rol."
        if d.get("activo") is None:
            errs["activo"] = "Seleccioná el estado."
        return (len(errs) == 0, errs)

    def _hash_password(self, password: str) -> str:
        """
        Genera un hash seguro con PBKDF2-HMAC-SHA256 y salt.
        Se devuelve en formato: salt$hex(hash)
        """
        if password is None:
            return None
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return binascii.hexlify(salt).decode() + "$" + binascii.hexlify(dk).decode()

    def _limpiar_formulario(self):
        self.in_nombre.clear()
        self.in_usuario.clear()
        self.in_password.clear()
        self.in_email.clear()
        if self.in_rol.count() > 0:
            self.in_rol.setCurrentIndex(0)
        if self.in_estado.count() > 0:
            # preseleccionar Activo si aparece
            idx = self.in_estado.findText("Activo", Qt.MatchContains)
            self.in_estado.setCurrentIndex(idx if idx != -1 else 0)
        self._dirty = False

