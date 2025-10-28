from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.data.database import SessionLocal


class UsuariosRepository:
    """
    Repositorio CRUD de usuarios usando SQLAlchemy Session (como Vehículos).
    NO crea ni cierra la sesión si se la pasan desde el service.
    """

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db: Session = db or SessionLocal()
        self._own_session = db is None  # por si querés usar este repo standalone

    # ---------------------------------------------------------------------
    # Helpers para aceptar dict o kwargs (compat con tu patrón de Vehículos)
    # ---------------------------------------------------------------------
    def _unpack_filters(
        self,
        filtros: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if isinstance(filtros, dict):
            base = dict(filtros)
            base.update(kwargs or {})
            return base
        return dict(kwargs or {})

    # ---------------------------------------------------------------------
    # Search
    # ---------------------------------------------------------------------
    def search(
        self,
        filtros: Optional[Dict[str, Any]] = None,
        *,
        nombre: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        rol_id: Optional[int] = None,
        estado_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:

        f = self._unpack_filters(
            filtros,
            nombre=nombre,
            username=username,
            email=email,
            rol_id=rol_id,
            estado_id=estado_id,
            page=page,
            page_size=page_size,
        )

        # Normalizaciones mínimas
        def _clean(s: Any) -> Optional[str]:
            if isinstance(s, str):
                s = s.strip()
                return s.lower() if s else None
            return None

        nombre = _clean(f.get("nombre"))
        username = _clean(f.get("username"))
        email = _clean(f.get("email"))
        try:
            rol_id = int(f.get("rol_id")) if f.get("rol_id") is not None else None
        except Exception:
            rol_id = None
        try:
            estado_id = int(f.get("estado_id")) if f.get("estado_id") is not None else None
        except Exception:
            estado_id = None

        where = ["1=1"]
        params: Dict[str, Any] = {}

        if nombre:
            where.append("LOWER(u.nombre) LIKE :nombre")
            params["nombre"] = f"%{nombre}%"
        if username:
            where.append("LOWER(u.usuario) LIKE :usuario")
            params["usuario"] = f"%{username}%"
        if email:
            where.append("LOWER(u.email) LIKE :email")
            params["email"] = f"%{email}%"

        if rol_id is not None:
            if rol_id == 1:
                where.append("LOWER(u.rol) = 'admin'")
            elif rol_id == 2:
                where.append("LOWER(u.rol) = 'vendedor'")

        if estado_id is not None:
            where.append("u.activo = :activo")
            params["activo"] = 1 if estado_id == 1 else 0

        # Total
        count_sql = text(f"SELECT COUNT(*) AS c FROM usuarios u WHERE {' AND '.join(where)}")
        total = int(self.db.execute(count_sql, params).scalar() or 0)

        # Paginado
        offset = max((page - 1) * page_size, 0)
        sql = text(f"""
            SELECT u.id,
                   u.nombre,
                   u.usuario AS username,
                   u.rol,
                   u.email,
                   u.activo,
                   CASE WHEN u.activo = 1 THEN 'Activo' ELSE 'Inactivo' END AS estado,
                   u.fecha_creacion
            FROM usuarios u
            WHERE {' AND '.join(where)}
            ORDER BY u.id DESC
            LIMIT :limit OFFSET :offset
        """)
        params.update({"limit": page_size, "offset": offset})

        rows = self.db.execute(sql, params).mappings().all()

        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["rol_id"] = 1 if (d.get("rol") or "").lower() == "admin" else 2
            d["estado_id"] = 1 if d.get("activo") else 0
            d["rol_nombre"] = d.get("rol", "")
            d["estado_nombre"] = d.get("estado", "")
            out.append(d)

        return out, total

    # ---------------------------------------------------------------------
    # Catálogos
    # ---------------------------------------------------------------------
    def get_roles(self) -> List[Dict[str, Any]]:
        sql = text("SELECT DISTINCT rol FROM usuarios WHERE rol IS NOT NULL ORDER BY rol")
        rows = self.db.execute(sql).mappings().all()
        roles = []
        for r in rows:
            rol = (r.get("rol") or "").strip()
            if not rol:
                continue
            roles.append({"id": 1 if rol.lower() == "admin" else 2, "nombre": rol})
        if not roles:
            roles = [{"id": 1, "nombre": "Administrador"}, {"id": 2, "nombre": "Vendedor"}]
        return roles

    def get_estados(self) -> List[Dict[str, Any]]:
        return [{"id": 1, "nombre": "Activo"}, {"id": 0, "nombre": "Inactivo"}]

    # ---------------------------------------------------------------------
    # CRUD
    # ---------------------------------------------------------------------
    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        sql = text("""
            SELECT id, nombre, usuario AS username, rol, email, activo, fecha_creacion
            FROM usuarios
            WHERE id = :id
        """)
        row = self.db.execute(sql, {"id": user_id}).mappings().first()
        return dict(row) if row else None

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        sql = text("""
            SELECT id,
                   nombre,
                   usuario AS username,
                   rol,
                   email,
                   activo,
                   contrasenia_hash,
                   CASE WHEN LOWER(rol) = 'admin' THEN 1 ELSE 2 END AS rol_id,
                   CASE WHEN activo = 1 THEN 1 ELSE 0 END AS estado_id
            FROM usuarios
            WHERE LOWER(usuario) = LOWER(:usuario)
            LIMIT 1
        """)
        row = self.db.execute(sql, {"usuario": username}).mappings().first()
        return dict(row) if row else None

    def insert(self, data: Dict[str, Any]) -> int:
        """
        Espera keys: nombre, usuario, contrasenia_hash, rol, email, activo
        """
        sql = text("""
            INSERT INTO usuarios (nombre, usuario, contrasenia_hash, rol, email, activo, fecha_creacion)
            VALUES (:nombre, :usuario, :contrasenia_hash, :rol, :email, :activo, NOW())
        """)
        result = self.db.execute(sql, data)
        # el commit lo hace el service
        return int(result.lastrowid or 0)

    def update(self, user_id: int, data: Dict[str, Any]) -> int:
        if not data:
            return 0
        fields = []
        params = {"id": user_id}
        for k, v in data.items():
            fields.append(f"{k} = :{k}")
            params[k] = v
        sql = text(f"UPDATE usuarios SET {', '.join(fields)} WHERE id = :id")
        result = self.db.execute(sql, params)
        return int(result.rowcount or 0)

    def delete(self, user_id: int) -> int:
        sql = text("DELETE FROM usuarios WHERE id = :id")
        result = self.db.execute(sql, {"id": user_id})
        return int(result.rowcount or 0)
