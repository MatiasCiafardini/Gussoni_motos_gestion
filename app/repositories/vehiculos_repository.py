from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


class VehiculosRepository:
    """Consultas a 'vehiculos' y tablas auxiliares (colores, estados)."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------- Lookups --------------------

    def list_colores(self) -> List[Dict[str, Any]]:
        """
        Retorna colores desde tabla 'colores(id, nombre)'.
        """
        sql = text("SELECT id, nombre FROM colores ORDER BY nombre ASC")
        rows = self.db.execute(sql).mappings().all()
        return [dict(r) for r in rows]

    def list_estados_stock(self) -> List[Dict[str, Any]]:
        """
        Retorna estados de stock desde 'estados_stock(id, nombre)'.
        Si en tu BD se llama 'estado_stock', intentamos fallback.
        """
        try:
            rows = self.db.execute(
                text("SELECT id, nombre FROM estados_stock ORDER BY nombre ASC")
            ).mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            rows = self.db.execute(
                text("SELECT id, nombre FROM estado_stock ORDER BY nombre ASC")
            ).mappings().all()
            return [dict(r) for r in rows]

    def list_estados_condicion(self) -> List[Dict[str, Any]]:
        """
        Condición de la moto (Nueva/Usada).
        1) Intenta tabla 'estados_moto(id, nombre)' si existe.
        2) Fallback: distinct desde vehiculos.estado_moto_id con nombres comunes.
        """
        try:
            rows = self.db.execute(
                text("SELECT id, nombre FROM estados_moto ORDER BY nombre ASC")
            ).mappings().all()
            if rows:
                return [dict(r) for r in rows]
        except Exception:
            pass

        # Fallback: inferido desde vehiculos
        rows = self.db.execute(
            text(
                """
                SELECT DISTINCT
                    estado_moto_id AS id,
                    CASE estado_moto_id
                        WHEN 1 THEN 'Nueva'
                        WHEN 2 THEN 'Usada'
                        ELSE CONCAT('Estado ', estado_moto_id)
                    END AS nombre
                FROM vehiculos
                WHERE estado_moto_id IS NOT NULL
                ORDER BY id ASC
                """
            )
        ).mappings().all()
        return [dict(r) for r in rows]
    
    def list_proveedores(self) -> List[Dict[str, Any]]:
        """
        Devuelve proveedores para combos siendo tolerantes a diferencias de esquema.
        Prueba, en orden:
          - proveedores(nombre)
          - proveedores(razon_social)
          - proveedores(COALESCE(nombre, razon_social, nombre_fantasia))
          - proveedor(nombre/razon_social)
        Además, el filtro de 'activo' se aplica sólo si la columna existe.
        """
        # 1) Armamos versiones con/ sin 'activo'
        base_variants = [
            # tabla proveedores
            "SELECT p.id, p.nombre AS nombre FROM proveedores p {filtro} ORDER BY nombre ASC",
            "SELECT p.id, p.razon_social AS nombre FROM proveedores p {filtro} ORDER BY nombre ASC",
            "SELECT p.id, COALESCE(p.nombre, p.razon_social, p.nombre_fantasia, CONCAT('Proveedor ', p.id)) AS nombre "
            "FROM proveedores p {filtro} ORDER BY nombre ASC",
            # tabla proveedor (singular)
            "SELECT p.id, p.nombre AS nombre FROM proveedor p {filtro} ORDER BY nombre ASC",
            "SELECT p.id, p.razon_social AS nombre FROM proveedor p {filtro} ORDER BY nombre ASC",
            "SELECT p.id, COALESCE(p.nombre, p.razon_social, p.nombre_fantasia, CONCAT('Proveedor ', p.id)) AS nombre "
            "FROM proveedor p {filtro} ORDER BY nombre ASC",
        ]

        # ¿Existe la columna 'activo'? Si existe, usamos filtro; si no, sin filtro.
        filtro_activo_sql = """
            SELECT COUNT(*) AS n
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name IN ('proveedores','proveedor')
              AND column_name = 'activo'
        """
        try:
            has_activo = bool(self.db.execute(text(filtro_activo_sql)).scalar())
        except Exception:
            has_activo = False

        filtro = "WHERE (p.activo = 1 OR p.activo IS NULL)" if has_activo else ""

        # Probar variantes en orden hasta que alguna funcione y traiga filas
        for tmpl in base_variants:
            sql_txt = tmpl.format(filtro=filtro)
            try:
                rows = self.db.execute(text(sql_txt)).mappings().all()
                if rows:
                    data = [dict(r) for r in rows]
                    logger.debug(f"[repo] Proveedores cargados: {len(data)} con SQL: {sql_txt}")
                    return data
            except Exception as e:
                logger.debug(f"[repo] Variante proveedores falló: {e} | SQL: {sql_txt}")
                continue

        logger.warning("[repo] No se encontraron proveedores con las variantes probadas.")
        return []

    # -------------------- Búsqueda / Detalle / Update --------------------

    def search(
        self,
        marca: Optional[str] = None,
        modelo: Optional[str] = None,
        anio: Optional[int] = None,
        nro_cuadro: Optional[str] = None,
        nro_motor: Optional[str] = None,
        color: Optional[str] = None,                # por nombre (compat)
        color_id: Optional[int] = None,             # nuevo: por id
        estado_stock_id: Optional[int] = None,
        estado_moto_id: Optional[int] = None,       # nuevo: Nueva/Usada
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retorna lista de resultados (dict) y total.
        """
        where = ["(1=1)"]
        params: Dict[str, Any] = {}

        if marca:
            where.append("v.marca LIKE :marca")
            params["marca"] = f"%{marca}%"
        if modelo:
            where.append("v.modelo LIKE :modelo")
            params["modelo"] = f"%{modelo}%"
        if anio:
            where.append("v.anio = :anio")
            params["anio"] = anio
        if nro_cuadro:
            where.append("v.numero_cuadro LIKE :nro_cuadro")
            params["nro_cuadro"] = f"%{nro_cuadro}%"
        if nro_motor:
            where.append("v.numero_motor LIKE :nro_motor")
            params["nro_motor"] = f"%{nro_motor}%"

        # Filtro de color por id tiene prioridad; si no hay id, admitimos por nombre (evitando placeholders)
        if color_id:
            where.append("v.color_id = :color_id")
            params["color_id"] = color_id
        elif color and color.strip().lower() not in ("todos", "color (todos)"):
            where.append("LOWER(c.nombre) LIKE :color")
            params["color"] = f"%{color.lower()}%"

        if estado_stock_id:
            where.append("v.estado_stock_id = :estado_stock_id")
            params["estado_stock_id"] = estado_stock_id

        if estado_moto_id:
            where.append("v.estado_moto_id = :estado_moto_id")
            params["estado_moto_id"] = estado_moto_id

        where_sql = " AND ".join(where)
        offset = (max(page, 1) - 1) * max(page_size, 1)

        sql_base = f"""
            FROM vehiculos v
            LEFT JOIN colores c ON c.id = v.color_id
            LEFT JOIN estados_stock es ON es.id = v.estado_stock_id
            LEFT JOIN estados_moto em ON em.id = v.estado_moto_id
            LEFT JOIN proveedores p ON p.id = v.proveedor_id
            WHERE {where_sql}
        """

        total = self.db.execute(text(f"SELECT COUNT(*) {sql_base}"), params).scalar_one()

        rows = self.db.execute(
            text(
                f"""
                SELECT
                    v.id, v.marca, v.modelo, v.anio, v.nro_certificado, v.nro_dnrpa,
                    v.numero_cuadro, v.numero_motor,
                    v.precio_lista,
                    v.color_id, c.nombre AS color,
                    p.razon_social AS proveedor,
                    v.estado_stock_id, es.nombre AS estado_stock,
                    v.estado_moto_id, COALESCE(em.nombre,
                        CASE v.estado_moto_id WHEN 1 THEN 'Nueva'
                                              WHEN 2 THEN 'Usada'
                                              ELSE NULL END) AS estado_moto
                {sql_base}
                ORDER BY v.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": page_size, "offset": offset},
        ).mappings().all()

        return [dict(r) for r in rows], int(total)

    def get_by_id(self, vehiculo_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.execute(
            text(
                """
                SELECT
                    v.*,
                    c.nombre AS color_nombre,
                    es.nombre AS estado_stock_nombre,
                    COALESCE(em.nombre,
                        CASE v.estado_moto_id WHEN 1 THEN 'Nueva'
                                              WHEN 2 THEN 'Usada'
                                              ELSE NULL END) AS estado_moto_nombre
                FROM vehiculos v
                LEFT JOIN colores c ON c.id = v.color_id
                LEFT JOIN estados_stock es ON es.id = v.estado_stock_id
                LEFT JOIN estados_moto em ON em.id = v.estado_moto_id
                WHERE v.id = :id
                """
            ),
            {"id": vehiculo_id},
        ).mappings().first()
        return dict(row) if row else None

    def update(self, vehiculo_id: int, data: Dict[str, Any]) -> int:
        """
        Actualiza columnas permitidas. Devuelve filas afectadas.
        Si proveedor_id está vacío o None, lo setea explícitamente a NULL.
        """
        editable = [
            "marca", "modelo", "anio", "nro_certificado", "nro_dnrpa",
            "numero_cuadro", "numero_motor", "precio_lista",
            "color_id", "estado_stock_id", "estado_moto_id",
            "proveedor_id", "observaciones", "cliente_id"
        ]
    
        sets = []
        params: Dict[str, Any] = {"id": vehiculo_id}
    
        for k in editable:
            # Si el campo está presente en data
            if k in data:
                val = data[k]
    
                # ---- manejo especial para proveedor_id ----
                if k == "proveedor_id" and (val is None or val == "" or str(val).lower() in ("none", "null")):
                    sets.append(f"{k} = NULL")
                    continue  # no lo agregamos a params
                
                # otros campos normales
                sets.append(f"{k} = :{k}")
                params[k] = val
    
        if not sets:
            return 0
    
        sql = f"UPDATE vehiculos SET {', '.join(sets)} WHERE id = :id"
        res = self.db.execute(text(sql), params)
        return res.rowcount
    