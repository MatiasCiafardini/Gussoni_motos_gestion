import os
from datetime import datetime
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.pages import vehiculos_detail_page as module


@pytest.fixture
def page(monkeypatch):
    app = QApplication.instance() or QApplication([])
    service = Mock()
    service.get.return_value = {
        "id": 42, "marca": "Zanella", "modelo": "ZB 110", "anio": 2027,
        "precio_lista": 1107438.02, "color_id": 1, "estado_stock_id": 2,
        "estado_moto_id": 1, "proveedor_id": 8,
        "numero_cuadro": "CUADRO42", "numero_motor": "MOTOR42",
    }
    service.get_proveedores.return_value = [{"id": 8, "nombre": "Zanella"}]
    service.get_colores.return_value = [{"id": 1, "nombre": "Negro"}]
    service.get_estados_stock.return_value = [{"id": 2, "nombre": "Vendido"}]
    service.get_estados_condicion.return_value = [{"id": 1, "nombre": "Nueva"}]
    service.get_facturacion_history.return_value = [{
        "factura_id": 99, "fecha_emision": datetime(2026, 11, 6),
        "cliente_nombre": "Ana", "cliente_apellido": "Perez",
        "cliente_documento": "12345678", "punto_venta": 2, "numero": 123,
        "comprobante_tipo": "Factura B", "importe_item": 1107438.02,
        "factura_estado": "Autorizada",
    }]
    monkeypatch.setattr(module, "VehiculosService", lambda: service)
    def unexpected_dialog(*args, **kwargs):
        pytest.fail(f"Dialogo inesperado: {args[1:]}")
    monkeypatch.setattr(module.popUp, "warning", unexpected_dialog)
    monkeypatch.setattr(module.popUp, "error", unexpected_dialog)
    widget = module.VehiculoDetailPage(42)
    yield widget, service
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_consulta_sin_editar_no_pide_descartar_y_muestra_comprador(page, monkeypatch):
    widget, service = page
    ask = Mock(return_value=False)
    monkeypatch.setattr(module.popUp, "ask_discard", ask)
    back = Mock()
    widget.navigate_back.connect(back)
    assert not widget.edit_mode
    assert not widget.section_facturacion.isHidden()
    assert "Ana Perez" in widget.tbl_facturacion.item(0, 1).text()
    assert widget.tbl_facturacion.item(0, 2).text() == "Factura B 00002-00000123"
    factura = Mock()
    widget.navigate_to_factura.connect(factura)
    widget.tbl_facturacion.cellWidget(0, 5).click()
    factura.assert_called_once_with(99)
    widget._on_back_clicked()
    ask.assert_not_called()
    back.assert_called_once()
    service.update.assert_not_called()


def test_entrar_en_edicion_sin_cambiar_no_pide_descartar(page, monkeypatch):
    widget, _ = page
    ask = Mock(return_value=False)
    monkeypatch.setattr(module.popUp, "ask_discard", ask)
    widget._toggle_edit()
    widget._on_back_clicked()
    ask.assert_not_called()
    assert not widget.edit_mode


@pytest.mark.parametrize("field", ["precio", "modelo", "observaciones"])
def test_cambios_reales_piden_confirmacion_y_cancelar_restaura(page, monkeypatch, field):
    widget, _ = page
    original = widget._collect_payload()
    ask = Mock(return_value=False)
    monkeypatch.setattr(module.popUp, "ask_discard", ask)
    back = Mock()
    widget.navigate_back.connect(back)
    widget._toggle_edit()
    if field == "precio":
        widget.in_precio.setValue(900000)
    elif field == "modelo":
        widget.in_modelo.setText("Otro modelo")
    else:
        widget.in_observ.setPlainText("Cambio")
    widget._on_back_clicked()
    ask.assert_called_once()
    back.assert_not_called()
    assert widget.edit_mode
    widget._cancel_edit()
    assert widget._collect_payload() == original
    assert not widget.edit_mode
    assert not widget.section_facturacion.isHidden()


def test_guardar_precio_no_deja_consulta_en_edicion(page):
    widget, service = page
    widget._toggle_edit()
    widget.in_precio.setValue(900000)
    service.get.return_value = {**service.get.return_value, "precio_lista": 900000}
    widget._save()
    service.update.assert_called_once()
    assert not widget.edit_mode
    assert widget.btn_save.isHidden()
    assert not widget.section_facturacion.isHidden()
