from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


class ClientesRepository:
    """Consultas a 'clientes' + alta/edición y catálogos auxiliares."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------- Lookups (opcionales) --------------------

    def list_tipos_documento(self) -> List[Dict[str, Any]]:
        """
        Retorna tipos de documento si existe la tabla 'tipos_documento(codigo, nombre)'.
        Fallback: defaults comunes.
        """
        try:
            rows = self.db.execute(
                text("SELECT codigo, nombre FROM tipos_documento ORDER BY nombre ASC")
            ).mappings().all()
            out = [{"codigo": r["codigo"], "nombre": r["nombre"]} for r in rows]
            if out:
                return out
        except Exception:
            pass
        return [{"codigo": "DNI", "nombre": "DNI"},
                {"codigo": "CUIT", "nombre": "CUIT"},
                {"codigo": "CUIL", "nombre": "CUIL"}]

    def list_estados_clientes(self) -> List[Dict[str, Any]]:
        """
        Estados de cliente (activo/inactivo). Si no hay tabla, devuelve defaults.
        """
        try:
            rows = self.db.execute(
                text("SELECT id, nombre FROM estados where tipo = 'clientes' ORDER BY id ASC")
            ).mappings().all()
            out = [{"id": r["id"], "nombre": r["nombre"]} for r in rows]
            if out:
                return out
        except Exception:
            pass
        return [{"id": 10, "nombre": "Activo"}, {"id": 11, "nombre": "Inactivo"}]

    # -------------------- Validaciones / existencia --------------------

    def exists_by_doc(self, tipo_doc: Optional[str], nro_doc: Optional[str]) -> bool:
        """
        True si ya existe un cliente con ese par (tipo_doc, nro_doc).
        """
        if not nro_doc or not tipo_doc:
            return False
        sql = text(
            "SELECT 1 FROM clientes WHERE tipo_doc = :tipo_doc AND nro_doc = :nro_doc LIMIT 1"
        )
        return self.db.execute(sql, {"tipo_doc": tipo_doc, "nro_doc": nro_doc}).first() is not None

    # -------------------- Alta --------------------

    def create_cliente(self, data: Dict[str, Any]) -> int:
        """
        Inserta un cliente y devuelve su ID.
        Sólo incluye las columnas presentes en 'data' para tolerar esquemas distintos.
        """
        # Normalizaciones mínimas
        payload = dict(data)
        if "nro_doc" in payload and payload["nro_doc"]:
            payload["nro_doc"] = "".join(ch for ch in str(payload["nro_doc"]) if ch.isdigit())
        if "email" in payload and payload["email"]:
            payload["email"] = str(payload["email"]).strip().lower()

        allowed = [
            "tipo_doc", "nro_doc",
            "nombre", "apellido",
            "telefono", "email",
            "direccion",
            "estado_id",           # 1/0
            "observaciones"
        ]

        columns, values, params = [], [], {}
        for k in allowed:
            if k in payload:
                columns.append(k)
                values.append(f":{k}")
                params[k] = payload[k]

        if not columns:
            raise ValueError("No se recibieron campos para crear el cliente.")

        sql = text(
            f"INSERT INTO clientes ({', '.join(columns)}) VALUES ({', '.join(values)})"
        )
        res = self.db.execute(sql, params)

        new_id = getattr(res, "lastrowid", None)
        if not new_id:
            try:
                new_id = self.db.execute(text("SELECT LAST_INSERT_ID()")).scalar_one()
            except Exception:
                pass

        if not new_id:
            raise RuntimeError("No se pudo obtener el ID del cliente insertado.")

        logger.debug(f"[repo] Cliente creado id={new_id}")
        return int(new_id)

    # -------------------- Búsqueda / Detalle / Update --------------------

    def search(
        self,
        nombre: Optional[str] = None,
        apellido: Optional[str] = None,
        tipo_doc: Optional[str] = None,
        nro_doc: Optional[str] = None,
        email: Optional[str] = None,
        direccion: Optional[str] = None,
        estado_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 25,
        q: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retorna lista de resultados (dict) y total.

        Compatibilidad:
        - Si te llega un dict en el primer parámetro (nombre), se interpreta como 'filtros'
          y se mapean automáticamente los valores.

        Nuevo:
        - Si el dict trae 'q', se usa como búsqueda general (nombre, apellido, nombre completo, nro_doc),
          pensado para combos/autocomplete.
        """
        # ------ COMPAT: permitir pasar un dict 'filtros' como primer parámetro ------
        if isinstance(nombre, dict):
            filtros = nombre
            apellido = filtros.get("apellido")
            tipo_doc = filtros.get("tipo_doc")
            nro_doc = filtros.get("nro_doc")
            email = filtros.get("email")
            direccion = filtros.get("direccion")
            estado_id = filtros.get("estado_id")
            page = filtros.get("page", page)
            page_size = filtros.get("page_size", page_size)
            q = filtros.get("q", q)
            nombre = filtros.get("nombre")

        where = ["(1=1)"]
        params: Dict[str, Any] = {}

        # ---- NUEVO: búsqueda general 'q' (para combo de facturas) ----
        if q:
            q_str = str(q).strip()
            if q_str:
                q_lower = q_str.lower()
                where.append(
                    "("
                    "LOWER(c.nombre) LIKE :q "
                    "OR LOWER(c.apellido) LIKE :q "
                    "OR LOWER(CONCAT_WS(' ', c.nombre, c.apellido)) LIKE :q "
                    "OR REPLACE(COALESCE(c.nro_doc, ''), '-', '') LIKE :q_digits "
                    ")"
                )
                params["q"] = f"%{q_lower}%"
                q_digits = "".join(ch for ch in q_str if ch.isdigit())
                params["q_digits"] = f"%{q_digits}%" if q_digits else params["q"]

        # ---- filtros tradicionales (no se tocan, mantiene página Clientes igual) ----
        if nombre:
            where.append("LOWER(c.nombre) LIKE :nombre")
            params["nombre"] = f"%{nombre.lower()}%"
        if apellido:
            where.append("LOWER(c.apellido) LIKE :apellido")
            params["apellido"] = f"%{apellido.lower()}%"
        if tipo_doc:
            where.append("c.tipo_doc = :tipo_doc")
            params["tipo_doc"] = tipo_doc
        if nro_doc:
            where.append("c.nro_doc LIKE :nro_doc")
            params["nro_doc"] = f"%{nro_doc}%"
        if email:
            where.append("LOWER(c.email) LIKE :email")
            params["email"] = f"%{email.lower()}%"
        if direccion:
            where.append("LOWER(c.direccion) LIKE :direccion")
            params["direccion"] = f"%{direccion.lower()}%"
        if estado_id is not None and str(estado_id) != "":
            where.append("c.estado_id = :estado_id")
            try:
                params["estado_id"] = int(estado_id)
            except Exception:
                params["estado_id"] = 1 if str(estado_id).lower() in ("activo", "true", "1") else 0

        where_sql = " AND ".join(where)
        offset = (max(page, 1) - 1) * max(page_size, 1)

        # Si existe una tabla de estados, mostrar el nombre; si no, inferir
        sql_base = f"""
            FROM clientes c
            LEFT JOIN estados ec ON ec.id = c.estado_id
            WHERE {where_sql}
        """

        total = self.db.execute(text(f"SELECT COUNT(*) {sql_base}"), params).scalar_one()

        rows = self.db.execute(
            text(
                f"""
                SELECT
                    c.id,
                    c.tipo_doc, c.nro_doc,
                    c.nombre, c.apellido,
                    c.telefono, c.email, c.direccion,
                    c.estado_id,
                    COALESCE(ec.nombre, CASE c.estado_id WHEN 1 THEN 'Activo' WHEN 0 THEN 'Inactivo' END) AS estado,
                    c.observaciones
                {sql_base}
                ORDER BY c.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": page_size, "offset": offset},
        ).mappings().all()

        return [dict(r) for r in rows], int(total)

    def get_by_id(self, cliente_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.execute(
            text(
                """
                SELECT
                    c.*,
                    COALESCE(ec.nombre, CASE c.estado_id WHEN 1 THEN 'Activo' WHEN 0 THEN 'Inactivo' END) AS estado_nombre
                FROM clientes c
                LEFT JOIN estados ec ON ec.id = c.estado_id
                WHERE c.id = :id
                """
            ),
            {"id": cliente_id},
        ).mappings().first()
        return dict(row) if row else None

    def update(self, cliente_id: int, data: Dict[str, Any]) -> int:
        """
        Actualiza columnas permitidas. Devuelve filas afectadas.
        """
        editable = [
            "tipo_doc", "nro_doc",
            "nombre", "apellido",
            "telefono", "email",
            "direccion",
            "estado_id",
            "observaciones",
        ]

        # Normalizaciones suaves
        payload = dict(data)
        if "nro_doc" in payload and payload["nro_doc"] is not None:
            payload["nro_doc"] = "".join(ch for ch in str(payload["nro_doc"]) if ch.isdigit())
        if "email" in payload and payload["email"]:
            payload["email"] = str(payload["email"]).strip().lower()

        sets = []
        params: Dict[str, Any] = {"id": cliente_id}

        for k in editable:
            if k in payload:
                val = payload[k]
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    # si querés evitar setear NULL para ciertos campos, filtralo aquí
                    sets.append(f"{k} = NULL")
                else:
                    sets.append(f"{k} = :{k}")
                    params[k] = val

        if not sets:
            return 0

        sql = f"UPDATE clientes SET {', '.join(sets)} WHERE id = :id"
        res = self.db.execute(text(sql), params)
        return res.rowcount
