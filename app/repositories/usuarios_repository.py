from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

# Importación de la lógica de hashing (asumiendo que existe en el servicio)
# NOTA: En este paso, el repositorio recibe el hash ya calculado.

class UsuariosRepository:
    """Consultas a la tabla 'usuarios' + ABM."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------- Creación (Create) --------------------
    def create_user(self, data: Dict[str, Any]) -> int:
        """
        Inserta un nuevo usuario.
        El campo 'contraseña_hash' ya debe venir hasheado desde el Service.
        """
        logger.error(data)
        payload = dict(data)
        logger.error(data)
        # Tipos de datos en la base:
        # id (autoincremental), nombre, usuario, contraseña_hash, rol, 
        # email, activo (INT/BIT), fecha_creacion (se asigna por defecto en SQL)
        
        allowed = [
            "nombre", "usuario", "contraseña_hash",
            "rol", "email", "activo", "fecha_creacion"
        ]
        
        columns, values, params = [], [], {}
        for k in allowed:
            if k in payload:
                columns.append(k)
                values.append(f":{k}")
                params[k] = payload[k]

        if not columns:
            raise ValueError("No se recibieron campos para crear el usuario.")

        sql = text(
            f"INSERT INTO usuarios ({', '.join(columns)}) VALUES ({', '.join(values)})"
        )
        
        res = self.db.execute(sql, params)
        
        # Similar a la lógica de ClientesRepository [7] para obtener el ID
        new_id = getattr(res, "lastrowid", None)
        if not new_id:
            try:
                new_id = self.db.execute(text("SELECT LAST_INSERT_ID()")).scalar_one()
            except Exception:
                pass

        if not new_id:
            raise RuntimeError("No se pudo obtener el ID del usuario insertado.")
            
        logger.debug(f"[repo] Usuario creado id={new_id}")
        return int(new_id)

    # -------------------- Lectura (Read/Auth) --------------------
    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Busca un usuario por su nombre de usuario."""
        sql = text(
            """
            SELECT
                id, nombre, usuario, contraseña_hash, rol, email, activo
            FROM usuarios
            WHERE usuario = :usuario
            """
        )
        row = self.db.execute(sql, {"usuario": username}).mappings().first()
        return dict(row) if row else None

    # -------------------- Actualización (Update) --------------------
    def update(self, user_id: int, data: Dict[str, Any]) -> int:
        """Actualiza columnas permitidas de un usuario."""
        editable = [
            "nombre", "usuario", "contraseña_hash",
            "rol", "email", "activo",
        ]

        sets = []
        params: Dict[str, Any] = {"id": user_id}
        
        for k in editable:
            if k in data:
                val = data[k]
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    sets.append(f"{k} = NULL")
                else:
                    sets.append(f"{k} = :{k}")
                    params[k] = val

        if not sets:
            return 0

        sql = f"UPDATE usuarios SET {', '.join(sets)} WHERE id = :id"
        res = self.db.execute(text(sql), params) [8]
        return res.rowcount

    # -------------------- Listado (Search) --------------------
    def search(
        self,
        usuario: Optional[str] = None,
        nombre_o_email: Optional[str] = None,
        rol: Optional[str] = None,
        activo: Optional[int] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        
        where = ["(1=1)"]
        params: Dict[str, Any] = {}

        if usuario:
            where.append("LOWER(u.usuario) LIKE :usuario")
            params["usuario"] = f"%{usuario.lower()}%"
        
        if nombre_o_email:
            # Búsqueda combinada en nombre y email
            where.append("(LOWER(u.nombre) LIKE :q OR LOWER(u.email) LIKE :q)")
            params["q"] = f"%{nombre_o_email.lower()}%"
            
        if rol:
            where.append("u.rol = :rol")
            params["rol"] = rol

        if activo is not None and str(activo) != "":
            where.append("u.activo = :activo")
            params["activo"] = int(activo) if str(activo).isdigit() else 1
            
        where_sql = " AND ".join(where)
        offset = (max(page, 1) - 1) * max(page_size, 1)
        
        sql_base = f"""
        FROM usuarios u
        WHERE {where_sql}
        """

        total = self.db.execute(text(f"SELECT COUNT(*) {sql_base}"), params).scalar_one()

        rows = self.db.execute(
            text(
                f"""
                SELECT
                u.id, u.nombre, u.usuario, u.rol, u.email, u.activo, u.fecha_creacion
                {sql_base}
                ORDER BY u.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": page_size, "offset": offset},
        ).mappings().all()

        return [dict(r) for r in rows], int(total)