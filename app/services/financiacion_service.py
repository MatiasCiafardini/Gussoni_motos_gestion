from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


class FinanciacionService:
    """Crea planes y cuotas dentro de una transaccion existente."""

    def crear_plan_con_cuotas(
        self,
        *,
        db: Session,
        venta_id: int,
        cantidad_cuotas: Optional[int],
        importe_cuota: Optional[float],
        fecha_inicio: Optional[datetime] = None,
    ) -> int:
        if not cantidad_cuotas or cantidad_cuotas <= 0:
            raise ValueError("Cantidad de cuotas invalida")

        if not importe_cuota or importe_cuota <= 0:
            raise ValueError("Importe de cuota invalido")

        if not fecha_inicio:
            fecha_inicio = datetime.now()

        monto_financiado = cantidad_cuotas * importe_cuota

        plan_id = db.execute(
            text(
                """
                INSERT INTO plan_financiacion
                (venta_id, cantidad_cuotas, importe_cuota, fecha_inicio, monto_financiado)
                VALUES
                (:venta_id, :cuotas, :importe_cuota, :fecha, :monto)
                """
            ),
            {
                "venta_id": venta_id,
                "cuotas": cantidad_cuotas,
                "importe_cuota": importe_cuota,
                "fecha": fecha_inicio,
                "monto": monto_financiado,
            },
        ).lastrowid

        if not plan_id:
            raise RuntimeError("No se pudo crear el plan de financiacion")

        for nro in range(1, cantidad_cuotas + 1):
            db.execute(
                text(
                    """
                    INSERT INTO cuotas
                    (plan_id, nro_cuota, fecha_vencimiento, monto)
                    VALUES
                    (:plan, :nro, DATE_ADD(:fecha, INTERVAL :mes MONTH), :importe)
                    """
                ),
                {
                    "plan": plan_id,
                    "nro": nro,
                    "mes": nro,
                    "fecha": fecha_inicio,
                    "importe": importe_cuota,
                },
            )

        return int(plan_id)
