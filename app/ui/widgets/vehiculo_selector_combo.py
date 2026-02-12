from __future__ import annotations
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, QTimer, QStringListModel, Signal
from PySide6.QtWidgets import QLineEdit, QCompleter
from PySide6.QtGui import QStandardItemModel, QStandardItem

import app.ui.app_message as popUp
from app.services.vehiculos_service import VehiculosService
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit,
    QCompleter, QToolButton
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QToolTip


def _vehiculo_label(v: Dict[str, Any]) -> str:
    desc = f"{v.get('marca', '')} {v.get('modelo', '')}".strip()

    if v.get("anio"):
        desc += f" {v['anio']}"

    if v.get("numero_motor"):
        desc += f" | Motor: {v['numero_motor']}"

    if v.get("numero_cuadro"):
        desc += f" | Cuadro: {v['numero_cuadro']}"

    return desc or "(sin descripción)"


class VehiculoSelectorCombo(QLineEdit):

    vehiculo_selected = Signal(dict)
    vehiculo_cleared = Signal()

    def __init__(self, vehiculos_service: VehiculosService, parent=None):
        super().__init__(parent)

        self._svc = vehiculos_service
        self._selected: Optional[Dict[str, Any]] = None
        self._results: List[Dict[str, Any]] = []

        self.setPlaceholderText("Buscar vehículo...")
        self.setClearButtonEnabled(True)

        self._model = QStandardItemModel(self)

        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setMaxVisibleItems(5)
        
        self.setCompleter(self._completer)
    
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

        # 🔥 Aumentar altura de fila
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

    # -------------------------------------------------
    def _force_search(self):

        text = self.text().strip()

        if not text:
            return

        self._do_search()
    def mousePressEvent(self, event):
        super().mousePressEvent(event)

        text = self.text().strip()
        if len(text) >= 3:
            self._force_search()
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

    def _on_text_edited(self, text):

        if not text.strip():
            self._model.clear()
            self._selected = None
            self.vehiculo_cleared.emit()
            return

        self._timer.start()

    # -------------------------------------------------

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
            popUp.toast(self, f"Error al buscar vehículos: {ex}", kind="error")
            rows = []

        self._results = rows or []

        self._model.clear()

        for v in self._results:
            item = QStandardItem(_vehiculo_label(v))
            item.setData(v, Qt.UserRole)
            self._model.appendRow(item)

        # 🔥 mostrar popup sin perder foco
        self._completer.complete()

    # -------------------------------------------------

    def _on_selected(self, text):

        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item.text() == text:
                data = item.data(Qt.UserRole)
                if isinstance(data, dict):
                    self._selected = data
                    self.vehiculo_selected.emit(data)
                break

    # -------------------------------------------------

    @property
    def selected_vehiculo(self):
        return self._selected
