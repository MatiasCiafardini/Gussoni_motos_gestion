from __future__ import annotations

from sqlalchemy import text

from tests.conftest import build_factura_payload
from tests.fixtures.arca_fakes import FakeWSFEConError, FakeWSFETimeoutDespuesDeAutorizar


def test_error_comunicacion_conserva_numero_venta_y_stock_hasta_confirmar(
    db,
    cliente_id,
    vehiculo_id,
    factura_service_factory,
):
    svc = factura_service_factory(wsfe=FakeWSFEConError("ARCA no responde"))
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id, pto_vta=2)

    factura_id = svc.create_factura_completa(cabecera, items)
    result = svc.autorizar_en_arca(factura_id)

    factura = db.execute(text("SELECT estado_id, cae, observaciones, venta_id FROM facturas WHERE id=:id"), {"id": factura_id}).mappings().first()
    vehiculo_estado = db.execute(text("SELECT estado_stock_id FROM vehiculos WHERE id=:id"), {"id": vehiculo_id}).scalar()
    movimientos_venta = db.execute(
        text("SELECT COUNT(*) FROM stock_movimientos WHERE vehiculo_id=:id AND tipo_movimiento='VENTA'"),
        {"id": vehiculo_id},
    ).scalar()
    movimientos_anulacion = db.execute(
        text("SELECT COUNT(*) FROM stock_movimientos WHERE vehiculo_id=:id AND tipo_movimiento='ANULACION'"),
        {"id": vehiculo_id},
    ).scalar()
    venta_estado = db.execute(text("SELECT estado_id FROM ventas WHERE id=:id"), {"id": factura["venta_id"]}).scalar()

    assert result["aprobada"] is False
    assert result["rechazada"] is False
    assert result["estado_incierto"] is True
    assert factura["cae"] is None
    assert factura["estado_id"] == svc.ESTADO_ERROR_COMUNICACION
    assert "Pendiente de confirmacion" in factura["observaciones"]
    assert vehiculo_estado == 3
    assert movimientos_venta == 1
    assert movimientos_anulacion == 0
    assert venta_estado != svc.ESTADO_VENTA_CANCELADA


def test_timeout_despues_de_autorizar_recupera_cae_sin_duplicar(
    db, cliente_id, vehiculo_id, factura_service_factory
):
    wsfe = FakeWSFETimeoutDespuesDeAutorizar(
        ultimo_autorizado=0,
        aprobada=True,
        cae="CAE-RECUPERADO",
        vto_cae="20301231",
    )
    svc = factura_service_factory(wsfe=wsfe)
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id, pto_vta=2)
    factura_id = svc.create_factura_completa(cabecera, items)

    result = svc.autorizar_en_arca(factura_id)
    factura = db.execute(
        text("SELECT numero,estado_id,cae FROM facturas WHERE id=:id"),
        {"id": factura_id},
    ).mappings().one()

    assert result["aprobada"] is True
    assert result["cae"] == "CAE-RECUPERADO"
    assert factura["numero"] == 1
    assert factura["estado_id"] == svc.ESTADO_AUTORIZADA
    assert factura["cae"] == "CAE-RECUPERADO"
    assert len(wsfe.solicitudes) == 1


def test_factura_incierta_bloquea_la_siguiente_emision(
    cliente_id, vehiculo_id, factura_service_factory
):
    import pytest

    svc = factura_service_factory(wsfe=FakeWSFEConError("ARCA no responde"))
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id, pto_vta=2)
    factura_id = svc.create_factura_completa(cabecera, items)
    svc.autorizar_en_arca(factura_id)

    with pytest.raises(RuntimeError, match="respuesta pendiente de ARCA"):
        svc.create_factura_completa(cabecera, items)


def test_sincronizacion_recupera_incierta_sin_cambiar_numero(
    db, cliente_id, vehiculo_id, factura_service_factory
):
    wsfe = FakeWSFEConError("ARCA no responde")
    svc = factura_service_factory(wsfe=wsfe)
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id, pto_vta=2)
    factura_id = svc.create_factura_completa(cabecera, items)
    svc.autorizar_en_arca(factura_id)
    numero_original = db.execute(
        text("SELECT numero FROM facturas WHERE id=:id"), {"id": factura_id}
    ).scalar_one()

    wsfe.comprobantes[numero_original] = {
        "resultado": "A",
        "cae": "CAE-RECUPERADO-DESPUES",
        "fecha_cae": "20260813",
        "vto_cae": "20301231",
        "errores": [],
        "observaciones": [],
    }
    resumen = svc.sincronizar_borradores_con_arca()
    factura = db.execute(
        text("SELECT numero,estado_id,cae FROM facturas WHERE id=:id"),
        {"id": factura_id},
    ).mappings().one()

    assert resumen["aprobadas"] == 1
    assert factura["numero"] == numero_original
    assert factura["estado_id"] == svc.ESTADO_AUTORIZADA
    assert factura["cae"] == "CAE-RECUPERADO-DESPUES"
    assert len(wsfe.solicitudes) == 1


def test_sincronizacion_reintenta_mismo_numero_si_arca_confirma_que_es_el_proximo(
    db, cliente_id, vehiculo_id, factura_service_factory
):
    wsfe = FakeWSFEConError("Solicitud no recibida")
    svc = factura_service_factory(wsfe=wsfe)
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id, pto_vta=2)
    factura_id = svc.create_factura_completa(cabecera, items)
    svc.autorizar_en_arca(factura_id)
    numero_original = db.execute(
        text("SELECT numero FROM facturas WHERE id=:id"), {"id": factura_id}
    ).scalar_one()

    wsfe.fallar = False
    wsfe.cae = "CAE-REINTENTO-SEGURO"
    resumen = svc.sincronizar_borradores_con_arca()
    factura = db.execute(
        text("SELECT numero,estado_id,cae FROM facturas WHERE id=:id"),
        {"id": factura_id},
    ).mappings().one()

    assert resumen["aprobadas"] == 1
    assert factura["numero"] == numero_original
    assert factura["cae"] == "CAE-REINTENTO-SEGURO"
    assert factura["estado_id"] == svc.ESTADO_AUTORIZADA
    assert [s["factura"]["numero"] for s in wsfe.solicitudes] == [numero_original, numero_original]
