from app.domain.facturas_validaciones import validar_factura


def _cabecera(**overrides):
    cabecera = {
        "tipo": "FB",
        "pto_vta": 3,
        "fecha_emision": "2026-08-14",
        "cliente_id": 1,
        "condicion_iva_receptor_id": 1,
    }
    cabecera.update(overrides)
    return cabecera


def _items():
    return [
        {
            "vehiculo_id": 1,
            "cantidad": 1,
            "precio_unitario": 100,
            "importe_total": 100,
        }
    ]


def test_acepta_codigo_tipo_usado_al_editar_factura():
    ok, errores = validar_factura(
        cabecera=_cabecera(),
        items=_items(),
        es_nota_credito=False,
    )

    assert ok
    assert "Seleccioná el tipo de comprobante." not in errores


def test_rechaza_tipo_vacio():
    ok, errores = validar_factura(
        cabecera=_cabecera(tipo=""),
        items=_items(),
        es_nota_credito=False,
    )

    assert not ok
    assert "Seleccioná el tipo de comprobante." in errores
