from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.data.database import SessionLocal
from app.repositories.vehiculos_repository import VehiculosRepository


class VehiculosService:
    """Orquesta casos de uso de Vehículos."""

    def __init__(self) -> None:
        ...

    def _repo(self, db: Optional[Session] = None) -> VehiculosRepository:
        return VehiculosRepository(db or SessionLocal())

    # -------------------- Lookups --------------------

    def get_colores(self) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            return self._repo(db).list_colores()
        finally:
            db.close()

    def get_estados_stock(self) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            return self._repo(db).list_estados_stock()
        finally:
            db.close()

    def get_estados_condicion(self) -> List[Dict[str, Any]]:
        """
        Nueva/Usada. Intenta tabla 'estados_moto'; si no existe, lo infiere de 'vehiculos'.
        """
        db = SessionLocal()
        try:
            return self._repo(db).list_estados_condicion()
        finally:
            db.close()

    def get_proveedores(self) -> List[Dict[str, Any]]:
        """
        Devuelve proveedores (activos por defecto) para combos.
        """
        db = SessionLocal()
        try:
            return self._repo(db).list_proveedores()
        finally:
            db.close()

    # -------------------- Search / CRUD --------------------

    def search(
        self,
        filtros: Dict[str, Any],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        db = SessionLocal()
        try:
            repo = self._repo(db)
            rows, total = repo.search(
                marca=filtros.get("marca"),
                modelo=filtros.get("modelo"),
                anio=filtros.get("anio"),
                nro_cuadro=filtros.get("nro_cuadro"),
                nro_motor=filtros.get("nro_motor"),
                color=filtros.get("color"),               # nombre (no se usa si viene color_id)
                color_id=filtros.get("color_id"),
                estado_stock_id=filtros.get("estado_stock_id"),
                estado_moto_id=filtros.get("estado_moto_id"),
                page=page,
                page_size=page_size,
            )
            return rows, total
        finally:
            db.close()

    def get(self, vehiculo_id: int) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            return self._repo(db).get_by_id(vehiculo_id)
        finally:
            db.close()

    def update(self, vehiculo_id: int, data: Dict[str, Any]) -> int:
        db = SessionLocal()
        try:
            rc = self._repo(db).update(vehiculo_id, data)
            db.commit()
            return rc
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
