from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.data.database import SessionLocal
from app.repositories.clientes_repository import ClientesRepository
from app.services.catalogos_service import CatalogosService


class ClientesService:
    """Orquesta casos de uso de Clientes."""

    def __init__(self) -> None:
        # Servicio de catálogos con caché global (tipos documento, estados, etc.)
        self._catalogos = CatalogosService()

    # -------------------- Infra --------------------
    def _repo(self, db: Optional[Session] = None) -> ClientesRepository:
        return ClientesRepository(db or SessionLocal())

    # -------------------- Lookups (desde caché) --------------------
    def get_tipos_documento(self) -> List[Dict[str, Any]]:
        """
        Intenta obtener desde CatalogosService; si no hay, devuelve defaults.
        """
        try:
            tipos = self._catalogos.get_tipos_documento()
            if tipos:
                return tipos
        except Exception:
            pass
        # fallback
        return [
            {"codigo": "DNI", "nombre": "DNI"},
            {"codigo": "CUIT", "nombre": "CUIT"},
            {"codigo": "CUIL", "nombre": "CUIL"},
        ]

    def get_estados_clientes(self) -> List[Dict[str, Any]]:
        """
        Estados de cliente (1 Activo / 0 Inactivo).
        """
        try:
            estados = self._catalogos.get_estados_clientes()
            if estados:
                return estados
        except Exception:
            pass
        # fallback
        return [{"id": 1, "nombre": "Activo"}, {"id": 0, "nombre": "Inactivo"}]

    # -------------------- Search / CRUD --------------------
    def search(
        self,
        filtros: Dict[str, Any],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Recibe un dict de filtros (nombre, apellido, tipo_doc, nro_doc, email,
        direccion, estado_id, q, etc.) y delega al repositorio.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            rows, total = repo.search(filtros, page=page, page_size=page_size)
            return rows, total
        finally:
            db.close()

    def get(self, cliente_id: int) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            return self._repo(db).get_by_id(cliente_id)
        finally:
            db.close()

    def update(self, cliente_id: int, data: Dict[str, Any]) -> int:
        db = SessionLocal()
        try:
            payload = dict(data)
            # normalizaciones suaves
            for k in ("estado_id",):
                if payload.get(k) in ("", " ", None):
                    payload[k] = None
            if "nro_doc" in payload and isinstance(payload["nro_doc"], str):
                payload["nro_doc"] = "".join(ch for ch in payload["nro_doc"] if ch.isdigit()) or None

            rc = self._repo(db).update(cliente_id, payload)
            db.commit()
            return rc
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_cliente(self, data: Dict[str, Any]) -> int:
        """
        Crea un cliente y devuelve el ID insertado.
        Se adapta al nombre del método que tenga el repositorio:
        - create_cliente / create / add_cliente / add / insert_cliente / insert
        Fallback: usa SELECT LAST_INSERT_ID() si el repo no devuelve el ID.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)

            payload = dict(data)
            # normalizaciones mínimas (evitar strings vacíos)
            for k in ("estado_id",):
                if payload.get(k) in ("", " ", None):
                    payload[k] = None
            # nro_doc sólo dígitos
            if "nro_doc" in payload and isinstance(payload["nro_doc"], str):
                payload["nro_doc"] = "".join(ch for ch in payload["nro_doc"] if ch.isdigit()) or None

            method_names = [
                "create_cliente", "create",
                "add_cliente", "add",
                "insert_cliente", "insert",
            ]
            fn = None
            for name in method_names:
                cand = getattr(repo, name, None)
                if callable(cand):
                    fn = cand
                    break

            if fn is None:
                raise AttributeError(
                    "ClientesRepository no implementa un método de creación compatible "
                    "(esperado: create_cliente/create/add_cliente/add/insert_cliente/insert)"
                )

            result = fn(payload)

            new_id: Optional[int] = None
            if isinstance(result, int):
                new_id = result
            elif isinstance(result, dict) and "id" in result:
                try:
                    new_id = int(result["id"])
                except Exception:
                    new_id = None

            if not new_id:
                try:
                    new_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
                    if new_id is not None:
                        new_id = int(new_id)
                except Exception:
                    new_id = None

            if not new_id:
                raise RuntimeError("No se pudo determinar el ID del nuevo cliente insertado.")

            db.commit()
            return int(new_id)

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # -------------------- Utilidades opcionales --------------------
    def warmup_catalogos(self) -> None:
        """Precarga catálogos si aún no están cacheados."""
        self._catalogos.warmup_all()
