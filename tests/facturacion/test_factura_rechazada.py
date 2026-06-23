from __future__ import annotations

from sqlalchemy import text

from tests.conftest import build_factura_payload
from tests.fixtures.arca_fakes import FakeWSFE


def test_factura_rechazada_revierte_stock_y_cancela_venta(
    db,
    cliente_id,
    vehiculo_id,
    factura_service_factory,
):
    svc = factura_service_factory(
        wsfe=FakeWSFE(ultimo_autorizado=0, aprobada=False, errores=["10016 - rechazo controlado"])
    )
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id)

    factura_id = svc.create_factura_completa(cabecera, items)
    result = svc.autorizar_en_arca(factura_id)

    factura = db.execute(text("SELECT * FROM facturas WHERE id=:id"), {"id": factura_id}).mappings().first()
    vehiculo_estado = db.execute(text("SELECT estado_stock_id FROM vehiculos WHERE id=:id"), {"id": vehiculo_id}).scalar()
    venta_estado = db.execute(text("SELECT estado_id FROM ventas WHERE id=:id"), {"id": factura["venta_id"]}).scalar()
    anulaciones = db.execute(
        text("SELECT COUNT(*) FROM stock_movimientos WHERE vehiculo_id=:id AND tipo_movimiento='ANULACION'"),
        {"id": vehiculo_id},
    ).scalar()

    assert result["rechazada"] is True
    assert factura["estado_id"] == 15
    assert factura["cae"] is None
    assert vehiculo_estado == 1
    assert venta_estado == 33
    assert anulaciones == 1
    assert "rechazo controlado" in result["mensaje"]
