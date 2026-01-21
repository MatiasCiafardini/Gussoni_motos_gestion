from __future__ import annotations
from typing import List, Dict, Any
from sqlalchemy import text
from datetime import date

from app.data.database import SessionLocal


class DashboardService:
    """
    Servicio exclusivo para el Dashboard.
    Centraliza TODA la lógica de cobranza y métricas.
    """

    UPCOMING_DAYS = 7

    # -------------------------
    # KPIs principales
    # -------------------------

    def get_resumen_cobranza(self) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            deuda_vencida = db.execute(
                text("""
                    SELECT COALESCE(SUM(monto - monto_pagado), 0)
                    FROM cuotas
                    WHERE estado != 'PAGADA'
                      AND fecha_vencimiento < CURDATE()
                """)
            ).scalar() or 0

            cuotas_vencidas = db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM cuotas
                    WHERE estado != 'PAGADA'
                      AND fecha_vencimiento < CURDATE()
                """)
            ).scalar() or 0

            cuotas_proximas = db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM cuotas
                    WHERE estado != 'PAGADA'
                      AND fecha_vencimiento BETWEEN CURDATE()
                                                AND DATE_ADD(CURDATE(), INTERVAL :dias DAY)
                """),
                {"dias": self.UPCOMING_DAYS}
            ).scalar() or 0

            facturas_pendientes_mes = self.get_facturas_pendientes_mes()

            return {
                "deuda_vencida": float(deuda_vencida),
                "cuotas_vencidas": int(cuotas_vencidas),
                "cuotas_proximas": int(cuotas_proximas),
                "facturas_pendientes_mes": int(facturas_pendientes_mes),
            }
        finally:
            db.close()

    # -------------------------
    # Listados
    # -------------------------

    def get_cuotas_proximas(self, limit: int = 5) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = db.execute(
                text("""
                    SELECT
                        c.fecha_vencimiento,
                        (c.monto - c.monto_pagado) AS saldo,
                        CONCAT(cl.nombre, ' ', cl.apellido) AS cliente
                    FROM cuotas c
                    JOIN plan_financiacion p ON p.id = c.plan_id
                    JOIN ventas v            ON v.id = p.venta_id
                    JOIN clientes cl         ON cl.id = v.cliente_id
                    WHERE c.estado != 'PAGADA'
                      AND c.fecha_vencimiento BETWEEN CURDATE()
                                                  AND DATE_ADD(CURDATE(), INTERVAL :dias DAY)
                    ORDER BY c.fecha_vencimiento ASC
                    LIMIT :lim
                """),
                {"dias": self.UPCOMING_DAYS, "lim": limit}
            ).mappings().all()

            return [dict(r) for r in rows]
        finally:
            db.close()

    def get_cuotas_vencidas(self, limit: int = 5) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = db.execute(
                text("""
                    SELECT
                        c.fecha_vencimiento,
                        (c.monto - c.monto_pagado) AS saldo,
                        CONCAT(cl.nombre, ' ', cl.apellido) AS cliente
                    FROM cuotas c
                    JOIN plan_financiacion p ON p.id = c.plan_id
                    JOIN ventas v            ON v.id = p.venta_id
                    JOIN clientes cl         ON cl.id = v.cliente_id
                    WHERE c.estado != 'PAGADA'
                      AND c.fecha_vencimiento < CURDATE()
                    ORDER BY c.fecha_vencimiento ASC
                    LIMIT :lim
                """),
                {"lim": limit}
            ).mappings().all()

            return [dict(r) for r in rows]
        finally:
            db.close()

    # -------------------------
    # Unidades vendidas
    # -------------------------

    def get_unidades_vendidas_por_mes(self, limit: int = 6) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = db.execute(
                text("""
                    SELECT
                        DATE_FORMAT(fecha, '%Y-%m') AS mes,
                        COUNT(*) AS unidades
                    FROM ventas
                    WHERE estado_id IN (31, 32)
                    GROUP BY YEAR(fecha), MONTH(fecha)
                    ORDER BY YEAR(fecha), MONTH(fecha)
                    LIMIT :lim;
                """),
                {"lim": limit}
            ).mappings().all()

            return list(reversed([dict(r) for r in rows]))
        finally:
            db.close()

    def get_facturas_pendientes_mes(self) -> int:
        db = SessionLocal()
        try:
            return db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM facturas f
                    JOIN ventas v ON v.id = f.venta_id
                    WHERE MONTH(f.fecha_emision) = MONTH(CURDATE())
                      AND YEAR(f.fecha_emision) = YEAR(CURDATE())
                      AND v.estado_id IN (30, 31)
                """)
            ).scalar() or 0
        finally:
            db.close()

 

