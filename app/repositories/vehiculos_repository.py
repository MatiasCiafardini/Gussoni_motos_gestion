from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


class VehiculosRepository:
    """Consultas a 'vehiculos' y tablas auxiliares (colores, estados) + alta."""

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
        Devuelve proveedores activos (campo 'activo' = 1) 
        con id y razón social, ordenados alfabéticamente.
        """
        try:
            sql = text("""
                SELECT id, razon_social AS proveedor
                FROM proveedores
                WHERE activo = 1
                ORDER BY razon_social ASC
            """)
            rows = self.db.execute(sql).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[repo] Error al obtener proveedores: {e}")
            return []

    # -------------------- Alta --------------------

    def exists_by_nro_cuadro(self, nro_cuadro: Optional[str]) -> bool:
        """
        True si ya existe una unidad con ese número de cuadro.
        """
        if not nro_cuadro:
            return False
        sql = text(
            "SELECT 1 FROM vehiculos WHERE numero_cuadro = :nro_cuadro LIMIT 1"
        )
        return self.db.execute(sql, {"nro_cuadro": nro_cuadro}).first() is not None

    def exists_by_nro_motor(self, nro_motor: Optional[str]) -> bool:
        """
        True si ya existe una unidad con ese número de motor.
        """
        if not nro_motor:
            return False
        sql = text(
            "SELECT 1 FROM vehiculos WHERE numero_motor = :nro_motor LIMIT 1"
        )
        return self.db.execute(sql, {"nro_motor": nro_motor}).first() is not None

    def create_vehiculo(self, data: Dict[str, Any]) -> int:
        """
        Inserta un vehículo y devuelve su ID.
        Sólo incluye las columnas presentes en 'data' para tolerar esquemas distintos.
        """
        # Normalizaciones mínimas
        if "numero_cuadro" in data and data["numero_cuadro"]:
            data["numero_cuadro"] = str(data["numero_cuadro"]).strip().upper()
        if "numero_motor" in data and data["numero_motor"]:
            data["numero_motor"] = str(data["numero_motor"]).strip().upper()

        columns = []
        values = []
        params: Dict[str, Any] = {}

        allowed = [
            "marca", "modelo", "anio",
            "nro_certificado", "nro_dnrpa",
            "numero_cuadro", "numero_motor",
            "precio_lista",
            "color_id", "estado_stock_id", "estado_moto_id",
            "proveedor_id", "observaciones", "cliente_id"
        ]
        for k in allowed:
            if k in data:
                columns.append(k)
                values.append(f":{k}")
                params[k] = data[k]

        if not columns:
            raise ValueError("No se recibieron campos para crear el vehículo.")

        sql = text(
            f"INSERT INTO vehiculos ({', '.join(columns)}) "
            f"VALUES ({', '.join(values)})"
        )
        res = self.db.execute(sql, params)

        # SQLAlchemy con MySQL: intentar lastrowid; fallback a LAST_INSERT_ID()
        new_id = getattr(res, "lastrowid", None)
        if not new_id:
            try:
                new_id = self.db.execute(text("SELECT LAST_INSERT_ID()")).scalar_one()
            except Exception:
                pass

        if not new_id:
            raise RuntimeError("No se pudo obtener el ID del vehículo insertado.")

        logger.debug(f"[repo] Vehículo creado id={new_id}")
        return int(new_id)

    # -------------------- Búsqueda / Detalle / Update --------------------

    def search(
        self,
        marca: Optional[str] = None,
        modelo: Optional[str] = None,
        anio: Optional[int] = None,
        nro_cuadro: Optional[str] = None,
        nro_motor: Optional[str] = None,
        color: Optional[str] = None,                # por nombre (compat)
        color_id: Optional[int] = None,             # por id
        estado_stock_id: Optional[int] = None,
        estado_moto_id: Optional[int] = None,       # Nueva/Usada
        page: int = 1,
        page_size: int = 25,
        # --- NUEVOS ---
        nro_certificado: Optional[str] = None,
        nro_dnrpa: Optional[str] = None,
        observaciones: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retorna lista de resultados (dict) y total.

        Compatibilidad:
        - Si te llega un dict en el primer parámetro (marca), se interpreta como 'filtros'
          y se mapean los valores automáticamente.
        """
        # ------ COMPAT: permitir pasar un dict 'filtros' como primer argumento ------
        if isinstance(marca, dict):
            filtros = marca
            modelo = filtros.get("modelo")
            anio = filtros.get("anio")
            nro_cuadro = filtros.get("nro_cuadro")
            nro_motor = filtros.get("nro_motor")
            color = filtros.get("color")
            color_id = filtros.get("color_id")
            estado_stock_id = filtros.get("estado_stock_id")
            estado_moto_id = filtros.get("estado_moto_id")
            page = filtros.get("page", page)
            page_size = filtros.get("page_size", page_size)
            nro_certificado = filtros.get("nro_certificado")
            nro_dnrpa = filtros.get("nro_dnrpa")
            observaciones = filtros.get("observaciones")
            marca = filtros.get("marca")

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
            params["anio"] = int(anio)
        if nro_cuadro:
            where.append("v.numero_cuadro LIKE :nro_cuadro")
            params["nro_cuadro"] = f"%{nro_cuadro}%"
        if nro_motor:
            where.append("v.numero_motor LIKE :nro_motor")
            params["nro_motor"] = f"%{nro_motor}%"

        # NUEVOS filtros
        if nro_certificado:
            where.append("v.nro_certificado LIKE :nro_certificado")
            params["nro_certificado"] = f"%{nro_certificado}%"
        if nro_dnrpa:
            where.append("v.nro_dnrpa LIKE :nro_dnrpa")
            params["nro_dnrpa"] = f"%{nro_dnrpa}%"
        if observaciones:
            # evitar NULL: COALESCE
            where.append("COALESCE(v.observaciones, '') LIKE :observaciones")
            params["observaciones"] = f"%{observaciones}%"

        # Filtro de color por id tiene prioridad; si no hay id, admitimos por nombre
        if color_id:
            where.append("v.color_id = :color_id")
            params["color_id"] = int(color_id)
        elif color and color.strip().lower() not in ("todos", "color (todos)"):
            where.append("LOWER(c.nombre) LIKE :color")
            params["color"] = f"%{color.lower()}%"

        if estado_stock_id:
            where.append("v.estado_stock_id = :estado_stock_id")
            params["estado_stock_id"] = int(estado_stock_id)

        if estado_moto_id:
            where.append("v.estado_moto_id = :estado_moto_id")
            params["estado_moto_id"] = int(estado_moto_id)

        where_sql = " AND ".join(where)
        offset = (max(page, 1) - 1) * max(page_size, 1)

        sql_base = f"""
            FROM vehiculos v
            LEFT JOIN colores c       ON c.id = v.color_id
            LEFT JOIN estados_stock es ON es.id = v.estado_stock_id
            LEFT JOIN estados_moto em  ON em.id = v.estado_moto_id
            LEFT JOIN proveedores p    ON p.id = v.proveedor_id
            WHERE {where_sql}
        """

        total = self.db.execute(text(f"SELECT COUNT(*) {sql_base}"), params).scalar_one()

        rows = self.db.execute(
            text(
                f"""
                SELECT
                    v.id, v.marca, v.modelo, v.anio,
                    v.nro_certificado, v.nro_dnrpa,
                    v.numero_cuadro, v.numero_motor,
                    v.precio_lista,
                    v.observaciones,
                    v.color_id,         c.nombre AS color,
                    v.estado_stock_id,  es.nombre AS estado_stock,
                    v.estado_moto_id,
                    COALESCE(em.nombre,
                        CASE v.estado_moto_id WHEN 1 THEN 'Nueva'
                                              WHEN 2 THEN 'Usada'
                                              ELSE NULL END) AS estado_moto,
                    p.razon_social AS proveedor
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
