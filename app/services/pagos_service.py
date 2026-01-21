from __future__ import annotations

from typing import Optional, Dict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from app.data.database import SessionLocal


class PagosService:
    """
    Service para registrar pagos e imputarlos automáticamente a cuotas.
    Usa SQL directo (sin ORM), consistente con el resto del proyecto.
    """

    ESTADO_VENTA_ACTIVA = 31
    ESTADO_VENTA_CERRADA = 32

    ESTADO_FACTURA_PENDIENTE = 21
    ESTADO_FACTURA_PAGADA = 22

    # -------------------------------------------------
    # SIMULACIÓN (NO escribe en DB)
    # -------------------------------------------------
    def simular_pago(self, venta_id: int, monto: float) -> Dict[str, float]:
        with SessionLocal() as db:
            # Obtener cuotas pendientes ordenadas
            cuotas = db.execute(
                text("""
                    SELECT c.id, c.monto, c.monto_pagado
                    FROM cuotas c
                    JOIN plan_financiacion p ON p.id = c.plan_id
                    WHERE p.venta_id = :venta_id
                      AND c.estado <> 'PAGADA'
                    ORDER BY c.nro_cuota ASC
                """),
                {"venta_id": venta_id}
            ).mappings().all()

            if not cuotas:
                raise ValueError("No hay cuotas pendientes.")

            monto_restante = Decimal(str(monto))
            cuotas_pagadas = 0
            cuotas_parciales = 0

            for c in cuotas:
                if monto_restante <= 0:
                    break

                saldo = c["monto"] - c["monto_pagado"]
                aplicado = min(saldo, monto_restante)

                if aplicado >= saldo:
                    cuotas_pagadas += 1
                else:
                    cuotas_parciales += 1

                monto_restante -= aplicado

            return {
                "cuotas_pagadas": cuotas_pagadas,
                "cuotas_parciales": cuotas_parciales,
                "monto_restante": monto_restante,
            }
    def get_detalle_venta(self, venta_id: int):
        with SessionLocal() as db:
            row = db.execute(
                text("""
                    SELECT
                        v.id AS venta_id,
                        v.precio_total,
                        v.anticipo,
                        ve.marca,
                        ve.modelo,
                        ve.anio,
                        pf.cantidad_cuotas,
                        pf.interes_pct,
                        pf.monto_financiado
                    FROM ventas v
                    JOIN vehiculos ve ON ve.id = v.vehiculo_id
                    LEFT JOIN plan_financiacion pf ON pf.venta_id = v.id
                    WHERE v.id = :venta_id
                """),
                {"venta_id": venta_id}
            ).mappings().first()
    
            if not row:
                raise ValueError("La venta no existe.")
    
            # Moto
            moto = f'{row["marca"]} {row["modelo"]} ({row["anio"]})'
    
            # Precio
            precio = row["precio_total"] or 0
    
            # Financiación
            if row["cantidad_cuotas"]:
                financiacion = (
                    f'{row["cantidad_cuotas"]} cuotas'
                    f' (interés {row["interes_pct"] or 0}%)'
                )
            else:
                financiacion = "Contado"
    
            return {
                "venta_id": row["venta_id"],
                "moto": moto,
                "precio": float(precio),
                "financiacion": financiacion,
            }
    

    def get_cuotas_venta(self, venta_id: int):
        with SessionLocal() as db:
            rows = db.execute(
                text("""
                    SELECT
                        c.id,
                        c.nro_cuota,
                        c.fecha_vencimiento,
                        c.monto,
                        c.monto_pagado,
                        (c.monto - c.monto_pagado) AS saldo_pendiente,
                        c.estado,
                        MAX(p.fecha) AS fecha_ultimo_pago
                    FROM cuotas c
                    JOIN plan_financiacion pf ON pf.id = c.plan_id
                    LEFT JOIN pagos_detalle pd ON pd.cuota_id = c.id
                    LEFT JOIN pagos p ON p.id = pd.pago_id
                    WHERE pf.venta_id = :venta_id
                    GROUP BY
                        c.id,
                        c.nro_cuota,
                        c.fecha_vencimiento,
                        c.monto,
                        c.monto_pagado,
                        c.estado
                    ORDER BY c.nro_cuota ASC
                """),
                {"venta_id": venta_id}
            ).mappings().all()

            cuotas = []
            for r in rows:
                cuotas.append({
                    "id": r["id"],
                    "nro": r["nro_cuota"],
                    "importe": float(r["monto"]),
                    "pagado": float(r["monto_pagado"]),
                    "pendiente": float(r["saldo_pendiente"]),
                    "estado": r["estado"],
                    "vencimiento": r["fecha_vencimiento"].strftime("%Y-%m-%d"),
                    "fecha_pago": (
                        r["fecha_ultimo_pago"].strftime("%Y-%m-%d")
                        if r["fecha_ultimo_pago"] else "-"
                    ),
                })

            return cuotas




    # -------------------------------------------------
    # REGISTRO REAL
    # -------------------------------------------------
    def registrar_pago(
        self,
        venta_id: int,
        cliente_id: int,
        monto: float,
        forma_pago_id: int,
        observaciones: Optional[str] = None
    ) -> Dict[str, float]:

        with SessionLocal() as db:
            try:
                # Validar venta
                venta = db.execute(
                    text("SELECT estado_id FROM ventas WHERE id = :id"),
                    {"id": venta_id}
                ).mappings().first()

                if not venta:
                    raise ValueError("La venta no existe.")

                if venta["estado_id"] != self.ESTADO_VENTA_ACTIVA:
                    raise ValueError("La venta no está activa.")

                # Crear pago
                res = db.execute(
                    text("""
                        INSERT INTO pagos
                            (fecha, venta_id, cliente_id, monto, forma_pago_id, observaciones)
                        VALUES
                            (:fecha, :venta_id, :cliente_id, :monto, :forma_pago_id, :obs)
                    """),
                    {
                        "fecha": datetime.now(),
                        "venta_id": venta_id,
                        "cliente_id": cliente_id,
                        "monto": monto,
                        "forma_pago_id": forma_pago_id,
                        "obs": observaciones,
                    }
                )
                pago_id = res.lastrowid

                # Cuotas pendientes
                cuotas = db.execute(
                    text("""
                        SELECT c.id, c.monto, c.monto_pagado
                        FROM cuotas c
                        JOIN plan_financiacion p ON p.id = c.plan_id
                        WHERE p.venta_id = :venta_id
                          AND c.estado <> 'PAGADA'
                        ORDER BY c.nro_cuota ASC
                    """),
                    {"venta_id": venta_id}
                ).mappings().all()

                monto_restante = Decimal(str(monto))

                cuotas_pagadas = 0
                cuotas_parciales = 0

                for c in cuotas:
                    if monto_restante <= 0:
                        break

                    saldo = c["monto"] - c["monto_pagado"]
                    aplicado = min(saldo, monto_restante)

                    # pagos_detalle
                    db.execute(
                        text("""
                            INSERT INTO pagos_detalle
                                (pago_id, cuota_id, monto_aplicado)
                            VALUES
                                (:pago_id, :cuota_id, :monto)
                        """),
                        {
                            "pago_id": pago_id,
                            "cuota_id": c["id"],
                            "monto": aplicado,
                        }
                    )

                    # actualizar cuota
                    nuevo_pagado = c["monto_pagado"] + aplicado
                    estado = "PAGADA" if nuevo_pagado >= c["monto"] else "PARCIAL"

                    db.execute(
                        text("""
                            UPDATE cuotas
                            SET monto_pagado = :pagado,
                                estado = :estado
                            WHERE id = :id
                        """),
                        {
                            "pagado": nuevo_pagado,
                            "estado": estado,
                            "id": c["id"],
                        }
                    )

                    if estado == "PAGADA":
                        cuotas_pagadas += 1
                    else:
                        cuotas_parciales += 1

                    monto_restante -= aplicado

                # ¿quedan cuotas?
                pendientes = db.execute(
                    text("""
                        SELECT 1
                        FROM cuotas c
                        JOIN plan_financiacion p ON p.id = c.plan_id
                        WHERE p.venta_id = :venta_id
                          AND c.estado <> 'PAGADA'
                        LIMIT 1
                    """),
                    {"venta_id": venta_id}
                ).first()

                if not pendientes:
                    db.execute(
                        text("UPDATE ventas SET estado_id = :e WHERE id = :id"),
                        {"e": self.ESTADO_VENTA_CERRADA, "id": venta_id}
                    )

                    db.execute(
                        text("""
                            UPDATE facturas
                            SET estado_id = :e
                            WHERE venta_id = :venta_id
                        """),
                        {"e": self.ESTADO_FACTURA_PAGADA, "venta_id": venta_id}
                    )

                db.commit()

                return {
                    "cuotas_pagadas": cuotas_pagadas,
                    "cuotas_parciales": cuotas_parciales,
                    "monto_restante": monto_restante,
                }

            except Exception:
                db.rollback()
                raise
