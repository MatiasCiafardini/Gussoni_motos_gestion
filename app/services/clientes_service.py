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
            return []
    def get_estados_clientes(self) -> List[Dict[str, Any]]:
        """
        Devuelve estados de cliente desde catálogo.
        """
        try:
            estados = self._catalogos.get_estados_clientes()
            return estados or []
        except Exception:
            return []
    

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
            rows, total = repo.search(filtros, page=page, page_size=page_size)

            if not rows:
                return rows, total

            # 🔥 Agregamos tipo_doc_label desde catálogo
            for r in rows:
                tipo = self._catalogos.get_tipo_doc_by_id(r.get("tipo_doc_id"))
                if tipo:
                    r["tipo_doc_label"] = tipo.get("descripcion") or tipo.get("codigo")
                else:
                    r["tipo_doc_label"] = ""


            return rows, total

        finally:
            db.close()


    def get(self, cliente_id: int) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            row = self._repo(db).get_by_id(cliente_id)
            if not row:
                return None

            tipo = self._catalogos.get_tipo_doc_by_id(row.get("tipo_doc_id"))
            if tipo:
                row["tipo_doc_label"] = tipo.get("descripcion") or tipo.get("codigo")
            else:
                row["tipo_doc_label"] = ""


            return row

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
