from __future__ import annotations


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
    assert "Expediente / IF: IF-TEST" in text


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
    assert "Expediente / IF" not in text


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
