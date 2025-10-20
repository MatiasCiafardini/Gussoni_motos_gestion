from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.data.database import SessionLocal
from app.repositories.facturas_repository import FacturasRepository
from app.services.catalogos_service import CatalogosService


class FacturasService:
    """Orquesta casos de uso de Facturación (listado, detalle, alta, etc.)."""

    def __init__(self) -> None:
        # Servicio de catálogos con caché global (estados, tipos de comprobante, etc.)
        self._catalogos = CatalogosService()

    # -------------------- Infra --------------------
    def _repo(self, db: Optional[Session] = None) -> FacturasRepository:
        return FacturasRepository(db or SessionLocal())

    # -------------------- Lookups (desde caché) --------------------
    def get_tipos_comprobante(self) -> List[Dict[str, Any]]:
        """
        Tipos de comprobante admitidos (Factura A/B/C, Notas de crédito/débito, etc.)
        """
        db = SessionLocal()
        try:
            return self._repo(db).list_tipos_comprobante()
        finally:
            db.close()

    def get_estados_facturas(self) -> List[Dict[str, Any]]:
        """
        Estados de las facturas (Borrador, Pendiente, Autorizada, etc.)
        Usa la tabla unificada 'estados' con tipo='facturas'.
        """
        # Primero intenta leer del caché
        estados = self._catalogos.get_value_safe("estados_facturas")
        if estados:
            return estados

        db = SessionLocal()
        try:
            estados = self._repo(db).list_estados_facturas()
            self._catalogos.set("estados_facturas", estados)
            return estados
        finally:
            db.close()

    # -------------------- Search / Read --------------------
    def search(
        self,
        filtros: Dict[str, Any],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Búsqueda paginada de facturas.
        Filtros admitidos: tipo, cliente, cuit, estado_id, fecha_desde/hasta, etc.
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            rows, total = repo.search(filtros, page=page, page_size=page_size)
            return rows, total
        finally:
            db.close()

    def get(self, factura_id: int) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            return self._repo(db).get_by_id(factura_id)
        finally:
            db.close()

    # -------------------- Alta (opcional) --------------------
    def create_factura(self, data: Dict[str, Any]) -> int:
        """
        Crea una factura y devuelve su ID.
        En esta etapa sólo inserta localmente (no genera CAE).
        """
        db = SessionLocal()
        try:
            repo = self._repo(db)
            payload = dict(data)

            # Normalización mínima: vacíos → NULL
            for k in ("cliente_id", "estado_id", "pto_vta", "numero", "total"):
                if payload.get(k) in ("", " ", None):
                    payload[k] = None

            fn = getattr(repo, "create_factura", None)
            if not callable(fn):
                raise AttributeError(
                    "FacturasRepository no implementa un método create_factura compatible."
                )

            new_id = fn(payload)
            if not new_id:
                new_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

            db.commit()
            return int(new_id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # -------------------- Utilidades opcionales --------------------
    def warmup_catalogos(self) -> None:
        """Permite precargar catálogos en memoria (estados_facturas, etc.)."""
        self._catalogos.warmup_all()

    # --- Helper para acceso seguro a cache ---
    def _catalogos_get_value_safe(self, key: str):
        try:
            cache = self._catalogos
            if hasattr(cache, "get_value"):
                return cache.get_value(key)
            if hasattr(cache, "get"):
                return cache.get(key)
        except Exception:
            return None
