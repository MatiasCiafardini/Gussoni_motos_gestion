from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session


class FacturasRepository:
    """Consultas a 'facturas' y catálogos auxiliares para facturación."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------- Lookups --------------------

    def list_tipos_comprobante(self) -> List[Dict[str, Any]]:
        """
        Tipos de comprobante (tabla opcional 'tipos_comprobante').
        Fallback a códigos comunes AR.
        """
        try:
            rows = self.db.execute(
                text("SELECT codigo, nombre FROM tipos_comprobante ORDER BY nombre ASC")
            ).mappings().all()
            out = [{"codigo": r["codigo"], "nombre": r["nombre"]} for r in rows]
            if out:
                return out
        except Exception:
            pass
        return [
            {"codigo": "FA", "nombre": "Factura A"},
            {"codigo": "FB", "nombre": "Factura B"},
            {"codigo": "FC", "nombre": "Factura C"},
            {"codigo": "NCA", "nombre": "Nota de crédito A"},
            {"codigo": "NCB", "nombre": "Nota de crédito B"},
            {"codigo": "NCC", "nombre": "Nota de crédito C"},
            {"codigo": "NDA", "nombre": "Nota de débito A"},
            {"codigo": "NDB", "nombre": "Nota de débito B"},
            {"codigo": "NDC", "nombre": "Nota de débito C"},
        ]

    def list_estados_facturas(self) -> List[Dict[str, Any]]:
        """
        Estados de facturas desde 'estados' (tipo='facturas'), si existe.
        Fallback vacío (UI mostrará "Todos").
        """
        try:
            rows = self.db.execute(
                text("SELECT id, nombre FROM estados WHERE tipo = 'facturas' ORDER BY nombre ASC")
            ).mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # -------------------- Búsqueda / Detalle --------------------

    def search(
        self,
        filters: Dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filtros admitidos (coinciden con tu UI):
          - tipo (código), pto_vta, numero, cliente (texto), cuit (texto -> se compara con clientes.nro_doc)
          - estado_id (int)
          - fecha_desde (YYYY-MM-DD), fecha_hasta (YYYY-MM-DD)
        """
        f = filters or {}
        where = ["(1=1)"]
        params: Dict[str, Any] = {}

        # tipo comprobante
        if f.get("tipo"):
            where.append("f.tipo = :tipo")
            params["tipo"] = f["tipo"]

        # punto de venta
        if f.get("pto_vta"):
            where.append("f.punto_venta = :pto_vta")
            params["pto_vta"] = f["pto_vta"]

        # número (like)
        if f.get("numero"):
            where.append("CAST(f.numero AS CHAR) LIKE :numero")
            params["numero"] = f"%{f['numero']}%"

        # cliente por nombre/apellido
        if f.get("cliente"):
            where.append("LOWER(CONCAT_WS(' ', c.nombre, c.apellido)) LIKE :cliente")
            params["cliente"] = f"%{str(f['cliente']).lower()}%"

        # CUIT/CUIL del filtro -> usamos nro_doc (solo dígitos)
        if f.get("cuit"):
            doc_digits = "".join(ch for ch in str(f["cuit"]) if ch.isdigit())
            if doc_digits:
                where.append("REPLACE(COALESCE(c.nro_doc, ''), '-', '') LIKE :doc")
                params["doc"] = f"%{doc_digits}%"

        # estado
        if f.get("estado_id") not in (None, "", "null"):
            where.append("f.estado_id = :estado_id")
            params["estado_id"] = int(f["estado_id"])

        # fechas (solo si vienen)
        if f.get("fecha_desde"):
            where.append("f.fecha_emision >= :fd")
            params["fd"] = f["fecha_desde"]
        if f.get("fecha_hasta"):
            where.append("f.fecha_emision <= :fh")
            params["fh"] = f["fecha_hasta"]

        where_sql = " AND ".join(where)
        offset = (max(page, 1) - 1) * max(page_size, 1)

        sql_base = f"""
            FROM facturas f
            LEFT JOIN clientes c ON c.id = f.cliente_id
            LEFT JOIN estados  e ON e.id = f.estado_id
            WHERE {where_sql}
        """

        total = self.db.execute(text(f"SELECT COUNT(*) {sql_base}"), params).scalar_one()

        rows = self.db.execute(
            text(
                f"""
                SELECT
                    f.id,
                    f.fecha_emision AS fecha,
                    f.tipo,
                    f.punto_venta    AS pto_vta,
                    f.numero,
                    CONCAT_WS(' ', c.nombre, c.apellido) AS cliente,
                    TRIM(CONCAT(COALESCE(c.tipo_doc, ''), 
                                CASE WHEN c.tipo_doc IS NULL OR c.tipo_doc = '' THEN '' ELSE ' ' END,
                                COALESCE(c.nro_doc, ''))) AS cuit,
                    f.total,
                    f.estado_id,
                    e.nombre AS estado,
                    f.cae,
                    f.vto_cae,
                    f.observaciones
                {sql_base}
                ORDER BY f.fecha_emision DESC, f.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": page_size, "offset": offset},
        ).mappings().all()

        return [dict(r) for r in rows], int(total)

    def get_by_id(self, factura_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.execute(
            text(
                """
                SELECT
                    f.*,
                    CONCAT_WS(' ', c.nombre, c.apellido) AS cliente,
                    TRIM(CONCAT(COALESCE(c.tipo_doc, ''), 
                                CASE WHEN c.tipo_doc IS NULL OR c.tipo_doc = '' THEN '' ELSE ' ' END,
                                COALESCE(c.nro_doc, ''))) AS cuit,
                    e.nombre AS estado_nombre
                FROM facturas f
                LEFT JOIN clientes c ON c.id = f.cliente_id
                LEFT JOIN estados  e ON e.id = f.estado_id
                WHERE f.id = :id
                """
            ),
            {"id": factura_id},
        ).mappings().first()
        return dict(row) if row else None
