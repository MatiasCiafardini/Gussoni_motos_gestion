from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.conftest import build_factura_payload
from tests.fixtures.arca_fakes import FakeWSFE


def test_no_se_puede_facturar_vehiculo_no_disponible(db, cliente_id, vehiculo_id, factura_service_factory):
    db.execute(text("UPDATE vehiculos SET estado_stock_id=2 WHERE id=:id"), {"id": vehiculo_id})
    db.commit()
    svc = factura_service_factory(wsfe=FakeWSFE(ultimo_autorizado=0, aprobada=True))
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id)

    with pytest.raises(ValueError, match="no disponibles"):
        svc.create_factura_completa(cabecera, items)


def test_rechazo_arca_libera_stock(db, cliente_id, vehiculo_id, factura_service_factory):
    svc = factura_service_factory(wsfe=FakeWSFE(ultimo_autorizado=0, aprobada=False))
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id)
    factura_id = svc.create_factura_completa(cabecera, items)
    svc.autorizar_en_arca(factura_id)

    assert db.execute(text("SELECT estado_stock_id FROM vehiculos WHERE id=:id"), {"id": vehiculo_id}).scalar() == 1
