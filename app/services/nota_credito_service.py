from __future__ import annotations

from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.domain_constants import EstadoStock, TipoMovimientoStock
from app.repositories.facturas_repository import FacturasRepository
from app.services.stock_service import StockService


class NotaCreditoService:
    """Aplica efectos de negocio de notas de credito autorizadas."""

    def __init__(
        self,
        *,
        repo_factory: Callable[[Session], FacturasRepository],
        stock_service: StockService,
        estado_anulada_por_nc_getter: Callable[[], int],
        estado_venta_cancelada_getter: Callable[[], int],
    ) -> None:
        self._repo_factory = repo_factory
        self._stock = stock_service
        self._estado_anulada_por_nc_getter = estado_anulada_por_nc_getter
        self._estado_venta_cancelada_getter = estado_venta_cancelada_getter

    def procesar_nc_autorizada(self, db: Session, nc_id: int) -> None:
        repo = self._repo_factory(db)

        nc = repo.get_by_id(nc_id)
        if not nc:
            return

        tipo = repo.get_tipo_comprobante_by_id(nc.get("tipo_comprobante_id"))
        if not tipo or not tipo.get("es_nota_credito"):
            return

        factura_origen_id = nc.get("factura_origen_id")
        if not factura_origen_id:
            return

        factura_original = repo.get_by_id(factura_origen_id)
        if not factura_original:
            return

        repo.actualizar_estado(
            factura_origen_id,
            self._estado_anulada_por_nc_getter(),
        )

        self._devolver_stock(db, factura_origen_id, nc_id)
        self._cancelar_venta_y_cuotas(db, factura_original)

    def _devolver_stock(self, db: Session, factura_origen_id: int, nc_id: int) -> None:
        stock_rows = db.execute(
            text(
                """
                SELECT v.id, v.estado_stock_id
                FROM vehiculos v
                JOIN facturas_detalle fd ON fd.vehiculo_id = v.id
                WHERE fd.factura_id = :factura_orig_id
                """
            ),
            {"factura_orig_id": factura_origen_id},
        ).mappings().all()

        for row in stock_rows:
            self._stock.cambiar_estado(
                db,
                vehiculo_id=int(row["id"]),
                estado_nuevo_id=EstadoStock.DISPONIBLE,
                tipo_movimiento=TipoMovimientoStock.ANULACION,
                origen_tipo="facturas",
                origen_id=factura_origen_id,
                observaciones=f"Nota de credito autorizada id={nc_id}.",
            )

    def _cancelar_venta_y_cuotas(self, db: Session, factura_original: dict) -> None:
        venta_id = factura_original.get("venta_id")
        if not venta_id:
            return

        db.execute(
            text(
                """
                UPDATE ventas
                SET estado_id = :estado_cancelada
                WHERE id = :venta_id
                """
            ),
            {
                "estado_cancelada": self._estado_venta_cancelada_getter(),
                "venta_id": venta_id,
            },
        )

        plan = db.execute(
            text(
                """
                SELECT id
                FROM plan_financiacion
                WHERE venta_id = :venta_id
                """
            ),
            {"venta_id": venta_id},
        ).mappings().first()

        if not plan:
            return

        db.execute(
            text(
                """
                UPDATE cuotas
                SET estado = 'ANULADA'
                WHERE plan_id = :plan_id
                """
            ),
            {"plan_id": plan["id"]},
        )
