from __future__ import annotations

from sqlalchemy import text

from tests.conftest import build_factura_payload
from tests.fixtures.arca_fakes import FakeWSFE


def test_factura_autorizada_crea_venta_detalle_cae_y_vende_stock(
    db,
    cliente_id,
    vehiculo_id,
    factura_service_factory,
):
    svc = factura_service_factory(
        wsfe=FakeWSFE(ultimo_autorizado=22, aprobada=True, cae="CAE-TEST", vto_cae="20301231")
    )
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id, pto_vta=2)

    factura_id = svc.create_factura_completa(cabecera, items)
    result = svc.autorizar_en_arca(factura_id)

    factura = db.execute(text("SELECT * FROM facturas WHERE id=:id"), {"id": factura_id}).mappings().first()
    detalle_count = db.execute(text("SELECT COUNT(*) FROM facturas_detalle WHERE factura_id=:id"), {"id": factura_id}).scalar()
    vehiculo_estado = db.execute(text("SELECT estado_stock_id FROM vehiculos WHERE id=:id"), {"id": vehiculo_id}).scalar()
    movimientos = db.execute(
        text("SELECT COUNT(*) FROM stock_movimientos WHERE vehiculo_id=:id AND tipo_movimiento='VENTA'"),
        {"id": vehiculo_id},
    ).scalar()

    assert result["aprobada"] is True
    assert factura["cliente_id"] == cliente_id
    assert factura["venta_id"] is not None
    assert factura["cae"] == "CAE-TEST"
    assert str(factura["vto_cae"]).replace("-", "") == "20301231"
    assert factura["punto_venta"] == 2
    assert factura["numero"] == 23
    assert detalle_count == 1
    assert vehiculo_estado == 3
    assert movimientos == 1
