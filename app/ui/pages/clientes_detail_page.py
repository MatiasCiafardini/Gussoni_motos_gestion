from __future__ import annotations
from typing import Any, Dict, Optional
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel, QListView, QSizePolicy, QMessageBox
)

from app.services.clientes_service import ClientesService
from app.ui.widgets.confirm_dialog import ConfirmDialog


class ClientesDetailPage(QWidget):
    """
    Detalle de un cliente:
    - Campos de lectura/edición con el mismo estilo de filtros.
    - Al entrar: todo deshabilitado (modo lectura).
    - Botonera: Editar / Guardar / Cancelar / Volver (centrada).
    - Volver confirma si hay edición pendiente.
    """
    navigate_back = Signal()

    def __init__(self, cliente_id: int, parent: Optional[Widget] = None):
        super().__init__(parent)
        self.setObjectName("ClientesDetailPage")

        self.service = ClientesService()
        self.cliente_id = cliente_id
        self.data: Dict[str, Any] = {}
        self.edit_mode = False

        # ---------- Controles ----------
        # Línea 0
        self.in_nombre = QLineEdit();     self.in_nombre.setPlaceholderText("Nombre")
        self.in_apellido = QLineEdit();   self.in_apellido.setPlaceholderText("Apellido")

        # Línea 1
        self.in_tipo_doc = QComboBox();   self._setup_combo(self.in_tipo_doc)
        self.in_nro_doc = QLineEdit();    self.in_nro_doc.setPlaceholderText("N° Documento")
        self.in_nro_doc.setValidator(QIntValidator(0, 99999999, self))

        # Línea 2
        self.in_email = QLineEdit();      self.in_email.setPlaceholderText("Email")
        self.in_telefono = QLineEdit();   self.in_telefono.setPlaceholderText("Teléfono")

        # Línea 3
        self.in_direccion = QLineEdit();  self.in_direccion.setPlaceholderText("Dirección")
        self.in_estado = QComboBox();     self._setup_combo(self.in_estado)

        # Observaciones
        self.in_observ = QTextEdit()
        self.in_observ.setPlaceholderText("Observaciones")
        self.in_observ.setMinimumHeight(80)

        # ---------- Botonera del pie (centrada) ----------
        self.btn_edit = QPushButton("Editar");      self.btn_edit.setObjectName("BtnPrimary")
        self.btn_save = QPushButton("Guardar");     self.btn_save.setObjectName("BtnPrimary")
        self.btn_cancel = QPushButton("Cancelar");  self.btn_cancel.setObjectName("BtnFlat")
        self.btn_back = QPushButton("Volver");      self.btn_back.setObjectName("BtnGhost")
        for b in (self.btn_edit, self.btn_save, self.btn_cancel, self.btn_back):
            b.setMinimumWidth(140)

        # ---------- Layout ----------
        for w in (
            self.in_nombre, self.in_apellido, self.in_tipo_doc, self.in_nro_doc,
            self.in_email, self.in_telefono, self.in_direccion, self.in_estado
        ):
            w.setMinimumHeight(36)

        grid = QGridLayout()
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1); grid.setColumnStretch(3, 3)
        grid.setColumnStretch(4, 1); grid.setColumnStretch(5, 3)
        grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)

        row = 0
        grid.addWidget(QLabel("Nombre"), row, 0);       grid.addWidget(self.in_nombre, row, 1)
        grid.addWidget(QLabel("Apellido"), row, 2);     grid.addWidget(self.in_apellido, row, 3)

        row += 1
        grid.addWidget(QLabel("Tipo doc"), row, 0);     grid.addWidget(self.in_tipo_doc, row, 1)
        grid.addWidget(QLabel("N° Documento"), row, 2); grid.addWidget(self.in_nro_doc, row, 3)

        row += 1
        grid.addWidget(QLabel("Email"), row, 0);        grid.addWidget(self.in_email, row, 1)
        grid.addWidget(QLabel("Teléfono"), row, 2);     grid.addWidget(self.in_telefono, row, 3)

        row += 1
        grid.addWidget(QLabel("Dirección"), row, 0);    grid.addWidget(self.in_direccion, row, 1)
        grid.addWidget(QLabel("Estado"), row, 2);       grid.addWidget(self.in_estado, row, 3)

        row += 1
        grid.addWidget(QLabel("Observaciones"), row, 0, Qt.AlignTop)
        grid.addWidget(self.in_observ, row, 1, 1, 5)

        root = QVBoxLayout(self)
        title = QLabel(f"Cliente #{self.cliente_id}")
        title.setObjectName("KpiValue")
        root.addWidget(title)
        root.addLayout(grid)
        root.addStretch(1)

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

        # Estados iniciales
        self._set_editable(False)
        self._update_buttons()

        # Señales
        self.btn_edit.clicked.connect(self._toggle_edit)
        self.btn_cancel.clicked.connect(self._cancel_edit)
        self.btn_save.clicked.connect(self._save)
        self.btn_back.clicked.connect(self._on_back_clicked)

        # Carga inicial
        self._load_lookups()
        self._load_data()

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
            self.in_nombre, self.in_apellido, self.in_tipo_doc, self.in_nro_doc,
            self.in_email, self.in_telefono, self.in_direccion, self.in_estado, self.in_observ
        ):
            w.setEnabled(enabled)

    def _update_buttons(self):
        if self.edit_mode:
            self.btn_edit.hide()
            self.btn_cancel.show()
            self.btn_save.show()
            self.btn_back.show()
        else:
            self.btn_edit.show()
            self.btn_cancel.hide()
            self.btn_save.hide()
            self.btn_back.show()

    def _toggle_edit(self):
        self.edit_mode = True
        self._set_editable(True)
        self._update_buttons()

    def _cancel_edit(self):
        self.edit_mode = False
        self._set_editable(False)
        self._fill_fields(self.data)  # restauro valores
        self._update_buttons()

    # ---------------------- Data ----------------------
    def _load_lookups(self):
        # Tipos de documento
        self.in_tipo_doc.clear()
        try:
            tipos = self.service.get_tipos_documento()
        except Exception:
            tipos = None
        if not tipos:
            tipos = [{"codigo": "DNI", "nombre": "DNI"}, {"codigo": "CUIT", "nombre": "CUIT"}, {"codigo": "CUIL", "nombre": "CUIL"}]
        for t in tipos:
            codigo = t.get("codigo") or t.get("nombre") or ""
            nombre = t.get("nombre") or t.get("codigo") or codigo
            self.in_tipo_doc.addItem(nombre, codigo)

        # Estados (1 Activo / 0 Inactivo)
        self.in_estado.clear()
        try:
            estados = self.service.get_estados_clientes()
        except Exception:
            estados = None
        if not estados:
            estados = [{"id": 10, "nombre": "Activo"}, {"id": 11, "nombre": "Inactivo"}]
        for e in estados:
            self.in_estado.addItem(e.get("nombre", f"ID {e.get('id')}"), e.get("id"))

    def _load_data(self):
        data = self.service.get(self.cliente_id)
        if not data:
            QMessageBox.warning(self, "Clientes", "No se encontró el cliente.")
            self.navigate_back.emit()
            return
        self.data = data
        self._fill_fields(data)

    def _fill_fields(self, d: Dict[str, Any]):
        self.in_nombre.setText(str(d.get("nombre", "") or ""))
        self.in_apellido.setText(str(d.get("apellido", "") or ""))
        self._set_combo_by_value(self.in_tipo_doc, d.get("tipo_doc") or d.get("tipo_documento"))
        self.in_nro_doc.setText(str(d.get("nro_doc", "") or ""))

        self.in_email.setText(str(d.get("email", "") or ""))
        self.in_telefono.setText(str(d.get("telefono", "") or ""))
        self.in_direccion.setText(str(d.get("direccion", "") or ""))

        # estado_id (1/0) o nombre
        estado_val = d.get("estado_id")
        if estado_val is None and d.get("estado") in ("Activo", "Inactivo"):
            estado_val = 10 if d.get("estado") == "Activo" else 11
        self._set_combo_by_value(self.in_estado, estado_val)

        self.in_observ.setPlainText(str(d.get("observaciones", "") or ""))

    def _set_combo_by_value(self, cb: QComboBox, value: Any):
        if value is None:
            cb.setCurrentIndex(0 if cb.count() else -1)
            return
        for i in range(cb.count()):
            if cb.itemData(i) == value:
                cb.setCurrentIndex(i)
                return
        # si mandaron el texto en vez del data
        if isinstance(value, str):
            idx = cb.findText(value, Qt.MatchFixedString | Qt.MatchCaseSensitive)
            if idx >= 0:
                cb.setCurrentIndex(idx)
                return
        cb.setCurrentIndex(0 if cb.count() else -1)

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
            "apellido": self.in_apellido.text().strip() or None,
            "tipo_doc": self.in_tipo_doc.currentData(),
            "nro_doc": self._only_digits(self.in_nro_doc.text()),
            "email": self.in_email.text().strip() or None,
            "telefono": self.in_telefono.text().strip() or None,
            "direccion": self.in_direccion.text().strip() or None,
            "estado_id": self.in_estado.currentData(),
            "observaciones": self.in_observ.toPlainText().strip() or None,
        }
        # limpio None para no sobreescribir con NULL si tu update ignora faltantes
        return {k: v for k, v in payload.items() if v is not None}

    def _validate(self, d: Dict[str, Any]) -> Dict[str, str]:
        errs: Dict[str, str] = {}
        if not d.get("nombre"):
            errs["nombre"] = "El nombre es obligatorio."
        if not d.get("tipo_doc"):
            errs["tipo_doc"] = "Seleccioná el tipo de documento."
        nro = d.get("nro_doc")
        if not nro:
            errs["nro_doc"] = "Ingresá el número de documento."
        elif not str(nro).isdigit():
            errs["nro_doc"] = "El N° de documento debe contener sólo números."
        email = d.get("email")
        if email and not self._is_valid_email(email):
            errs["email"] = "Email inválido."
        if d.get("estado_id") is None:
            errs["estado_id"] = "Seleccioná el estado."
        return errs

    def _is_valid_email(self, s: str) -> bool:
        s = (s or "").strip()
        if not s:
            return True
        # validación simple
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s))

    def _only_digits(self, s: str) -> Optional[str]:
        s = (s or "").strip()
        digits = "".join(ch for ch in s if ch.isdigit())
        return digits or None

    def _save(self):
        payload = self._collect_payload()
        errs = self._validate(payload)
        if errs:
            msg = "\n".join(f"• {v}" for v in errs.values())
            QMessageBox.warning(self, "Clientes", msg)
            return

        try:
            changed = self.service.update(self.cliente_id, payload)
        except Exception as ex:
            QMessageBox.critical(self, "Clientes", f"Error al guardar: {ex}")
            return
        finally:
            # volver a modo lectura siempre
            self.edit_mode = False
            self._set_editable(False)
            self._load_data()
            self._update_buttons()
