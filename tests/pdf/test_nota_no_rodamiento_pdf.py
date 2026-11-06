from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.mark.parametrize("origen", ["facturas", "documentacion"])
def test_ambas_pantallas_generan_pdf_con_firma_y_sello(monkeypatch, tmp_path, origen):
    from PySide6.QtWidgets import QApplication
    from app.ui.documentacion import nota_no_rodamiento as nota
    from app.ui.pages import facturas_consultar, documentacion_page

    app = QApplication.instance() or QApplication([])
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    monkeypatch.setattr(nota.os.path, "expanduser", lambda _: str(tmp_path))
    original_image = nota.Image
    images = []

    def track_image(filename, *args, **kwargs):
        image = original_image(filename, *args, **kwargs)
        images.append((Path(filename), kwargs.get("mask"), image))
        return image

    monkeypatch.setattr(nota, "Image", track_image)
    cliente = {"id": 1, "nombre": "Cliente", "apellido": "Prueba", "nro_doc": "123"}
    vehiculo = {"id": 2, "marca": "Zanella", "modelo": "ZB 110", "numero_cuadro": "PRUEBA", "numero_motor": "PRUEBA", "color": "Gris oscuro", "anio": 2027}
    if origen == "facturas":
        session = Mock()
        session.execute.return_value.mappings.return_value.first.return_value = vehiculo
        monkeypatch.setattr(facturas_consultar, "SessionLocal", lambda: session)
        opened = Mock(return_value=True)
        monkeypatch.setattr(facturas_consultar.QDesktopServices, "openUrl", opened)
        page = SimpleNamespace(
            _factura_id=5,
            _factura={"cliente_id": 1, "cliente_nombre": "Cliente", "cliente_apellido": "Prueba", "cliente_nro_doc": "123"},
            setCursor=Mock(),
        )
        facturas_consultar.FacturasConsultarPage._on_nota_no_rodamiento(page)
        session.close.assert_called_once()
    else:
        opened = Mock()
        monkeypatch.setattr(documentacion_page.os, "startfile", opened)
        monkeypatch.setattr(documentacion_page.popUp, "toast", Mock())
        page = SimpleNamespace(_selected_cliente=cliente, _selected_vehiculo=vehiculo)
        documentacion_page.DocumentacionPage._generar_pdf(page)
    opened.assert_called_once()
    pdf = downloads / "nota_no_rodamiento_1_2.pdf"
    assert pdf.read_bytes().startswith(b"%PDF-")
    firmas = [(mask, image) for filename, mask, image in images if filename == nota.paths.FIRMA_CON_SELLO]
    assert len(firmas) == 1
    mask, firma = firmas[0]
    assert mask == "auto"
    assert firma.drawWidth / firma.drawHeight == pytest.approx(firma.imageWidth / firma.imageHeight)
    assert all(filename != nota.paths.FIRMA_ADMIN for filename, _, _ in images)
    app.processEvents()


def test_nota_no_rodamiento_muestra_lca_si_corresponde(monkeypatch):
    from app.ui.documentacion import nota_no_rodamiento as nota

    captured = {}

    class FakeDoc:
        width = 500

        def __init__(self, *args, **kwargs):
            pass

        def build(self, story):
            captured["story"] = story

    monkeypatch.setattr(nota, "SimpleDocTemplate", FakeDoc)
    cliente = {"id": 1, "nombre": "Cliente", "apellido": "QA", "tipo_doc": "DNI", "nro_doc": "123", "direccion": "Calle"}
    veh = {
        "id": 1,
        "marca": "QA",
        "modelo": "Moto",
        "numero_cuadro": "C1",
        "numero_motor": "M1",
        "lca": "IF-TEST",
        "color": "Negro",
        "anio": "2026",
    }

    nota.generar_nota_no_rodamiento_pdf(cliente, veh)

    text = "\n".join(
        element.getPlainText()
        for element in captured["story"]
        if hasattr(element, "getPlainText")
    )
    assert "LCA: IF-TEST" in text


def test_nota_no_rodamiento_no_muestra_lca_si_esta_vacio(monkeypatch):
    from app.ui.documentacion import nota_no_rodamiento as nota

    captured = {}

    class FakeDoc:
        width = 500

        def __init__(self, *args, **kwargs):
            pass

        def build(self, story):
            captured["story"] = story

    monkeypatch.setattr(nota, "SimpleDocTemplate", FakeDoc)
    cliente = {"id": 1, "nombre": "Cliente", "apellido": "QA", "tipo_doc": "DNI", "nro_doc": "123", "direccion": "Calle"}
    veh = {
        "id": 1,
        "marca": "QA",
        "modelo": "Moto",
        "numero_cuadro": "C1",
        "numero_motor": "M1",
        "lca": "",
        "color": "Negro",
        "anio": "2026",
    }

    nota.generar_nota_no_rodamiento_pdf(cliente, veh)

    text = "\n".join(
        element.getPlainText()
        for element in captured["story"]
        if hasattr(element, "getPlainText")
    )
    assert "LCA" not in text


def test_nota_no_rodamiento_no_imprime_none_en_documento(monkeypatch):
    from app.ui.documentacion import nota_no_rodamiento as nota

    captured = {}

    class FakeDoc:
        width = 500

        def __init__(self, *args, **kwargs):
            pass

        def build(self, story):
            captured["story"] = story

    monkeypatch.setattr(nota, "SimpleDocTemplate", FakeDoc)
    cliente = {
        "id": 1,
        "nombre": "JAVIER ANTONIO",
        "apellido": "ABATE",
        "tipo_doc": None,
        "nro_doc": "20329486177",
        "direccion": "JUAN MANUEL DE ROSAS 298",
    }
    veh = {
        "id": 1,
        "marca": "QA",
        "modelo": "Moto",
        "numero_cuadro": "C1",
        "numero_motor": "M1",
    }

    nota.generar_nota_no_rodamiento_pdf(cliente, veh)

    text = "\n".join(
        element.getPlainText()
        for element in captured["story"]
        if hasattr(element, "getPlainText")
    )
    assert "DNI/CUIT/CUIL: 20329486177" in text
    assert "None" not in text
