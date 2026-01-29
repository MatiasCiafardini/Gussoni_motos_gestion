from __future__ import annotations
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, QRect, QEvent, Signal
from PySide6.QtWidgets import QComboBox, QListView, QAbstractItemView, QLineEdit
from PySide6.QtGui import QStandardItemModel, QStandardItem

import app.ui.app_message as popUp
from app.services.clientes_service import ClientesService


def _cliente_label(c: Dict[str, Any]) -> str:
    nombre = f"{c.get('nombre', '')} {c.get('apellido', '')}".strip()
    doc = f"{c.get('tipo_doc', '')} {c.get('nro_doc', '')}".strip()
    label = nombre
    if doc:
        label += f" ({doc})"
    return label or "(sin nombre)"


class ClienteSelectorCombo(QComboBox):
    cliente_selected = Signal(dict)
    cliente_cleared = Signal()
    def __init__(self, clientes_service: ClientesService, parent=None) -> None:
        super().__init__(parent)

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

        self._svc = clientes_service
        self._results: List[Dict[str, Any]] = []
        self._selected: Optional[Dict[str, Any]] = None

        le = self.lineEdit()
        le.addAction(le.findChild(type(le.addAction)), QLineEdit.TrailingPosition)

        le.setPlaceholderText("Buscar cliente...")
        le.setClearButtonEnabled(True)

        self._popup = QListView()
        self._popup.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self._popup.setFocusPolicy(Qt.NoFocus)
        self._popup.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._popup.setSelectionMode(QAbstractItemView.SingleSelection)

        fm = self._popup.fontMetrics()
        row_h = max(24, fm.height() + 8)

        self._popup.setStyleSheet(f"""
        QListView {{
            background: #ffffff;
            border: 1px solid #cfcfcf;
            border-radius: 6px;
            padding: 4px;
        }}
        QListView::item {{
            padding: 6px 8px;
            min-height: {row_h}px;
        }}
        QListView::item:selected {{
            background: #6c63ff;
            color: white;
        }}
        QListView::item:hover {{
            background: #e8e7ff;
        }}
        """)

        self._model = QStandardItemModel(self._popup)
        self._popup.setModel(self._model)
        self._popup.clicked.connect(self._on_popup_clicked)

        self.installEventFilter(self)
        le.installEventFilter(self)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._do_search)

        le.textChanged.connect(self._on_text_changed)

    @property
    def selected_cliente(self) -> Optional[Dict[str, Any]]:
        return self._selected

    # -------- búsqueda --------

    def _on_text_changed(self, text: str) -> None:
        # Si había un cliente seleccionado
        if self._selected is not None:
            # Caso 1: el usuario borró todo (❌ o Ctrl+A + Delete)
            if not text.strip():
                self._selected = None
                self._popup.hide()
                self.cliente_cleared.emit()
                return

            # Caso 2: el usuario empieza a escribir algo nuevo
            self._selected = None
            self._popup.hide()
            self.cliente_cleared.emit()
            self._timer.start()
            return

        # ---- Sin cliente seleccionado ----
        if not text.strip():
            self._popup.hide()
            return

        self._timer.start()






    def _do_search(self) -> None:
        text = (self.lineEdit().text() or "").strip()
        if len(text) < 4:
            self._model.clear()
            self._popup.hide()
            return

        filtros = {
            "q": text,
            "page": 1,
            "page_size": 20,
        }


        try:
            rows, _ = self._svc.search(filtros, page=1, page_size=20)
        except Exception as ex:
            popUp.toast(self, f"Error al buscar clientes: {ex}", kind="error")
            rows = []

        self._results = rows or []
        self._model.clear()

        for c in self._results:
            it = QStandardItem(_cliente_label(c))
            it.setData(c, Qt.UserRole)
            self._model.appendRow(it)

        if self._model.rowCount():
            self._show_popup()
        else:
            self._popup.hide()

    def _show_popup(self) -> None:
        le = self.lineEdit()
        pos = le.mapToGlobal(le.rect().bottomLeft())
        h = min(220, self._popup.sizeHintForRow(0) * self._model.rowCount() + 6)
        self._popup.setGeometry(QRect(pos.x(), pos.y(), le.width(), h))
        self._popup.show()
        self._popup.raise_()

    def _on_popup_clicked(self, index) -> None:
        item = self._model.itemFromIndex(index)
        data = item.data(Qt.UserRole) if item else None
        if not isinstance(data, dict):
            return

        self._selected = data
        le = self.lineEdit()

        le.blockSignals(True)
        le.setText(_cliente_label(data))
        le.blockSignals(False)

        self._popup.hide()
        self.cliente_selected.emit(data)
        self.clearFocus()




    # -------- eventos --------

    def eventFilter(self, obj, event) -> bool:
        if event.type() in (QEvent.FocusOut, QEvent.MouseButtonPress):
            self._popup.hide()

            # Si quedó vacío, forzamos limpieza
            if not (self.lineEdit().text() or "").strip():
                if self._selected is not None:
                    self._selected = None
                    self.lineEdit().setReadOnly(False)
                    self.cliente_cleared.emit()


        return super().eventFilter(obj, event)


    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._popup.hide()
