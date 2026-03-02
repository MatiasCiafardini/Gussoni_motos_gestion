from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session


class RemitosRepository:
    """Consultas a 'remitos' y 'remitos_detalle'."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------- Numeración --------------------

    def get_next_numero(self, pto_vta: int) -> int:
        row = self.db.execute(
            text("""
                SELECT MAX(numero) AS ultimo
                FROM remitos
                WHERE punto_venta = :pto
            """),
            {"pto": pto_vta}
        ).mappings().first()

        ultimo = row["ultimo"] if row and row["ultimo"] else 0
        return int(ultimo) + 1


    # -------------------- Alta --------------------

    def insert_remito(self, cabecera: Dict[str, Any]) -> int:

        result = self.db.execute(
            text("""
                INSERT INTO remitos (
                    numero,
                    punto_venta,
                    fecha_emision,
                    cliente_id,
                    venta_id,
                    observaciones,
                    estado
                )
                VALUES (
                    :numero,
                    :punto_venta,
                    :fecha_emision,
                    :cliente_id,
                    :venta_id,
                    :observaciones,
                    :estado
                )
            """),
            {
                "numero": cabecera.get("numero"),
                "punto_venta": cabecera.get("punto_venta"),
                "fecha_emision": cabecera.get("fecha_emision"),
                "cliente_id": cabecera.get("cliente_id"),
                "venta_id": cabecera.get("venta_id"),
                "observaciones": cabecera.get("observaciones"),
                "estado": cabecera.get("estado", "Emitido"),
            },
        )

        new_id = result.lastrowid
        return int(new_id) if new_id is not None else new_id


    def insert_detalle(self, remito_id: int, items: List[Dict[str, Any]]) -> None:

        if not items:
            return

        for it in items:
            self.db.execute(
                text("""
                    INSERT INTO remitos_detalle (
                        remito_id,
                        vehiculo_id,
                        descripcion,
                        observaciones
                    )
                    VALUES (
                        :remito_id,
                        :vehiculo_id,
                        :descripcion,
                        :observaciones
                    )
                """),
                {
                    "remito_id": remito_id,
                    "vehiculo_id": it.get("vehiculo_id"),
                    "descripcion": it.get("descripcion"),
                    "observaciones": it.get("observaciones"),
                },
            )


    # -------------------- Consulta --------------------

    def get_by_id(self, remito_id: int) -> Optional[Dict[str, Any]]:

        row = self.db.execute(
            text("""
                SELECT
                    r.*,
                    c.nombre        AS cliente_nombre,
                    c.apellido      AS cliente_apellido,
                    c.nro_doc       AS cliente_nro_doc,
                    c.tipo_doc_id      AS cliente_tipo_doc,
                    c.direccion     AS cliente_direccion,
                    c.telefono      AS cliente_telefono
                FROM remitos r
                LEFT JOIN clientes c ON c.id = r.cliente_id
                LEFT JOIN tipos_documento dt on c.tipo_doc_id = dt.id
                WHERE r.id = :id
            """),
            {"id": remito_id},
        ).mappings().first()

        return dict(row) if row else None


    def get_detalle_by_remito(self, remito_id: int) -> List[Dict[str, Any]]:

        rows = self.db.execute(
            text("""
                SELECT
                    rd.id,
                    rd.remito_id,
                    rd.vehiculo_id,
                    rd.descripcion,
                    rd.observaciones,
                    v.marca,
                    v.modelo,
                    v.numero_cuadro,
                    v.numero_motor,
                    v.anio,
                    v.nro_certificado
                FROM remitos_detalle rd
                LEFT JOIN vehiculos v ON v.id = rd.vehiculo_id
                WHERE rd.remito_id = :rid
                ORDER BY rd.id ASC
            """),
            {"rid": remito_id},
        ).mappings().all()

        return [dict(r) for r in rows]


    # -------------------- Búsqueda --------------------

    def search(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:

        f: Dict[str, Any] = filters or {}
        where = ["(1=1)"]
        params: Dict[str, Any] = {}

        offset = (max(page, 1) - 1) * max(page_size, 1)

        if f.get("numero"):
            where.append("CAST(r.numero AS CHAR) LIKE :numero")
            params["numero"] = f"%{f['numero']}%"

        if f.get("cliente"):
            where.append("LOWER(CONCAT_WS(' ', c.nombre, c.apellido)) LIKE :cliente")
            params["cliente"] = f"%{str(f['cliente']).lower()}%"

        if f.get("fecha_desde"):
            where.append("r.fecha_emision >= :fd")
            params["fd"] = f["fecha_desde"]

        if f.get("fecha_hasta"):
            where.append("r.fecha_emision <= :fh")
            params["fh"] = f["fecha_hasta"]

        where_sql = " AND ".join(where)

        sql_base = f"""
            FROM remitos r
            LEFT JOIN clientes c ON c.id = r.cliente_id
            WHERE {where_sql}
        """

        total = self.db.execute(
            text(f"SELECT COUNT(*) {sql_base}"),
            params
        ).scalar_one()

        rows = self.db.execute(
            text(f"""
                SELECT
                    r.id,
                    r.numero,
                    r.punto_venta,
                    r.fecha_emision,
                    CONCAT_WS(' ', c.nombre, c.apellido) AS cliente,
                    r.estado
                {sql_base}
                ORDER BY r.fecha_emision DESC, r.id DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": page_size, "offset": offset},
        ).mappings().all()

        return [dict(r) for r in rows], int(total)