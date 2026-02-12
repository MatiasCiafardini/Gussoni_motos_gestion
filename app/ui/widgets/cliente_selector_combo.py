from __future__ import annotations
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLineEdit, QCompleter
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction

import app.ui.app_message as popUp
from app.services.clientes_service import ClientesService
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QToolTip


# -------------------------------------------------
def _cliente_label(c: Dict[str, Any]) -> str:
    nombre = f"{c.get('nombre', '')} {c.get('apellido', '')}".strip()

    if c.get("tipo_doc") and c.get("nro_doc"):
        nombre += f" | {c['tipo_doc']} {c['nro_doc']}"

    return nombre or "(sin nombre)"


# =================================================
class ClienteSelectorCombo(QLineEdit):

    cliente_selected = Signal(dict)
    cliente_cleared = Signal()

    def __init__(self, clientes_service: ClientesService, parent=None):
        super().__init__(parent)

        self._svc = clientes_service
        self._selected: Optional[Dict[str, Any]] = None
        self._results: List[Dict[str, Any]] = []

        self.setPlaceholderText("Buscar cliente...")
        self.setClearButtonEnabled(True)

        # ------------------ MODEL ------------------
        self._model = QStandardItemModel(self)

        # ---------------- COMPLETER ----------------
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setMaxVisibleItems(5)

        self.setCompleter(self._completer)

        # ------------------ TIMER ------------------
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._do_search)

        self.textEdited.connect(self._on_text_edited)
        self._completer.activated.connect(self._on_selected)

        popup = self._completer.popup()
        popup.setMinimumWidth(self.width())
        popup.setUniformItemSizes(False)
        popup.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 🔥 Estética idéntica a VehiculoSelectorCombo
        fm = popup.fontMetrics()
        row_height = max(32, fm.height() + 12)

        popup.setStyleSheet(f"""
            QListView {{
                border: 1px solid #dcdcdc;
                background: white;
            }}

            QListView::item {{
                padding: 8px 10px;
                min-height: {row_height}px;
                border-radius: 6px;
            }}

            QListView::item:hover {{
                background-color: rgba(108, 99, 255, 0.12);
            }}

            QListView::item:selected {{
                background-color: #6c63ff;
                color: white;
            }}
        """)

        # 🔥 Botón forzar búsqueda
        self._search_action = QAction("-", self)
        self._search_action.triggered.connect(self._force_search)
        self.addAction(self._search_action, QLineEdit.TrailingPosition)

    # =================================================
    # 🔥 Forzar búsqueda manual
    def _force_search(self):
        text = self.text().strip()
        if not text:
            return
        self._do_search()
    def event(self, event):

        if event.type() == QEvent.ToolTip:
            text = self.text().strip()
            if not text:
                return True

            fm = self.fontMetrics()
            text_width = fm.horizontalAdvance(text)

            # Solo mostrar si está cortado
            if text_width > self.width() - 10:
                QToolTip.showText(
                    event.globalPos(),
                    text,
                    self
                )
            return True

        return super().event(event)
    # -------------------------------------------------
    # 🔥 Buscar también al hacer click si ya hay texto
    def mousePressEvent(self, event):
        super().mousePressEvent(event)

        text = self.text().strip()
        if len(text) >= 3:
            self._force_search()
    def _update_tooltip(self):
        text = self.text().strip()

        if not text:
            self.setToolTip("")
            return

        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(text)

        # Solo mostrar si está cortado
        if text_width > self.width() - 10:
            self.setToolTip(text)
        else:
            self.setToolTip("")
    def resizeEvent(self, event):
            super().resizeEvent(event)
            self._update_tooltip()
    # =================================================
    def _on_text_edited(self, text):

        if not text.strip():
            self._model.clear()
            self._selected = None
            self.cliente_cleared.emit()
            return

        self._timer.start()
    def select_cliente_externo(self, cliente: Dict[str, Any]) -> None:
        """
        Permite seleccionar un cliente programáticamente
        (por ejemplo cuando se abre desde ClientesDetail).
        """
        if not cliente:
            return

        self._selected = cliente

        # Mostrar texto visible
        self.setText(_cliente_label(cliente))

        # Emitir señal como si el usuario lo hubiera elegido
        self.cliente_selected.emit(cliente)

    # =================================================
    def _do_search(self):

        text = self.text().strip()

        if len(text) < 3:
            return

        try:
            rows, _ = self._svc.search(
                {"q": text},
                page=1,
                page_size=20
            )
        except Exception as ex:
            popUp.toast(self, f"Error al buscar clientes: {ex}", kind="error")
            rows = []

        self._results = rows or []
        self._model.clear()

        for c in self._results:
            item = QStandardItem(_cliente_label(c))
            item.setData(c, Qt.UserRole)
            self._model.appendRow(item)

        # 🔥 Mostrar popup sin perder foco
        self._completer.complete()

    # =================================================
    def _on_selected(self, text):

        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item.text() == text:
                data = item.data(Qt.UserRole)
                if isinstance(data, dict):
                    self._selected = data
                    self.cliente_selected.emit(data)
                break

    # =================================================
    @property
    def selected_cliente(self):
        return self._selected
