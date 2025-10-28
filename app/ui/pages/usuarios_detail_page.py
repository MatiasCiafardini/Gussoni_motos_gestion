from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel, QListView, QSizePolicy, QMessageBox, QFrame, QSpacerItem, QDialog
)

# Nota: Asumo que estos servicios manejan la DB
from app.services.usuarios_service import UsuariosService
from app.ui.widgets.confirm_dialog import ConfirmDialog
from app.ui.widgets.password_dialog import ChangePasswordDialog
# Nota: La Notificación la dejo comentada, se usa en la de Agregar.
# from app.ui.notify import NotifyPopup 


class UsuariosDetailPage(QWidget):
    """
    Detalle de un Usuario:
    - Campos de lectura/edición acordes a la tabla 'usuarios' (id, nombre, usuario, rol, email, activo).
    - Incluye campos de solo lectura (ID, fecha_creacion, contraseña_hash)
    - Botonera: Editar / Guardar / Cancelar / Volver.
    """
    navigate_back = Signal()

    def __init__(self, Usuario_id: Optional[int] = None, parent: Optional[QWidget] = None, **kwargs):
        """
        Compatibilidad hacia atrás:
        - Acepta alias: user_id / usuario_id / id_usuario -> mapean a Usuario_id
        - Acepta main_window en kwargs (se guarda si viene)
        """
        # Resolver alias de ID si no vino por nombre original
        if Usuario_id is None:
            Usuario_id = (
                kwargs.pop("user_id", None)
                or kwargs.pop("usuario_id", None)
                or kwargs.pop("id_usuario", None)
            )
        # Guardar main_window si lo pasan (opcional)
        self.main_window = kwargs.pop("main_window", None)
        # Ignorar cualquier otro kwarg desconocido silenciosamente

        if Usuario_id is None:
            raise ValueError("Usuario_id es obligatorio para UsuariosDetailPage")

        super().__init__(parent)
        self.setObjectName("UsuariosDetailPage")

        self.service = UsuariosService()
        self.Usuario_id = int(Usuario_id)
        self.data: Dict[str, Any] = {}
        self.edit_mode = False

        # -------------------- Controles (Adaptados a la tabla 'usuarios') --------------------
        # Línea 0
        self.in_nombre = QLineEdit();     self.in_nombre.setPlaceholderText("Nombre completo")
        self.in_usuario = QLineEdit();    self.in_usuario.setPlaceholderText("Nombre de usuario (Login)")
        self.in_rol = QComboBox();        self._setup_combo(self.in_rol)

        # Línea 1
        self.in_email = QLineEdit();      self.in_email.setPlaceholderText("Email")
        self.in_activo = QComboBox();     self._setup_combo(self.in_activo) # Campo 'activo' (1/0)
        self.btn_password = QPushButton("Cambiar Contraseña..."); self.btn_password.setObjectName("BtnFlat")
        self.btn_password.setMaximumWidth(200)

        # Línea 2 (Solo lectura)
        self.lbl_id = QLabel() 
        self.lbl_creacion = QLabel() 
        self.lbl_hash = QLabel("...") # Contraseña hash (opcional para debug/info)

        # -------------------- Layout (Basado en UsuariosAgregarPage) --------------------
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 16)
        root.setSpacing(10)

        title = QLabel(f"Detalle de Usuario #{self.Usuario_id}")
        title.setObjectName("KpiValue")
        root.addWidget(title)

        form_panel = QFrame(self)
        form_panel.setObjectName("Panel")
        form_panel.setStyleSheet("#Panel { background: transparent; border: none; }")
        form_wrap = QVBoxLayout(form_panel)
        form_wrap.setContentsMargins(0, 0, 0, 0)
        form_wrap.setSpacing(6)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1); grid.setColumnStretch(3, 3)
        grid.setColumnStretch(4, 1); grid.setColumnStretch(5, 3)
        
        # Estilos para campos de entrada
        for w in (self.in_nombre, self.in_usuario, self.in_rol, self.in_email, self.in_activo):
            w.setMinimumHeight(36)

        # Fila 0: Nombre, Usuario, Rol
        grid.addWidget(QLabel("Nombre *"), 0, 0);       grid.addWidget(self.in_nombre, 0, 1)
        grid.addWidget(QLabel("Usuario *"), 0, 2);      grid.addWidget(self.in_usuario, 0, 3)
        grid.addWidget(QLabel("Rol *"), 0, 4);          grid.addWidget(self.in_rol, 0, 5)

        # Fila 1: Email, Activo, Contraseña
        grid.addWidget(QLabel("Email"), 1, 0);          grid.addWidget(self.in_email, 1, 1)
        grid.addWidget(QLabel("Estado *"), 1, 2);       grid.addWidget(self.in_activo, 1, 3)
        grid.addWidget(QLabel("Contraseña"), 1, 4);     grid.addWidget(self.btn_password, 1, 5)
        
        # Fila 2: Info solo lectura
        grid.addWidget(QLabel("ID"), 2, 0);             grid.addWidget(self.lbl_id, 2, 1)
        grid.addWidget(QLabel("Creado"), 2, 2);         grid.addWidget(self.lbl_creacion, 2, 3)
        # grid.addWidget(QLabel("Hash"), 2, 4);           grid.addWidget(self.lbl_hash, 2, 5) # Opcional: mostrar hash

        form_wrap.addLayout(grid)
        root.addWidget(form_panel)
        root.addStretch(1)

        # -------------------- Botonera del pie (centrada) --------------------
        self.btn_edit = QPushButton("Editar");      self.btn_edit.setObjectName("BtnPrimary")
        self.btn_save = QPushButton("Guardar");     self.btn_save.setObjectName("BtnPrimary")
        self.btn_cancel = QPushButton("Cancelar");  self.btn_cancel.setObjectName("BtnFlat")
        self.btn_back = QPushButton("Volver");      self.btn_back.setObjectName("BtnGhost")
        for b in (self.btn_edit, self.btn_save, self.btn_cancel, self.btn_back):
            b.setMinimumWidth(140)

        self._footer = QHBoxLayout()
        self._footer.addStretch(1)
        self._footer.addWidget(self.btn_cancel)
        self._footer.addSpacing(8)
        self._footer.addWidget(self.btn_save)
        self._footer.addSpacing(16)
        self._footer.addWidget(self.btn_edit)
        self._footer.addSpacing(16)
        self._footer.addWidget(self.btn_back)
        self._footer.addStretch(1)
        root.addLayout(self._footer)

        # -------------------- Inicialización --------------------
        self._load_lookups()
        self._load_data()
        self._set_editable(False)
        self._update_buttons()

        # Señales
        self.btn_edit.clicked.connect(self._toggle_edit)
        self.btn_cancel.clicked.connect(self._cancel_edit)
        self.btn_save.clicked.connect(self._save)
        self.btn_back.clicked.connect(self._on_back_clicked)
        self.btn_password.clicked.connect(self._open_password_dialog)

    # ---------------------- Helpers UI ----------------------
    def _setup_combo(self, cb: QComboBox):
        cb.setObjectName("FilterCombo")
        cb.setMinimumHeight(36)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lv = QListView()
        lv.setObjectName("ComboPopup")
        lv.setUniformItemSizes(True)
        lv.setSpacing(2)
        cb.setView(lv)

    def _set_editable(self, enabled: bool):
        for w in (
            self.in_nombre, self.in_usuario, self.in_rol, self.in_email, self.in_activo
        ):
            w.setEnabled(enabled)
        
        # El botón de contraseña siempre debería estar habilitado, pero fuera de modo edición es menos relevante
        self.btn_password.setEnabled(not enabled) # Deshabilitar si está editando otros campos
        
        # Labels de solo lectura
        self.lbl_id.setEnabled(True)
        self.lbl_creacion.setEnabled(True)

    def _update_buttons(self):
        if self.edit_mode:
            self.btn_edit.hide()
            self.btn_password.hide() # Ocultar botón de password al editar otros campos
            self.btn_cancel.show()
            self.btn_save.show()
            self.btn_back.show()
        else:
            self.btn_edit.show()
            self.btn_password.show()
            self.btn_cancel.hide()
            self.btn_save.hide()
            self.btn_back.show()

    def _toggle_edit(self):
        self.edit_mode = True
        self._set_editable(True)
        self._update_buttons()
        # El campo 'usuario' (login) podría ser NO editable para evitar conflictos de integridad.
        # self.in_usuario.setEnabled(False)

    def _cancel_edit(self):
        self.edit_mode = False
        self._set_editable(False)
        self._fill_fields(self.data)  # restauro valores
        self._update_buttons()

    def _open_password_dialog(self):
        dialog = ChangePasswordDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        new_password = dialog.password
        if not new_password:
            return

        try:
            self.service.change_password(self.Usuario_id, new_password)
        except Exception as ex:
            QMessageBox.critical(
                self,
                "Usuarios",
                f"No se pudo actualizar la contraseña.\n\n{ex}",
            )
            return

        QMessageBox.information(
            self,
            "Usuarios",
            "La contraseña se actualizó correctamente.",
        )
        # Recargar la información para mantener consistencia en pantalla
        self._load_data()

    # ---------------------- Data & Lookups ----------------------
    def _load_lookups(self):
        # Roles (hardcodeado como ejemplo, usa tu CatalogosService para real)
        self.in_rol.clear()
        roles = [
            {"codigo": "admin", "nombre": "Administrador"},
            {"codigo": "vendedor", "nombre": "Vendedor"},
            {"codigo": "operador", "nombre": "Operador"}
        ]
        # Nota: En Detalle, NO necesitamos "Seleccione...".
        for r in roles:
            self.in_rol.addItem(r.get("nombre", r.get("codigo")), r.get("codigo"))

        # Activo (tinyint(1) -> 1/0)
        self.in_activo.clear()
        estados = [
            {"id": 1, "nombre": "Activo"},
            {"id": 0, "nombre": "Inactivo"}
        ]
        for e in estados:
            self.in_activo.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

    def _load_data(self):
        # Asumo que self.service.get(id) devuelve un dict con las keys de la tabla
        data = self.service.get(self.Usuario_id)
        if not data:
            QMessageBox.warning(self, "Usuarios", "No se encontró el Usuario.")
            self.navigate_back.emit()
            return
        self.data = data
        self._fill_fields(data)

    def _fill_fields(self, d: Dict[str, Any]):
        # Campos de edición
        self.in_nombre.setText(str(d.get("nombre", "") or ""))
        self.in_usuario.setText(str(d.get("usuario", "") or ""))
        self.in_email.setText(str(d.get("email", "") or ""))
        
        self._set_combo_by_value(self.in_rol, d.get("rol"))
        self._set_combo_by_value(self.in_activo, d.get("activo"))

        # Campos de solo lectura
        self.lbl_id.setText(str(d.get("id", "N/A")))
        
        fecha = d.get("fecha_creacion")
        if fecha:
            # Formato de fecha
            fecha_str = fecha.strftime("%d/%m/%Y %H:%M") if hasattr(fecha, 'strftime') else str(fecha)
        else:
            fecha_str = "N/A"
        self.lbl_creacion.setText(fecha_str)
        # self.lbl_hash.setText(str(d.get("contraseña_hash", "N/A")))

    def _set_combo_by_value(self, cb: QComboBox, value: Any):
        if value is None:
            cb.setCurrentIndex(-1)
            return
        for i in range(cb.count()):
            if cb.itemData(i) == value:
                cb.setCurrentIndex(i)
                return
        # Intentar por texto si el valor es un string y no se encontró por data
        if isinstance(value, str):
            idx = cb.findText(value, Qt.MatchFixedString | Qt.MatchCaseSensitive)
            if idx >= 0:
                cb.setCurrentIndex(idx)
                return
        cb.setCurrentIndex(-1)

    # ---------------------- Back con confirmación ----------------------
    def _on_back_clicked(self):
        if self.edit_mode:
            if not ConfirmDialog.ask_discard(self):
                return
            self._cancel_edit()
        self.navigate_back.emit()

    # ---------------------- Save ----------------------
    def _collect_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "nombre": self.in_nombre.text().strip() or None,
            "usuario": self.in_usuario.text().strip() or None,
            "rol": self.in_rol.currentData(),
            "email": self.in_email.text().strip() or None,
            "activo": self.in_activo.currentData(),
        }
        # Solo enviar los campos que tienen valor
        return {k: v for k, v in payload.items() if v is not None}

    def _validate(self, d: Dict[str, Any]) -> Dict[str, str]:
        errs: Dict[str, str] = {}
        if not d.get("nombre"):
            errs["nombre"] = "El nombre es obligatorio."
        if not d.get("usuario"):
            errs["usuario"] = "El nombre de usuario es obligatorio."
        if not d.get("rol"):
            errs["rol"] = "Seleccioná el rol."
        
        email = d.get("email")
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            errs["email"] = "Email inválido."
            
        if d.get("activo") is None:
            errs["activo"] = "Seleccioná el estado."
        
        return errs

    def _save(self):
        payload = self._collect_payload()
        errs = self._validate(payload)
        
        if errs:
            msg = "\n".join(f"• {v}" for v in errs.values())
            QMessageBox.warning(self, "Usuarios", msg)
            return

        try:
            # Nota: El campo 'contraseña_hash' NO se toca aquí. Se actualiza con el diálogo de contraseña.
            changed = self.service.update(self.Usuario_id, payload)
        except Exception as ex:
            # Aquí puedes añadir lógica para manejar errores específicos de UNIQUE (ej. usuario ya existe)
            QMessageBox.critical(self, "Usuarios", f"Error al guardar: {ex}")
            return
        
        QMessageBox.information(self, "Usuarios", "Usuario actualizado exitosamente.")
        
        # Volver a modo lectura y recargar la data
        self.edit_mode = False
        self._set_editable(False)
        self._load_data()
        self._update_buttons()
