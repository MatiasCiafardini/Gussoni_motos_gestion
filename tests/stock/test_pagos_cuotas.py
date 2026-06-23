from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text

from app.services.pagos_service import PagosService
from tests.fixtures.db_factory import insert_factura_autorizada


def _crear_plan_con_cuotas(db, venta_id: int, cuotas: list[float]) -> int:
    plan = db.execute(
        text(
            """
            INSERT INTO plan_financiacion
            (venta_id,cantidad_cuotas,importe_cuota,fecha_inicio,monto_financiado)
            VALUES (:venta,:cantidad,:importe,:fecha,:monto)
            """
        ),
        {
            "venta": venta_id,
            "cantidad": len(cuotas),
            "importe": cuotas[0],
            "fecha": datetime.now(),
            "monto": sum(cuotas),
        },
    )
    plan_id = int(plan.lastrowid)
    for nro, monto in enumerate(cuotas, start=1):
        db.execute(
            text(
                """
                INSERT INTO cuotas (plan_id,nro_cuota,fecha_vencimiento,monto,monto_pagado,estado)
                VALUES (:plan,:nro,:vto,:monto,0,'PENDIENTE')
                """
            ),
            {
                "plan": plan_id,
                "nro": nro,
                "vto": (datetime.now() + timedelta(days=30 * nro)).strftime("%Y-%m-%d"),
                "monto": monto,
            },
        )
    db.commit()
    return plan_id


def test_pago_parcial_imputa_fifo_y_deja_venta_activa(db, cliente_id, vehiculo_id):
    factura_id = insert_factura_autorizada(db, cliente_id, vehiculo_id, numero=40)
    venta_id = db.execute(text("SELECT venta_id FROM facturas WHERE id=:id"), {"id": factura_id}).scalar()
    db.execute(text("UPDATE ventas SET estado_id=31 WHERE id=:id"), {"id": venta_id})
    _crear_plan_con_cuotas(db, venta_id, [1000, 1000])

    result = PagosService().registrar_pago(
        venta_id=venta_id,
        cliente_id=cliente_id,
        monto=500,
        forma_pago_id=1,
        observaciones="Pago parcial QA",
    )

    cuotas = db.execute(
        text("SELECT nro_cuota,monto_pagado,estado FROM cuotas ORDER BY nro_cuota")
    ).mappings().all()
    venta_estado = db.execute(text("SELECT estado_id FROM ventas WHERE id=:id"), {"id": venta_id}).scalar()

    assert result["cuotas_pagadas"] == 0
    assert result["cuotas_parciales"] == 1
    assert cuotas[0]["monto_pagado"] == 500
    assert cuotas[0]["estado"] == "PARCIAL"
    assert cuotas[1]["monto_pagado"] == 0
    assert venta_estado == 31


def test_pago_total_cierra_venta_y_marca_factura_pagada(db, cliente_id, vehiculo_id):
    factura_id = insert_factura_autorizada(db, cliente_id, vehiculo_id, numero=41)
    venta_id = db.execute(text("SELECT venta_id FROM facturas WHERE id=:id"), {"id": factura_id}).scalar()
    db.execute(text("UPDATE ventas SET estado_id=31 WHERE id=:id"), {"id": venta_id})
    _crear_plan_con_cuotas(db, venta_id, [1000, 1000])

    result = PagosService().registrar_pago(
        venta_id=venta_id,
        cliente_id=cliente_id,
        monto=2000,
        forma_pago_id=1,
        observaciones="Pago total QA",
    )

    pendientes = db.execute(text("SELECT COUNT(*) FROM cuotas WHERE estado <> 'PAGADA'")).scalar()
    venta_estado = db.execute(text("SELECT estado_id FROM ventas WHERE id=:id"), {"id": venta_id}).scalar()
    factura_estado = db.execute(text("SELECT estado_id FROM facturas WHERE id=:id"), {"id": factura_id}).scalar()

    assert result["cuotas_pagadas"] == 2
    assert result["cuotas_parciales"] == 0
    assert pendientes == 0
    assert venta_estado == 32
    assert factura_estado == 22
