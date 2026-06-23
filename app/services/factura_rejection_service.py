from __future__ import annotations

from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.domain_constants import EstadoStock, TipoMovimientoStock
from app.repositories.facturas_repository import FacturasRepository
from app.services.audit_log_service import AuditLogService
from app.services.stock_service import StockService


class FacturaRejectionService:
    """Revierte efectos comerciales de una factura rechazada por ARCA."""

    def __init__(
        self,
        *,
        repo_factory: Callable[[Session], FacturasRepository],
        stock_service: StockService,
        estado_venta_cancelada_getter: Callable[[], int],
        audit: AuditLogService,
    ) -> None:
        self._repo_factory = repo_factory
        self._stock = stock_service
        self._estado_venta_cancelada_getter = estado_venta_cancelada_getter
        self._audit = audit

    def procesar_rechazo(self, db: Session, factura_id: int, motivo: str = "Rechazo ARCA") -> None:
        repo = self._repo_factory(db)
        factura = repo.get_by_id(factura_id)
        if not factura:
            return

        detalle = repo.get_detalle_by_factura(factura_id)
        for item in detalle:
            vehiculo_id = item.get("vehiculo_id")
            if not vehiculo_id:
                continue
            row = db.execute(
                text(
                    """
                    SELECT id, estado_stock_id
                    FROM vehiculos
                    WHERE id = :vehiculo_id
                    LIMIT 1
                    """
                ),
                {"vehiculo_id": vehiculo_id},
            ).mappings().first()
            if not row or int(row.get("estado_stock_id") or 0) != EstadoStock.VENDIDO:
                continue

            self._stock.cambiar_estado(
                db,
                vehiculo_id=int(vehiculo_id),
                estado_nuevo_id=EstadoStock.DISPONIBLE,
                tipo_movimiento=TipoMovimientoStock.ANULACION,
                origen_tipo="facturas",
                origen_id=factura_id,
                observaciones=f"{motivo}; stock liberado.",
            )

        venta_id = factura.get("venta_id")
        if venta_id:
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

        self._audit.registrar(
            db,
            entidad="facturas",
            entidad_id=factura_id,
            accion="FACTURA_RECHAZADA_EFECTOS_REVERTIDOS",
            datos_previos={"venta_id": venta_id},
            contexto={"motivo": motivo},
        )
