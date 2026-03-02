from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.data.database import SessionLocal
from app.repositories.remitos_repository import RemitosRepository


class RemitosService:
    """Orquesta casos de uso de Remitos."""

    ESTADO_EMITIDO = "Emitido"
    ESTADO_ENTREGADO = "Entregado"
    ESTADO_ANULADO = "Anulado"

    def __init__(self) -> None:
        pass

    # ---------------- Infra ----------------

    def _repo(self, db: Optional[Session] = None) -> RemitosRepository:
        return RemitosRepository(db or SessionLocal())

    # ---------------- Numeración ----------------

    def sugerir_proximo_numero(self, pto_vta: int) -> int:
        db = SessionLocal()
        try:
            repo = self._repo(db)
            return repo.get_next_numero(pto_vta)
        finally:
            db.close()

    # ---------------- Crear Remito Completo ----------------

    def create_remito_completo(
        self,
        cabecera: Dict[str, Any],
        items: List[Dict[str, Any]],
    ) -> int:

        db = SessionLocal()

        try:
            repo = self._repo(db)

            if not cabecera.get("cliente_id"):
                raise ValueError("Cliente requerido.")

            if not cabecera.get("punto_venta"):
                raise ValueError("Punto de venta requerido.")

            if not items:
                raise ValueError("Debe agregar al menos un vehículo.")

            pto_vta = int(cabecera.get("punto_venta"))

            # ---------------- Numeración ----------------
            numero = cabecera.get("numero")
            if not numero:
                numero = repo.get_next_numero(pto_vta)

            # ---------------- Validar stock ----------------
            vehiculo_ids = {
                it.get("vehiculo_id")
                for it in items
                if it.get("vehiculo_id")
            }

            rows = db.execute(
                text("""
                    SELECT id, estado_stock_id
                    FROM vehiculos
                    WHERE id IN :ids
                """),
                {"ids": tuple(vehiculo_ids)},
            ).mappings().all()

            no_disponibles = [
                r["id"] for r in rows if int(r["estado_stock_id"] or 0) != 1
            ]

            if no_disponibles:
                raise ValueError(
                    f"Vehículos no disponibles para remito: {no_disponibles}"
                )

            # ---------------- Insert cabecera ----------------
            cabecera_db = {
                "numero": int(numero),
                "punto_venta": pto_vta,
                "fecha_emision": cabecera.get("fecha_emision") or datetime.now(),
                "cliente_id": cabecera.get("cliente_id"),
                "venta_id": cabecera.get("venta_id"),
                "observaciones": cabecera.get("observaciones"),
                "estado": self.ESTADO_EMITIDO,
            }

            remito_id = repo.insert_remito(cabecera_db)

            # ---------------- Insert detalle ----------------
            repo.insert_detalle(remito_id, items)

            # ---------------- Actualizar stock ----------------
            db.execute(
                text("""
                    UPDATE vehiculos
                    SET estado_stock_id = 3  -- Vendido
                    WHERE id IN :ids
                """),
                {"ids": tuple(vehiculo_ids)},
            )

            db.commit()
            return remito_id

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ---------------- Buscar ----------------

    def search(
        self,
        filtros: Dict[str, Any],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:

        db = SessionLocal()
        try:
            repo = self._repo(db)
            return repo.search(filtros, page=page, page_size=page_size)
        finally:
            db.close()

    # ---------------- Obtener detalle ----------------

    def get(self, remito_id: int) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            repo = self._repo(db)
            return repo.get_by_id(remito_id)
        finally:
            db.close()

    def get_detalle(self, remito_id: int) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            repo = self._repo(db)
            return repo.get_detalle_by_remito(remito_id)
        finally:
            db.close()

    # ---------------- Anular ----------------

    def anular(self, remito_id: int) -> None:

        db = SessionLocal()

        try:
            repo = self._repo(db)

            detalle = repo.get_detalle_by_remito(remito_id)

            vehiculo_ids = [
                d["vehiculo_id"]
                for d in detalle
                if d.get("vehiculo_id")
            ]

            # devolver stock
            if vehiculo_ids:
                db.execute(
                    text("""
                        UPDATE vehiculos
                        SET estado_stock_id = 1
                        WHERE id IN :ids
                    """),
                    {"ids": tuple(vehiculo_ids)},
                )

            # marcar remito anulado
            db.execute(
                text("""
                    UPDATE remitos
                    SET estado = :estado
                    WHERE id = :id
                """),
                {
                    "estado": self.ESTADO_ANULADO,
                    "id": remito_id,
                },
            )

            db.commit()

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()