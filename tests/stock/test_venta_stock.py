from __future__ import annotations

from sqlalchemy import text

from tests.conftest import build_factura_payload
from tests.fixtures.arca_fakes import FakeWSFE


def test_venta_autorizada_deja_stock_vendido_y_movimiento(
    db,
    cliente_id,
    vehiculo_id,
    factura_service_factory,
):
    svc = factura_service_factory(wsfe=FakeWSFE(ultimo_autorizado=0, aprobada=True))
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id)
    factura_id = svc.create_factura_completa(cabecera, items)

    vehiculo_estado = db.execute(text("SELECT estado_stock_id FROM vehiculos WHERE id=:id"), {"id": vehiculo_id}).scalar()
    movimiento = db.execute(
        text(
            """
            SELECT estado_stock_anterior_id, estado_stock_nuevo_id
            FROM stock_movimientos
            WHERE vehiculo_id=:id AND origen_id=:factura AND tipo_movimiento='VENTA'
            """
        ),
        {"id": vehiculo_id, "factura": factura_id},
    ).mappings().first()

    assert vehiculo_estado == 3
    assert movimiento["estado_stock_anterior_id"] == 1
    assert movimiento["estado_stock_nuevo_id"] == 3
