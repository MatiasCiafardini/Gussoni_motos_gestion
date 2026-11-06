import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QStackedWidget, QWidget

from app.ui import main_window as module
from app.ui.pages.facturas_consultar import FacturasConsultarPage


class DetailStub(QWidget):
    navigate_back = Signal()
    navigate_to_factura = Signal(int)

    def __init__(self, record_id):
        super().__init__()
        self.record_id = record_id


class InvoiceStub(QWidget):
    go_back = Signal()
    _on_volver = FacturasConsultarPage._on_volver

    def __init__(self, factura_id, parent=None, main_window=None, return_to=None, cliente_id=None):
        super().__init__(parent)
        self._factura_id = factura_id
        self._main_window = main_window
        self._return_to = return_to
        self._cliente_id = cliente_id
        self.btn_volver = QPushButton("Volver", self)
        self.btn_volver.clicked.connect(self._on_volver)


class NavigationWindow(module.MainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.stack = QStackedWidget(self)
        self.setCentralWidget(self.stack)
        self._page_history = []
        self.loading = Mock()
        self.page_vehiculos = QWidget()
        self.page_clientes = QWidget()
        self.page_facturacion = QWidget()
        self.page_facturacion.reload = Mock()
        self.page_remitos = QWidget()
        for page in (self.page_vehiculos, self.page_clientes, self.page_facturacion, self.page_remitos):
            self.stack.addWidget(page)

    def _ensure_catalogs_ready(self, **kwargs):
        pass

    def show_loading(self, text=""):
        pass


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(module, "VehiculoDetailPage", DetailStub)
    monkeypatch.setattr(module, "ClientesDetailPage", DetailStub)
    monkeypatch.setattr(module, "FacturasConsultarPage", InvoiceStub)
    widget = NavigationWindow()
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("origin", ["vehiculo", "cliente"])
def test_factura_vuelve_al_mismo_detalle_y_luego_al_listado_sin_bucle(window, origin):
    listing = window.page_vehiculos if origin == "vehiculo" else window.page_clientes
    window.stack.setCurrentWidget(listing)
    # Repetir el recorrido no debe acumular facturas ni detalles duplicados.
    for _ in range(3):
        if origin == "vehiculo":
            window.open_vehiculo_detail(42)
        else:
            window.open_cliente_detail(42)
        detail = window.stack.currentWidget()
        detail.navigate_to_factura.emit(99)
        invoice = window.stack.currentWidget()
        assert isinstance(invoice, InvoiceStub)
        assert window._page_history == [listing, detail]
        invoice.btn_volver.click()
        assert window.stack.currentWidget() is detail
        assert window._page_history == [listing]
        detail.navigate_back.emit()
        assert window.stack.currentWidget() is listing
        assert window._page_history == []
        assert window.stack.count() == 4


def test_factura_desde_listado_regresa_y_recarga_sin_perder_pagina(window):
    window.stack.setCurrentWidget(window.page_facturacion)
    window.open_page("facturas_consultar", factura_id=99)
    invoice = window.stack.currentWidget()
    invoice.btn_volver.click()
    assert window.stack.currentWidget() is window.page_facturacion
    assert window._page_history == []
    window.page_facturacion.reload.assert_called_once_with(reset_page=False)
