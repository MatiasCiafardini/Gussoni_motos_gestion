from __future__ import annotations
from typing import Any, Dict, Optional, Tuple, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox, QTextEdit,
    QPushButton, QHBoxLayout, QSizePolicy, QListView, QFrame, QSpacerItem, QMessageBox
)
from app.ui.widgets.confirm_dialog import ConfirmDialog


# Servicio real (si existe) o fallback
try:
    from app.services.usuarios_service import UsuariosService
except Exception:
    UsuariosService = None  # fallback abajo
from app.domain.usuarios_validaciones import validar_usuario

from app.core.security import hash_password
import app.ui.app_message as popUp


class UsuariosAgregarPage(QWidget):
    """
    Pantalla de Alta de Usuario (estilo detalle, sin título).
    Campos: nombre, usuario, email, rol, estado (activo/inactivo), contraseña y confirmación.
    Botones: Volver | Guardar y seguir | Guardar y abrir detalle
    """

    go_back = Signal()
    go_to_detalle = Signal(int)  # user_id

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.setObjectName("UsuariosAgregarPage")

        self.service = UsuariosService() if UsuariosService else None
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
        self.in_nombre = QLineEdit();   self.in_nombre.setPlaceholderText("Nombre y apellido")
        self.in_usuario = QLineEdit();  self.in_usuario.setPlaceholderText("Usuario")
        self.in_email = QLineEdit();    self.in_email.setPlaceholderText("email@ejemplo.com")

        self.in_rol = QComboBox();      self._setup_combo(self.in_rol);     self.in_rol.addItem("Seleccione...", None)
        self.in_estado = QComboBox();   self._setup_combo(self.in_estado);  self.in_estado.addItem("Activo", 1); self.in_estado.addItem("Inactivo", 0)

        self.in_password = QLineEdit(); self.in_password.setEchoMode(QLineEdit.Password); self.in_password.setPlaceholderText("Contraseña")
        self.in_password2 = QLineEdit(); self.in_password2.setEchoMode(QLineEdit.Password); self.in_password2.setPlaceholderText("Repetir contraseña")

        # (opcional) observaciones, por si más adelante querés persistir notas
        self.in_observaciones = QTextEdit(); self.in_observaciones.setPlaceholderText("Observaciones (opcional)")
        self.in_observaciones.setFixedHeight(70)

        # === Filas (3 columnas) ===
        form.addWidget(QLabel("Nombre *"), 0, 0);    form.addWidget(self.in_nombre, 0, 1)
        form.addWidget(QLabel("Usuario *"), 0, 2);   form.addWidget(self.in_usuario, 0, 3)
        form.addWidget(QLabel("Email"), 0, 4);       form.addWidget(self.in_email, 0, 5)

        form.addWidget(QLabel("Rol *"), 1, 0);       form.addWidget(self.in_rol, 1, 1)
        form.addWidget(QLabel("Estado *"), 1, 2);    form.addWidget(self.in_estado, 1, 3)

        form.addWidget(QLabel("Contraseña *"), 2, 0);   form.addWidget(self.in_password, 2, 1)
        form.addWidget(QLabel("Repetir contraseña *"), 2, 2); form.addWidget(self.in_password2, 2, 3)

        form.addWidget(QLabel("Observaciones"), 3, 0); form.addWidget(self.in_observaciones, 3, 1, 1, 5)

        form_wrap.addLayout(form)
        content_l.addWidget(form_panel)

        content_l.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))
        root.addWidget(content)

        # ===================== FOOTER =====================
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

        for w in (self.in_nombre, self.in_usuario, self.in_email, self.in_password, self.in_password2):
            w.textChanged.connect(self._mark_dirty)
        for cb in (self.in_rol, self.in_estado):
            cb.currentIndexChanged.connect(self._mark_dirty)
        self.in_observaciones.textChanged.connect(self._mark_dirty)

        # Cargar combos
        self._load_roles()

    # -------------------- Setup helpers --------------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        lv = QListView(); lv.setObjectName("ComboPopup"); lv.setUniformItemSizes(True); lv.setSpacing(2)
        cb.setView(lv)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _mark_dirty(self, *_):
        self._dirty = True

    # -------------------- Catálogos --------------------
    def _load_roles(self):
        self.in_rol.clear(); self.in_rol.addItem("Seleccione...", None)
        roles: List[Dict[str, Any]] = []
        try:
            if self.service:
                roles = self.service.get_roles()
        except Exception as e:
            popUp.toast(
                self,
                "No se pudieron cargar roles. Se usarán valores por defecto.",
                kind="warning",
                msec=3000,
            )
            roles = [{"id": 1, "nombre": "Administrador"}, {"id": 2, "nombre": "Vendedor"}]
        for r in roles:
            rid = r.get("id")
            try: rid = int(rid) if rid is not None else None
            except Exception: rid = None
            self.in_rol.addItem(r.get("nombre", f"ID {rid}"), rid)

    # -------------------- Guardar --------------------
    def _on_guardar(self, abrir_detalle: bool):
        data = self._collect_data()
        ok, errs = validar_usuario(data, modo="alta")

        if not ok:
            msg = "\n".join(f"• {v}" for v in errs.values())
            popUp.toast(
                self,
                msg,
                kind="warning",
            )
            return


        # Insertar usando el service si está disponible (ideal: el service hashea)
        try:
            new_id: Optional[int] = None
            if self.service and hasattr(self.service, "create_usuario"):
                new_id = int(self.service.create_usuario(data))  # el service debería hashear y mapear campos
            else:
                # Fallback directo a repo + hashing local
                from app.repositories.usuarios_repository import UsuariosRepository
                repo = UsuariosRepository()
                to_db = {
                    "nombre": data["nombre"],
                    "usuario": data["usuario"],
                    "contrasenia_hash": self._hash_password(data["password"]),  # hash local
                    "rol": self._map_rol_texto(data["rol_id"]),
                    "email": data["email"],
                    "activo": 1 if data["estado_id"] == 1 else 0,
                }
                new_id = int(repo.insert(to_db))
        except Exception as ex:
            popUp.error(
                self,
                "Error al guardar usuario",
                str(ex),
            )
            return


        if new_id is None:
            popUp.toast(
                self,
                "No se pudo obtener el ID del usuario creado.",
                kind="error",
            )
            return


        self._dirty = False
        if abrir_detalle:
            popUp.toast(
                self,
                "Usuario guardado correctamente.\nAbriendo detalle…",
                kind="success",
            )
            self.go_to_detalle.emit(int(new_id))

        else:
            popUp.toast(
                self,
                "Usuario guardado correctamente.",
                kind="success",
            )
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
            self.in_nombre.text().strip(), self.in_usuario.text().strip(),
            self.in_email.text().strip(), self.in_password.text().strip(),
            self.in_password2.text().strip(), self.in_observaciones.toPlainText().strip()
        ]
        if any(campos_texto):
            return True
        if any(cb.currentData() for cb in (self.in_rol, self.in_estado)):
            return True
        return False

    # -------------------- Utils --------------------
    def _collect_data(self) -> Dict[str, Any]:
        return {
            "nombre": self.in_nombre.text().strip() or None,
            "usuario": self.in_usuario.text().strip() or None,
            "email": self.in_email.text().strip() or None,
            "rol_id": self._coerce_int(self.in_rol.currentData()),
            "estado_id": self._coerce_int(self.in_estado.currentData()),  # 1 activo / 0 inactivo
            "password": self.in_password.text(),
            "password2": self.in_password2.text(),
            "observaciones": self.in_observaciones.toPlainText().strip() or None,
        }


    def _coerce_int(self, v: Any) -> Optional[int]:
        if v is None: return None
        if isinstance(v, dict): v = v.get("id")
        try: return int(v)
        except Exception: return None

    def _map_rol_texto(self, rol_id: Optional[int]) -> Optional[str]:
        if rol_id is None: return None
        return "admin" if rol_id == 1 else "vendedor"

    def _hash_password(self, pwd: str) -> str:
        """
        Hash rápido con salt: salt(hex)$sha256(salt+pwd)
        (Si tu service ya hashea, no se usa esto.)
        """
        return hash_password(pwd)

    def _limpiar_formulario(self):
        self.in_nombre.clear()
        self.in_usuario.clear()
        self.in_email.clear()
        self.in_password.clear()
        self.in_password2.clear()
        self.in_rol.setCurrentIndex(0)
        self.in_estado.setCurrentIndex(0)
        self.in_observaciones.clear()
