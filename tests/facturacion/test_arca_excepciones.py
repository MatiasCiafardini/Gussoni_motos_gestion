from __future__ import annotations

from sqlalchemy import text

from tests.conftest import build_factura_payload
from tests.fixtures.arca_fakes import FakeWSFEConError


def test_error_comunicacion_arca_no_autoriza_ni_vende_stock(
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
    assert "ARCA no responde" in result["mensaje"]
    assert factura["cae"] is None
    assert factura["estado_id"] == svc.ESTADO_ERROR_COMUNICACION
    assert "Error de comunicacion" in factura["observaciones"]
    assert vehiculo_estado == 1
    assert movimientos_venta == 1
    assert movimientos_anulacion == 1
    assert venta_estado == svc.ESTADO_VENTA_CANCELADA
