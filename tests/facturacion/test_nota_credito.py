from __future__ import annotations

from sqlalchemy import text

from tests.fixtures.arca_fakes import FakeWSFE
from tests.fixtures.db_factory import insert_factura_autorizada


def test_nota_credito_autorizada_referencia_original_y_revierte_stock(
    db,
    cliente_id,
    vehiculo_id,
    factura_service_factory,
):
    factura_original_id = insert_factura_autorizada(db, cliente_id, vehiculo_id, numero=1)
    svc = factura_service_factory(wsfe=FakeWSFE(ultimo_autorizado=0, aprobada=True, cae="CAE-NC"))

    result = svc.generar_nota_credito(factura_original_id)

    nc = db.execute(text("SELECT * FROM facturas WHERE id=:id"), {"id": result["nc_id"]}).mappings().first()
    original_estado = db.execute(text("SELECT estado_id FROM facturas WHERE id=:id"), {"id": factura_original_id}).scalar()
    vehiculo_estado = db.execute(text("SELECT estado_stock_id FROM vehiculos WHERE id=:id"), {"id": vehiculo_id}).scalar()
    venta_estado = db.execute(text("SELECT estado_id FROM ventas WHERE id=:id"), {"id": nc["venta_id"] or 1}).scalar()

    assert result["aprobada"] is True
    assert nc["factura_origen_id"] == factura_original_id
    assert nc["tipo_comprobante_id"] == 5
    assert nc["cae"] == "CAE-NC"
    assert original_estado == 16
    assert vehiculo_estado == 1
    # La venta original existe y queda cancelada.
    assert db.execute(text("SELECT estado_id FROM ventas WHERE id=(SELECT venta_id FROM facturas WHERE id=:id)"), {"id": factura_original_id}).scalar() == 33
