from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.conftest import build_factura_payload
from tests.fixtures.arca_fakes import FakeWSFE


def test_numeracion_usa_arca_aunque_local_este_mas_alto(db, factura_service_factory):
    db.execute(
        text(
            """
            INSERT INTO facturas
            (tipo_comprobante_id,numero,fecha_emision,punto_venta,total,estado_id,cliente_id)
            VALUES (2,58,CURRENT_TIMESTAMP,2,1000,15,NULL)
            """
        )
    )
    db.commit()
    svc = factura_service_factory(wsfe=FakeWSFE(ultimo_autorizado=22, aprobada=True))

    diag = svc.diagnosticar_proximo_numero(2, 2)

    assert diag["ws_ok"] is True
    assert diag["ultimo_afip"] == 22
    assert diag["proximo_local"] == 59
    assert diag["proximo"] == 23


def test_numeracion_no_pisa_factura_existente(db, cliente_id, vehiculo_id, factura_service_factory):
    db.execute(
        text(
            """
            INSERT INTO facturas
            (tipo_comprobante_id,numero,fecha_emision,punto_venta,total,estado_id,cliente_id)
            VALUES (2,23,CURRENT_TIMESTAMP,2,1000,14,:cliente)
            """
        ),
        {"cliente": cliente_id},
    )
    db.commit()
    svc = factura_service_factory(wsfe=FakeWSFE(ultimo_autorizado=22, aprobada=True))
    cabecera, items = build_factura_payload(cliente_id, vehiculo_id)

    with pytest.raises(ValueError, match="ya existe en la base local"):
        svc.create_factura_completa(cabecera, items)
