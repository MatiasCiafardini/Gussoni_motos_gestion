from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.data.database import SessionLocal
from app.repositories.vehiculos_repository import VehiculosRepository
from app.services.catalogos_service import CatalogosService


class VehiculosService:
    """Orquesta casos de uso de Vehículos."""

    def __init__(self) -> None:
        # Servicio de catálogos con caché global (colores, estados, condiciones, proveedores)
        self._catalogos = CatalogosService()

    # -------------------- Infra --------------------
    def _repo(self, db: Optional[Session] = None) -> VehiculosRepository:
        return VehiculosRepository(db or SessionLocal())

    # -------------------- Lookups (desde caché) --------------------
    def get_colores(self) -> List[Dict[str, Any]]:
        # Lee del caché; si falta, hace warmup automáticamente
        return self._catalogos.get_colores()

    def get_estados_stock(self) -> List[Dict[str, Any]]:
        return self._catalogos.get_estados_stock()

    def get_estados_condicion(self) -> List[Dict[str, Any]]:
        """
        Nueva/Usada. Usa tabla 'estados_moto' si existe (vía CatalogosService).
        """
        return self._catalogos.get_condiciones()

    def get_proveedores(self) -> List[Dict[str, Any]]:
        """
        Devuelve proveedores (activos por defecto) para combos.
        """
        return self._catalogos.get_proveedores()

    # -------------------- Search / CRUD --------------------
    def search(
        self,
        filtros: Dict[str, Any],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Recibe un dict de filtros (marca, modelo, anio, nro_cuadro, nro_motor,
        color/color_id, estado_stock_id, estado_moto_id, nro_certificado, nro_dnrpa,
        observaciones, etc.) y delega al repositorio.

        Importante: Pasamos el dict completo como primer argumento para aprovechar
        la compatibilidad del repositorio (detecta dict y mapea automáticamente),
        evitando olvidar campos nuevos en el futuro.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            # Pasamos 'filtros' directamente (el repo soporta dict como primer arg)
            rows, total = repo.search(filtros, page=page, page_size=page_size)
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

    def create_vehiculo(self, data: Dict[str, Any]) -> int:
        """
        Crea un vehículo y devuelve el ID insertado.
        Se adapta al nombre del método que tenga el repositorio:
        - create_vehiculo / create / add_vehiculo / add / insert / insert_vehiculo
        Fallback: usa SELECT LAST_INSERT_ID() si el repo no devuelve el ID.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)

            # normalizaciones mínimas (dejá la validación fuerte en la UI)
            payload = dict(data)
            # evita strings vacíos que rompan enteros/numéricos en MySQL
            for k in ("anio", "color_id", "estado_stock_id", "estado_moto_id", "proveedor_id"):
                if payload.get(k) in ("", " ", None):
                    payload[k] = None

            method_names = [
                "create_vehiculo", "create",
                "add_vehiculo", "add",
                "insert_vehiculo", "insert",
            ]
            fn = None
            for name in method_names:
                cand = getattr(repo, name, None)
                if callable(cand):
                    fn = cand
                    break

            if fn is None:
                raise AttributeError(
                    "VehiculosRepository no implementa un método de creación compatible "
                    "(esperado: create_vehiculo/create/add_vehiculo/add/insert_vehiculo/insert)"
                )

            result = fn(payload)

            # Intentamos deducir el ID devuelto
            new_id: Optional[int] = None
            if isinstance(result, int):
                new_id = result
            elif isinstance(result, dict) and "id" in result:
                try:
                    new_id = int(result["id"])
                except Exception:
                    new_id = None

            # Fallback: obtener LAST_INSERT_ID() en esta misma sesión
            if not new_id:
                try:
                    new_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
                    if new_id is not None:
                        new_id = int(new_id)
                except Exception:
                    new_id = None

            if not new_id:
                raise RuntimeError("No se pudo determinar el ID del nuevo vehículo insertado.")

            db.commit()
            return int(new_id)

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # -------------------- Utilidades opcionales --------------------
    def warmup_catalogos(self) -> None:
        """
        Permite precargar catálogos manualmente (por ejemplo al iniciar la app).
        No hace nada si ya están cacheados.
        """
        self._catalogos.warmup_all()
