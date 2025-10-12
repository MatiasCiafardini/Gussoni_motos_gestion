from __future__ import annotations
from typing import List, Dict, Any, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

class ProveedoresRepository:
    def __init__(self, db: Session):
        self.db = db

    def search(
        self, nombre: str | None, cuit: str | None, email: str | None,
        limit: int = 10, offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Devuelve (rows, total). No filtramos por 'estado' porque la tabla no lo tiene.
        """
        where = ["1=1"]
        params: Dict[str, Any] = {}
        if nombre:
            where.append("p.razon_social LIKE :nombre")
            params["nombre"] = f"%{nombre.strip()}%"
        if cuit:
            where.append("p.cuit LIKE :cuit")
            params["cuit"] = f"%{cuit.strip().replace('-', '')}%"
        if email:
            where.append("p.email LIKE :email")
            params["email"] = f"%{email.strip()}%"

        base = f"""
            FROM proveedores p
            WHERE {" AND ".join(where)}
        """
        total = self.db.execute(text(f"SELECT COUNT(*) {base}"), params).scalar_one()
        q = text(f"""
            SELECT p.id, p.razon_social AS nombre, p.cuit, p.email, p.telefono, p.direccion
            {base}
            ORDER BY p.id DESC
            LIMIT :limit OFFSET :offset
        """)
        params |= {"limit": limit, "offset": offset}
        rows = [dict(r) for r in self.db.execute(q, params).mappings().all()]
        return rows, int(total)
