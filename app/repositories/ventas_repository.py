from __future__ import annotations
from typing import Dict, Any, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import date

class VentasRepository:
    def __init__(self, db: Session):
        self.db = db

    def metrics_mes_actual(self) -> Dict[str, Any]:
        today = date.today()
        first = today.replace(day=1)
        fin = date(first.year + (1 if first.month == 12 else 0),
                   1 if first.month == 12 else first.month + 1, 1)
        row = self.db.execute(text("""
            SELECT COUNT(*) AS cantidad, COALESCE(SUM(precio_operacion),0) AS total
            FROM ventas WHERE fecha >= :ini AND fecha < :fin
        """), {"ini": first, "fin": fin}).mappings().one()
        return {"cantidad": int(row["cantidad"]), "total": float(row["total"])}

    def ultimas(self, limit: int = 6) -> List[Dict[str, Any]]:
        q = text("""
            SELECT v.id AS venta_id, DATE(ven.fecha) AS fecha, c.nombre AS cliente,
                   vh.marca, vh.modelo, ven.precio_operacion
            FROM ventas ven
            JOIN clientes c ON c.id = ven.cliente_id
            JOIN vehiculos vh ON vh.id = ven.vehiculo_id
            ORDER BY ven.fecha DESC
            LIMIT :lim
        """)
        return [dict(r) for r in self.db.execute(q, {"lim": limit}).mappings().all()]
